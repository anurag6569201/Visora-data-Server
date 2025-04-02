import logging
import json
import os
import uuid
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods # Not strictly needed with @api_view
from django.views.decorators.csrf import csrf_exempt # Use carefully, only if needed and understood
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny # Or IsAuthenticated if required

# Use python-dotenv to load env vars if needed (handled in settings.py now)
# from dotenv import load_dotenv
# load_dotenv()

import google.generativeai as genai

logger = logging.getLogger(__name__) # Use the logger defined in settings.py

# --- Configuration ---
try:
    # Ensure GEMINI_API_KEY is loaded from environment (via settings.py)
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("CRITICAL: GEMINI_API_KEY environment variable not set.")
        # Optionally raise an ImproperlyConfigured error
    else:
        genai.configure(api_key=gemini_api_key)
        # Using Gemini 1.5 Flash as requested. Ensure this model is available to your key.
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            # Consider adding system_instruction for consistent behavior
             system_instruction="You are an AI assistant specialized in creating educational content and interactive learning materials.",
        )
        logger.info("Gemini model 'gemini-1.5-flash' configured successfully.")
except Exception as e:
    logger.error(f"CRITICAL: Failed to configure Gemini model: {e}", exc_info=True)
    model = None # Explicitly set to None if configuration fails

# --- Constants ---
MIN_DURATION_HOURS = 0.5 # Minimum allowed duration
MAX_DURATION_HOURS = 100 # Maximum allowed duration
VALID_DIFFICULTIES = ['Beginner', 'Intermediate', 'Advanced']
MAX_TOPIC_LENGTH = 150 # Max length for main topic input
DEFAULT_SUBTOPIC_TIME_MINS = 15 # Minimum time allocation per subtopic

# --- Helper Functions ---

def get_llm_error_response(message, status_code=500):
    """Standardizes LLM error responses."""
    logger.error(message)
    return JsonResponse({"error": message}, status=status_code)

def create_structure_prompt(topic: str, duration_hours: float, difficulty: str, prerequisites: str) -> str:
    """Creates the prompt for the LLM to generate the course structure JSON."""
    total_minutes = int(duration_hours * 60)
    prereq_info = f'Assumed Prerequisites: "{prerequisites}"\n' if prerequisites else ""

    # Enhanced prompt for clarity and stricter JSON adherence
    prompt = f"""
    You are an expert curriculum designer AI. Generate a detailed course structure JSON object for the following request:

    Course Topic: "{topic}"
    {prereq_info}Requested Duration: {duration_hours} hours ({total_minutes} minutes approx.)
    Target Difficulty: {difficulty}

    Output a single, valid JSON object adhering STRICTLY to this format:
    {{
      "subtopics": [
        {{
          "id": "temp_id_1", // TEMPORARY ID, sequential like temp_id_N
          "name": "Module 1: Descriptive Name", // Clear, concise name
          "time": <integer>, // Estimated time in MINUTES (min {DEFAULT_SUBTOPIC_TIME_MINS})
          "difficultyValue": <float>, // 0.0 (easy) to 1.0 (hard), reflect '{difficulty}'
          "conceptDensity": <float>, // 0.0 (sparse) to 1.0 (dense)
          "prerequisiteIds": ["temp_id_X", ...] // List temporary IDs of direct prerequisites FROM THIS LIST ONLY. Empty for initial topics. NO CYCLES.
        }}
        // ... more subtopic objects ({4 if duration_hours < 5 else (6 if duration_hours < 20 else 10)}-{8 if duration_hours < 5 else (12 if duration_hours < 20 else 20)} topics approx)
      ],
      "analysis": {{
        "difficultyCurve": [<float>, ...], // difficultyValue for each subtopic IN ORDER
        "densityCurve": [<float>, ...], // conceptDensity for each subtopic IN ORDER
        "estimatedTotalTime": <integer> // SUM of all "time" values. MUST be close to {total_minutes} mins.
      }}
    }}

    Guidelines:
    1.  **Content:** Create logical, progressive module names covering the topic.
    2.  **Time:** Distribute {total_minutes} mins realistically. Min time per module: {DEFAULT_SUBTOPIC_TIME_MINS}. `analysis.estimatedTotalTime` MUST equal the sum of module times.
    3.  **Prerequisites:** Use only `temp_id_N` from this generated list. Ensure a valid learning path.
    4.  **Values:** Assign `difficultyValue` and `conceptDensity` appropriately for the `{difficulty}` level.
    5.  **JSON Only:** Output ONLY the JSON object. No explanations, backticks, or other text.
    """
    return prompt

def post_process_structure(llm_output: dict, requested_duration_hours: float) -> dict:
    """Validates, cleans, assigns UUIDs, adjusts time, and creates graph structure."""
    if not isinstance(llm_output, dict) or "subtopics" not in llm_output or "analysis" not in llm_output:
        raise ValueError("LLM output is not a valid dictionary or missing required keys ('subtopics', 'analysis').")

    subtopics = llm_output.get("subtopics", [])
    if not isinstance(subtopics, list) or not subtopics:
         raise ValueError("'subtopics' must be a non-empty list.")

    # --- 1. ID Replacement & Basic Validation ---
    id_map = {}
    processed_subtopics = []
    temp_ids_found = set()

    for i, st in enumerate(subtopics):
        if not isinstance(st, dict) or not all(k in st for k in ["id", "name", "time", "difficultyValue", "conceptDensity", "prerequisiteIds"]):
            logger.warning(f"Skipping invalid subtopic structure at index {i}: Missing keys in {st}")
            continue
        if not isinstance(st.get("name"), str) or not st["name"]:
             logger.warning(f"Skipping subtopic at index {i}: Invalid or empty name.")
             continue
        if not isinstance(st.get("time"), int) or st["time"] < DEFAULT_SUBTOPIC_TIME_MINS:
            st["time"] = DEFAULT_SUBTOPIC_TIME_MINS
            logger.warning(f"Adjusted subtopic '{st['name']}' time to minimum {DEFAULT_SUBTOPIC_TIME_MINS} mins.")
        if not isinstance(st.get("difficultyValue"), (int, float)) or not (0.0 <= st["difficultyValue"] <= 1.0):
            st["difficultyValue"] = 0.5 # Default fallback
            logger.warning(f"Set default difficultyValue for subtopic '{st['name']}'.")
        if not isinstance(st.get("conceptDensity"), (int, float)) or not (0.0 <= st["conceptDensity"] <= 1.0):
             st["conceptDensity"] = 0.5 # Default fallback
             logger.warning(f"Set default conceptDensity for subtopic '{st['name']}'.")
        if not isinstance(st.get("prerequisiteIds"), list):
             st["prerequisiteIds"] = []
             logger.warning(f"Corrected prerequisiteIds to empty list for subtopic '{st['name']}'.")

        temp_id = st.get("id")
        if not isinstance(temp_id, str) or not temp_id.startswith("temp_id_"):
             logger.warning(f"Subtopic at index {i} has invalid temporary ID '{temp_id}'. Assigning fallback.")
             temp_id = f"temp_id_fallback_{i}" # Assign a fallback temporary ID

        if temp_id in id_map:
             logger.warning(f"Duplicate temporary ID '{temp_id}' found. Skipping duplicate entry.")
             continue

        new_id = str(uuid.uuid4())
        id_map[temp_id] = new_id
        st["id"] = new_id # Replace temp id with UUID
        temp_ids_found.add(temp_id)
        processed_subtopics.append(st)

    # Update prerequisite IDs using the map
    for st in processed_subtopics:
        valid_prereqs = []
        for temp_prereq_id in st["prerequisiteIds"]:
            if temp_prereq_id in id_map:
                # Check for self-reference
                if id_map[temp_prereq_id] == st["id"]:
                     logger.warning(f"Removed self-referencing prerequisite for topic '{st['name']}' (ID: {st['id']})")
                else:
                    valid_prereqs.append(id_map[temp_prereq_id])
            else:
                logger.warning(f"Prerequisite temporary ID '{temp_prereq_id}' listed for subtopic '{st['name']}' not found in generated subtopics. Ignoring.")
        st["prerequisiteIds"] = valid_prereqs
        # TODO: Add cycle detection if needed (more complex)

    # --- 2. Time Adjustment ---
    target_total_minutes = requested_duration_hours * 60
    current_total_minutes = sum(st["time"] for st in processed_subtopics)

    # Adjust only if the difference is significant (e.g., > 5% or > 10 mins)
    if processed_subtopics and abs(current_total_minutes - target_total_minutes) > max(10, target_total_minutes * 0.05):
        ratio = target_total_minutes / current_total_minutes
        logger.info(f"Adjusting total time from {current_total_minutes}m to target {target_total_minutes}m (ratio: {ratio:.2f})")
        accumulated_remainder = 0.0
        for st in processed_subtopics:
            new_time_float = st["time"] * ratio + accumulated_remainder
            new_time_int = max(DEFAULT_SUBTOPIC_TIME_MINS, round(new_time_float))
            accumulated_remainder = new_time_float - new_time_int # Carry over the rounding difference
            st["time"] = new_time_int
    else:
         logger.info(f"Total time {current_total_minutes}m is close enough to target {target_total_minutes}m. No major adjustment needed.")


    # Recalculate final time after adjustments
    final_total_time = sum(st["time"] for st in processed_subtopics)

    # --- 3. Create Graph Structure (Nodes and Edges) ---
    nodes = []
    edges = []
    node_width = 160 # Keep consistent with frontend if possible
    default_position = {"x": 0, "y": 0} # Frontend usually calculates layout

    # Basic color mapping (can be customized)
    def get_node_colors(diff_val):
         if diff_val > 0.7: return {'background': '#d32f2f', 'color': '#ffffff'} # Hard - Reddish
         if diff_val < 0.4: return {'background': '#388e3c', 'color': '#ffffff'} # Easy - Greenish
         return {'background': '#5823c8', 'color': '#ffffff'} # Intermediate - Purple

    for st in processed_subtopics:
        label_parts = st["name"].split(":", 1)
        label = label_parts[1].strip() if len(label_parts) > 1 else st["name"]
        colors = get_node_colors(st["difficultyValue"])

        nodes.append({
            "id": st["id"],
            "position": default_position, # Frontend layout preferred
            "data": {"label": label},
            "style": {
                "width": node_width,
                "fontSize": '0.8rem',
                "textAlign": 'center',
                "padding": '8px 10px', # Slightly more padding
                "borderRadius": '6px', # Slightly rounder
                "background": colors['background'],
                "color": colors['color'],
                "border": f"1px solid {colors['background']}" # Border matches background
            },
            "type": 'default', # Or custom node type if defined in ReactFlow
        })

        for prereq_id in st.get("prerequisiteIds", []):
             # Ensure source node exists before creating edge
            if any(n['id'] == prereq_id for n in nodes):
                 edges.append({
                    "id": f"e-{prereq_id}-{st['id']}",
                    "source": prereq_id,
                    "target": st['id'],
                    "type": 'smoothstep', # Or 'default', 'straight', etc.
                    "animated": False, # Keep false unless needed
                    "markerEnd": {"type": "arrowclosed", "width": 15, "height": 15, "color": '#666'}, # Darker arrow
                    "style": {"strokeWidth": 1.5, "stroke": '#666'} # Darker edge
                })
            else:
                 # This should ideally not happen if prereq validation worked
                 logger.error(f"Consistency Error: Prerequisite ID '{prereq_id}' for node '{st['id']}' not found in node list during edge creation.")


    # --- 4. Final Analysis Object ---
    analysis = {
        "difficultyCurve": [st.get("difficultyValue", 0.5) for st in processed_subtopics],
        "densityCurve": [st.get("conceptDensity", 0.5) for st in processed_subtopics],
        "estimatedTotalTime": int(round(final_total_time)),
    }

    logger.info(f"Structure post-processing complete. Final estimated time: {final_total_time} mins.")

    return {
        "subtopics": processed_subtopics,
        "graph": {"nodes": nodes, "edges": edges},
        "analysis": analysis
    }

def create_content_prompt(main_topic: str, subtopic_name: str, difficulty: str) -> str:
    """Creates the prompt for generating subtopic HTML content."""
    # Consistent theme instructions
    color_theme_instructions = """
    - **Styling:** Use a single `<style>` block within the snippet.
      - Body/Container: `margin: 15px; padding: 0; background-color: #212529; color: #ffffff; font-family: sans-serif; line-height: 1.6;`
      - Headings (`h2`, `h3`): `color: #bb86fc; margin-bottom: 10px;`
      - Paragraphs (`p`): `margin-bottom: 15px;`
      - Lists (`ul`, `ol`): `margin-left: 20px; margin-bottom: 15px;`
      - Links (`a`): `color: #a7d0f5; text-decoration: none;` Links should open in new tab (`target="_blank"`).
      - Links hover (`a:hover`): `text-decoration: underline;`
      - Strong/Bold (`strong`, `b`): `color: #e0e0e0;`
      - Code (`code`): `background-color: #333; padding: 2px 5px; border-radius: 3px; font-family: monospace;`
      - Blockquotes (`blockquote`): `border-left: 3px solid #5823c8; padding-left: 15px; margin-left: 0; color: #ccc;`
    - **Responsiveness:** Ensure content flows well on smaller screens. Avoid fixed widths that cause horizontal scrolling.
    """

    prompt = f"""
    You are an expert web developer and educator AI assistant.
    Generate a self-contained HTML snippet (NO `<html>`, `<head>`, or `<body>` tags) for the following learning subtopic:

    Main Course Topic: "{main_topic}"
    Target Difficulty: {difficulty}
    Current Subtopic: "{subtopic_name}"

    Include the following sections in the HTML snippet:
    1.  **Title:** Use an `<h2>` for "{subtopic_name}".
    2.  **Explanation:** 1-3 paragraphs explaining the core concepts clearly, tailored to a {difficulty} level. Use `<p>`, `<strong>`, `<em>`, and potentially `<ul>` or `<ol>` for clarity.
    3.  **Examples (Optional but Recommended):** 1-2 simple, concrete examples using `<p>` or a `<div>` with code formatting (`<code>`) if applicable.
    4.  **Key Takeaways:** A bulleted list (`<ul>`) summarizing 2-4 main points.
    5.  **Further Resources:** A list (`<ul>`) of 2-3 relevant links (`<a>` tags with `target="_blank"`). Provide real, useful URLs if possible, otherwise use placeholders like `https://example.com/resource`.

    Apply these styling requirements:
    {color_theme_instructions}

    Output ONLY the raw HTML snippet (including the necessary `<style>` block). Do not include markdown markers (```html) or any other text outside the HTML itself.
    The snippet must be directly usable inside an iframe's `srcdoc`.
    """
    return prompt

def create_assessment_prompt(subtopic_id: str, subtopic_name: str, difficulty: str, theory_context: str) -> str:
    """Creates the prompt for generating interactive HTML assessment."""
    num_questions = 4 if difficulty == 'Advanced' else (2 if difficulty == 'Beginner' else 3)
    # Consistent theme instructions, slightly adapted for forms
    color_theme_instructions = """
    - **Styling:** Use a single `<style>` block within the snippet.
      - Body/Container: `margin: 15px; padding: 0; background-color: #212529; color: #ffffff; font-family: sans-serif; line-height: 1.6;`
      - Question Container (`.question-item`): `margin-bottom: 25px; padding: 15px; border: 1px solid #444; border-radius: 5px;`
      - Question Text (`p` inside `.question-item`): `margin-bottom: 10px; font-weight: bold;`
      - Options/Labels (`label`): `display: block; margin-bottom: 8px; cursor: pointer;`
      - Radio/Checkbox (`input[type='radio']`, `input[type='checkbox']`): `margin-right: 8px;`
      - Text Area (`textarea`): `width: 95%; padding: 8px; border-radius: 4px; border: 1px solid #555; background-color: #333; color: #fff; min-height: 60px;`
      - Button (`#checkAnswersBtn`, `#retryBtn`): `padding: 10px 20px; border: none; background-color: #5823c8; color: #ffffff; border-radius: 4px; cursor: pointer; font-size: 1rem; margin-top: 10px; margin-right: 10px;`
      - Button Hover (`button:hover`): `opacity: 0.85;`
      - Button Disabled (`button:disabled`): `background-color: #555; cursor: not-allowed;`
      - Score Display (`#scoreResult`, `#feedback`): `margin-top: 20px; padding: 10px; border-radius: 4px;`
      - Correct Feedback Style (`.correct-feedback`): `color: #a5d6a7; border: 1px solid #a5d6a7; background-color: #334e3f;`
      - Incorrect Feedback Style (`.incorrect-feedback`): `color: #ef9a9a; border: 1px solid #ef9a9a; background-color: #5c3333;`
      - Visual Answer Highlight (Correct - e.g., on label): `outline: 2px solid #a5d6a7;`
      - Visual Answer Highlight (Incorrect - e.g., on label): `outline: 2px solid #ef9a9a;`
    """

    prompt = f"""
    You are an expert web developer creating interactive educational assessments.
    Generate a self-contained, interactive HTML assessment snippet for the following:

    Target Difficulty: {difficulty}
    Subtopic: "{subtopic_name}"
    Subtopic ID: "{subtopic_id}" // CRITICAL for postMessage

    Generate an HTML snippet (NO `<html>`, `<head>`, or `<body>` tags) containing:
    1.  **Assessment Form:** An HTML form (`<form id="assessmentForm">`) with {num_questions} questions on "{subtopic_name}" ({difficulty} level). Use a mix of:
        * Multiple Choice (radio buttons, name="qN", unique IDs for each input like "qN_optM").
        * Multiple Answer (checkboxes, name="qN", unique IDs).
        * Short Answer (textarea, id="qN_ans").
    2.  **Questions:** Clearly state each question within a container like `<div class="question-item">`.
    3.  **Buttons:** Include a "Check Answers" button (`<button type="button" id="checkAnswersBtn">Check Answers</button>`) and initially hidden "Retry Quiz" button (`<button type="button" id="retryBtn" style="display:none;">Retry Quiz</button>`).
    4.  **Result Areas:** Include divs for feedback: `<div id="feedback"></div>` and `<div id="scoreResult"></div>`.
    5.  **Styling:** Apply styles using ONE `<style>` block.
        {color_theme_instructions}
    6.  **JavaScript (`<script>` block at the end):**
        a.  **Data:** Store correct answers internally (e.g., `const correctAnswers = {{ q1: 'correct_id', q2: ['chk1_id', 'chk3_id'], q3: 'keyword_or_regex' }};`). Question IDs MUST match HTML element IDs.
        b.  **Event Listener (Check Answers):** Attach to `#checkAnswersBtn`. On click:
            i.   Prevent multiple submissions (disable button).
            ii.  Get user answers (check selected radio/checkboxes, textarea values). Store them in an object like `userAnswers = {{ q1: 'user_ans_1', q2: ['user_chk1', ...], q3: 'user_text' }}`.
            iii. **Grade:** Compare `userAnswers` with `correctAnswers`. Calculate `score` (0.0 to 1.0). Be flexible with text answers (lowercase, trim, keyword check).
            iv.  **Feedback:**
                 * Display the score in `#scoreResult` (e.g., "Your Score: X / {num_questions}").
                 * Provide overall feedback in `#feedback` (e.g., "Great job!", "Review the material."). Use `.correct-feedback` or `.incorrect-feedback` classes on the feedback div.
                 * Visually highlight correct/incorrect answers directly on the form elements (e.g., add classes to labels or inputs).
                 * Disable all form inputs (`input`, `textarea`).
                 * Show the 'Retry Quiz' button.
            v.   **Send Results:** Use `window.parent.postMessage` EXACTLY like this:
                 `window.parent.postMessage({{ type: 'assessmentResult', subtopicId: '{subtopic_id}', score: score, answers: userAnswers }}, '*')`
                 (Ensure `{subtopic_id}` is embedded correctly, `score` is the decimal value, `userAnswers` is the object collected).
        c.  **Event Listener (Retry):** Attach to `#retryBtn`. On click:
            i.   Reset the form (`form.reset()`).
            ii.  Remove visual highlights and feedback text.
            iii. Enable form inputs and 'Check Answers' button.
            iv.  Hide 'Retry Quiz' button.

    Output ONLY the raw HTML snippet (including `<style>` and `<script>`). No markdown markers or other text. The snippet must work in an iframe `srcdoc`.
    """
    return prompt


def create_review_prompt(subtopic_names: list[str]) -> str:
    """Creates the prompt for generating review questions."""
    if not subtopic_names:
        return "" # Should not happen if called correctly

    topic_list = "\n".join([f"- {name}" for name in subtopic_names])
    num_questions = min(max(3, len(subtopic_names) // 2), 6) # Generate 3-6 questions

    prompt = f"""
    You are an AI assistant creating review questions for a study plan.
    Based on the following completed subtopics:
    {topic_list}

    Generate a JSON array containing {num_questions} insightful review questions that encourage synthesis and critical thinking about these topics.

    Requirements:
    1.  Focus on connections between topics, applications, or deeper understanding, not just simple recall.
    2.  Questions should be clear and concise.
    3.  Output ONLY a valid JSON array of strings, where each string is a question. Example: `["Question 1?", "Question 2?"]`
    4.  Do not include ```json markers or any other text.
    """
    return prompt

def create_summary_prompt(main_topic: str, subtopic_names: list[str], total_time_mins: int) -> str:
    """Creates the prompt for generating a plan summary."""
    if not subtopic_names:
        return ""

    topic_list = ", ".join(subtopic_names[:4]) # List first few topics
    if len(subtopic_names) > 4:
        topic_list += ", and more"

    # Convert total_time_mins to hours and minutes for the prompt
    hours = total_time_mins // 60
    minutes = total_time_mins % 60
    time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"


    prompt = f"""
    You are an AI assistant writing a brief, encouraging summary for a study plan.

    Main Topic: "{main_topic}"
    Estimated Duration: {time_str} ({total_time_mins} minutes)
    Key Subtopics Covered: {topic_list}.

    Generate a concise (2-4 sentences) summary of this study plan. The tone should be informative and motivating.

    Output ONLY the summary text. Do not include any other text, titles, or formatting.
    """
    return prompt

# --- API Views ---

@api_view(['POST'])
@permission_classes([AllowAny]) # Change to IsAuthenticated if login is required
def generate_course_structure(request):
    """API endpoint to generate a course structure using Gemini."""
    if not model:
        return get_llm_error_response("AI Model not configured.", 503)

    try:
        data = json.loads(request.body.decode('utf-8'))
        topic = data.get('topic', '').strip()
        duration_hours_str = data.get('durationHours')
        difficulty = data.get('difficulty', '').strip()
        prerequisites = data.get('prerequisites', '').strip() # Get prerequisites from request

        # --- Input Validation ---
        if not topic or len(topic) > MAX_TOPIC_LENGTH:
            return JsonResponse({"error": f"Valid topic required (max {MAX_TOPIC_LENGTH} chars)."}, status=400)
        try:
            duration_hours = float(duration_hours_str)
            if not (MIN_DURATION_HOURS <= duration_hours <= MAX_DURATION_HOURS):
                 raise ValueError()
        except (TypeError, ValueError, AttributeError):
             return JsonResponse({"error": f"Invalid 'durationHours' (number between {MIN_DURATION_HOURS}-{MAX_DURATION_HOURS})."}, status=400)
        if difficulty not in VALID_DIFFICULTIES:
             return JsonResponse({"error": f"Invalid 'difficulty' (must be one of: {VALID_DIFFICULTIES})."}, status=400)

        # --- LLM Interaction ---
        prompt = create_structure_prompt(topic, duration_hours, difficulty, prerequisites)
        logger.debug(f"Generating structure with prompt:\n{prompt[:500]}...") # Log beginning of prompt

        try:
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json", # Essential for reliable JSON
                temperature=0.7 # Balance creativity and consistency
            )
            response = model.generate_content(prompt, generation_config=generation_config)

            # Robust check for blocked content or empty response
            if not response.candidates:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                 logger.error(f"Structure generation blocked. Reason: {block_reason}. Safety Ratings: {feedback.safety_ratings}")
                 # Provide a more user-friendly error
                 user_error = f"Content generation failed due to safety constraints ({block_reason}). Please revise the topic/prerequisites or contact support."
                 if block_reason == 'OTHER':
                     user_error = "Content generation failed (Reason: OTHER). This might be due to overly complex instructions or an internal issue. Please simplify your request or try again later."
                 return get_llm_error_response(user_error, 400) # Bad Request due to input potentially

            # Parse JSON - should be safe due to response_mime_type
            llm_json_output = json.loads(response.text)

        except json.JSONDecodeError as json_err:
             logger.error(f"CRITICAL: Failed to decode JSON even with mime type set! LLM Raw Text: {response.text}", exc_info=True)
             return get_llm_error_response("AI returned invalid structure format. Please try again.", 500)
        except Exception as llm_err:
             logger.error(f"Error during Gemini structure generation: {llm_err}", exc_info=True)
             return get_llm_error_response("AI assistant communication failed. Please try again later.", 502)

        # --- Post-processing ---
        try:
            processed_data = post_process_structure(llm_json_output, duration_hours)
            if not processed_data.get("subtopics"): # Check if post-processing removed all topics
                logger.error("Post-processing resulted in no valid subtopics. Original LLM JSON: %s", llm_json_output)
                return get_llm_error_response("AI generated structure could not be fully processed. Try regenerating.", 500)

        except ValueError as val_err:
             logger.error(f"Structure Validation/Processing Error: {val_err}. Original LLM JSON: {llm_json_output}", exc_info=True)
             return get_llm_error_response(f"AI data processing failed: {val_err}. Try regenerating.", 500)

        return JsonResponse(processed_data, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON request body."}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in generate_course_structure: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def generate_subtopic_content(request):
    """API endpoint to generate HTML content for a subtopic."""
    if not model:
        return get_llm_error_response("AI Model not configured.", 503)

    try:
        data = json.loads(request.body.decode('utf-8'))
        subtopic_id = data.get('subtopicId') # Keep ID for potential future use/logging
        subtopic_name = data.get('subtopicName', '').strip()
        difficulty = data.get('difficulty', '').strip()
        main_topic = data.get('mainTopic', '').strip()

        # --- Input Validation ---
        if not subtopic_name or not subtopic_id or not main_topic or difficulty not in VALID_DIFFICULTIES:
            return JsonResponse({"error": "Missing required fields (subtopicId, subtopicName, mainTopic) or invalid difficulty."}, status=400)

        prompt = create_content_prompt(main_topic, subtopic_name, difficulty)
        logger.debug(f"Generating HTML content for: {subtopic_name}")

        try:
             # Plain text response expected for HTML
            generation_config = genai.types.GenerationConfig(temperature=0.6)
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                 logger.error(f"HTML content generation blocked for '{subtopic_name}'. Reason: {block_reason}.")
                 return get_llm_error_response(f"HTML Content generation blocked ({block_reason}).", 400)

            html_content = response.text.strip()

            # Basic HTML validation (ensure it's not empty and looks like HTML)
            if not html_content or not (html_content.startswith('<') and html_content.endswith('>')):
                 logger.warning(f"LLM output for '{subtopic_name}' content doesn't look like valid HTML: {html_content[:100]}...")
                 # Decide whether to return potentially broken HTML or an error
                 # return get_llm_error_response("AI generated invalid HTML content.", 500)
                 # For now, return what we got, frontend might handle it
                 logger.info("Returning potentially incomplete/invalid HTML from LLM.")

        except Exception as llm_err:
            logger.error(f"Error during Gemini HTML content generation for '{subtopic_name}': {llm_err}", exc_info=True)
            return get_llm_error_response("AI assistant communication failed for content generation.", 502)

        return JsonResponse({'html': html_content}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON request body."}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in generate_subtopic_content: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def generate_subtopic_assessment(request):
    """API endpoint to generate an interactive HTML assessment."""
    if not model:
        return get_llm_error_response("AI Model not configured.", 503)

    try:
        data = json.loads(request.body.decode('utf-8'))
        subtopic_id = data.get('subtopicId')
        subtopic_name = data.get('subtopicName', '').strip()
        difficulty = data.get('difficulty', '').strip()
        theory_context = data.get('theoryContext', '') # Optional context

        if not subtopic_id or not subtopic_name or difficulty not in VALID_DIFFICULTIES:
             return JsonResponse({"error": "Missing required fields (subtopicId, subtopicName) or invalid difficulty."}, status=400)

        prompt = create_assessment_prompt(subtopic_id, subtopic_name, difficulty, theory_context)
        logger.debug(f"Generating HTML assessment for: {subtopic_name} (ID: {subtopic_id})")

        try:
            generation_config = genai.types.GenerationConfig(temperature=0.75) # Slightly higher temp for varied questions
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                 logger.error(f"HTML assessment generation blocked for '{subtopic_name}'. Reason: {block_reason}.")
                 return get_llm_error_response(f"HTML Assessment generation blocked ({block_reason}).", 400)

            html_content = response.text.strip()

            # Basic validation for interactive elements
            if not html_content or not (html_content.startswith('<') and html_content.endswith('>')):
                 logger.warning(f"LLM assessment output for '{subtopic_name}' doesn't look like HTML.")
            if '<script>' not in html_content or 'window.parent.postMessage' not in html_content or subtopic_id not in html_content:
                 logger.warning(f"LLM assessment output for '{subtopic_name}' might be missing critical script, postMessage call, or subtopicId embedding.")
                 # Return potentially non-functional HTML, frontend needs to handle this possibility
                 logger.info("Returning potentially non-interactive assessment HTML from LLM.")

        except Exception as llm_err:
            logger.error(f"Error during Gemini HTML assessment generation for '{subtopic_name}': {llm_err}", exc_info=True)
            return get_llm_error_response("AI assistant communication failed for assessment generation.", 502)

        return JsonResponse({'html': html_content}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON request body."}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in generate_subtopic_assessment: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def generate_review_questions(request):
    """API endpoint to generate review questions based on subtopic names."""
    if not model:
        return get_llm_error_response("AI Model not configured.", 503)

    try:
        data = json.loads(request.body.decode('utf-8'))
        # Expecting a list of subtopic names that have been completed or are relevant
        subtopic_names = data.get('subtopicNames')

        if not isinstance(subtopic_names, list) or not subtopic_names:
            return JsonResponse({"error": "Missing or invalid 'subtopicNames' list in request body."}, status=400)

        # Filter out any non-string or empty names
        valid_names = [name for name in subtopic_names if isinstance(name, str) and name.strip()]
        if not valid_names:
             return JsonResponse({"error": "'subtopicNames' list contains no valid names."}, status=400)


        prompt = create_review_prompt(valid_names)
        logger.debug(f"Generating review questions for topics: {valid_names}")

        try:
            # Request JSON output
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.65
            )
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                 logger.error(f"Review question generation blocked. Reason: {block_reason}.")
                 return get_llm_error_response(f"Review question generation blocked ({block_reason}).", 400)

            # Parse the JSON array of questions
            review_questions = json.loads(response.text)
            if not isinstance(review_questions, list):
                logger.error(f"LLM returned non-list for review questions: {response.text}")
                raise ValueError("Expected a JSON list of questions.")
            # Further validate if needed (e.g., check if elements are strings)
            review_questions = [q for q in review_questions if isinstance(q, str)]

        except json.JSONDecodeError:
             logger.error(f"Failed to decode JSON review questions from LLM: {response.text}", exc_info=True)
             return get_llm_error_response("AI returned invalid review question format.", 500)
        except ValueError as ve:
             logger.error(f"Validation error for review questions: {ve}. LLM Response: {response.text}", exc_info=True)
             return get_llm_error_response(f"AI returned invalid data: {ve}", 500)
        except Exception as llm_err:
             logger.error(f"Error during Gemini review question generation: {llm_err}", exc_info=True)
             return get_llm_error_response("AI assistant communication failed for review questions.", 502)

        # Return the list of questions
        return JsonResponse({'reviewQuestions': review_questions}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON request body."}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in generate_review_questions: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def generate_plan_summary(request):
    """API endpoint to generate a brief summary for the study plan."""
    if not model:
        return get_llm_error_response("AI Model not configured.", 503)

    try:
        data = json.loads(request.body.decode('utf-8'))
        main_topic = data.get('mainTopic', '').strip()
        # Expecting subtopics list (like from structure generation) to extract names and time
        subtopics = data.get('subtopics')
        total_time = data.get('totalEstimatedTime') # Allow passing calculated time directly

        if not main_topic:
            return JsonResponse({"error": "Missing 'mainTopic'."}, status=400)
        if not isinstance(subtopics, list):
             return JsonResponse({"error": "Missing or invalid 'subtopics' list."}, status=400)

        subtopic_names = [st.get('name', 'Unnamed Topic') for st in subtopics if isinstance(st, dict)]
        valid_names = [name for name in subtopic_names if isinstance(name, str) and name.strip()]

        # Calculate total time if not provided directly
        if total_time is None:
             try:
                 total_time = sum(st.get('time', 0) for st in subtopics if isinstance(st, dict))
             except TypeError:
                 logger.warning("Could not calculate total time from subtopics for summary.")
                 total_time = 0 # Fallback
        elif not isinstance(total_time, int):
             logger.warning("Invalid 'totalEstimatedTime' provided, defaulting to 0.")
             total_time = 0


        if not valid_names:
            # Generate a generic summary if no valid subtopic names
            summary_text = f"This study plan focuses on '{main_topic}'. Dive into the modules to explore the key concepts!"
            logger.info("Generating generic summary as no valid subtopic names were provided.")
            return JsonResponse({'planSummary': summary_text}, status=200)

        prompt = create_summary_prompt(main_topic, valid_names, total_time)
        logger.debug(f"Generating plan summary for: {main_topic}")

        try:
            generation_config = genai.types.GenerationConfig(temperature=0.6)
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                 logger.error(f"Plan summary generation blocked. Reason: {block_reason}.")
                 return get_llm_error_response(f"Plan summary generation blocked ({block_reason}).", 400)

            summary_text = response.text.strip()

            if not summary_text:
                logger.warning(f"LLM returned empty summary for '{main_topic}'.")
                # Provide a fallback summary
                summary_text = f"This study plan will guide you through key concepts related to '{main_topic}'. Check the outline for details."

        except Exception as llm_err:
            logger.error(f"Error during Gemini plan summary generation for '{main_topic}': {llm_err}", exc_info=True)
            return get_llm_error_response("AI assistant communication failed for summary generation.", 502)

        return JsonResponse({'planSummary': summary_text}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON request body."}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in generate_plan_summary: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)