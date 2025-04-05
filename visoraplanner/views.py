# -*- coding: utf-8 -*-
import logging
import json
import os
import uuid
from collections import defaultdict, deque 

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods 
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

import google.generativeai as genai
logger = logging.getLogger(__name__)

# --- Configuration ---
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logger.error("CRITICAL: GEMINI_API_KEY environment variable not set.")
        model = None
    else:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(
            "gemini-2.0-flash",
             system_instruction="You are a world-renowned expert AI specializing in instructional design and the creation of highly detailed, engaging, and pedagogically sound educational content and interactive learning materials. Adapt your explanations and assessments precisely to the specified difficulty level.",
        )
        logger.info("Gemini model 'gemini-2.0-flash' configured successfully.")
except Exception as e:
    logger.error(f"CRITICAL: Failed to configure Gemini model: {e}", exc_info=True)
    model = None 

# --- Enhanced Constants ---
MIN_DURATION_HOURS = 0.5
MAX_DURATION_HOURS = 200 
VALID_DIFFICULTIES = ['Beginner', 'Intermediate', 'Advanced']
MAX_TOPIC_LENGTH = 200 
DEFAULT_SUBTOPIC_TIME_MINS = 20 
MIN_SUBTOPICS_SHORT = 5
MAX_SUBTOPICS_SHORT = 10
MIN_SUBTOPICS_MEDIUM = 8
MAX_SUBTOPICS_MEDIUM = 18
MIN_SUBTOPICS_LONG = 15
MAX_SUBTOPICS_LONG = 30

ASSESSMENT_QUESTIONS_BEGINNER = 4
ASSESSMENT_QUESTIONS_INTERMEDIATE = 6
ASSESSMENT_QUESTIONS_ADVANCED = 8

# --- Helper Functions ---
def get_llm_error_response(message, status_code=500, details=None):
    """Standardizes LLM error responses, optionally including details."""
    log_message = message
    if details:
        log_message += f" | Details: {details}"
    logger.error(log_message)
    response_data = {"error": message}
    if details and status_code == 500:
         response_data["details"] = details 
    return JsonResponse(response_data, status=status_code)

def detect_cycles(subtopics_map, processed_subtopics):
    """
    Detects cycles in the prerequisite graph using Kahn's algorithm (topological sort).
    Returns a set of node IDs involved in cycles if any are found.
    """
    in_degree = {st['id']: 0 for st in processed_subtopics}
    adj = defaultdict(list)
    node_ids = set(in_degree.keys())

    for st in processed_subtopics:
        st_id = st['id']
        for prereq_id in st.get('prerequisiteIds', []):
            if prereq_id in node_ids: 
                adj[prereq_id].append(st_id)
                in_degree[st_id] += 1

    queue = deque([node_id for node_id in node_ids if in_degree[node_id] == 0])
    count = 0
    while queue:
        u = queue.popleft()
        count += 1
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if count == len(node_ids):
        return set()
    else:
        # Nodes with in_degree > 0 at the end are part of cycles or depend on cycles
        cycle_nodes = {node_id for node_id in node_ids if in_degree[node_id] > 0}
        # This is an approximation; pinpointing exact cycles is more complex
        logger.warning(f"Cycle detected or nodes unreachable. Suspected nodes: {cycle_nodes}")
        return cycle_nodes


def create_structure_prompt(topic: str, duration_hours: float, difficulty: str, prerequisites: str, category: str,subCategory: str,categoryTopic: str) -> str:
    """Creates the enhanced prompt for the LLM to generate the course structure JSON."""
    total_minutes = int(duration_hours * 60)
    prereq_info = f'Assumed Prerequisites: "{prerequisites}"\n' if prerequisites else ""

    # Determine target subtopic range based on duration
    if duration_hours < 8:
        min_sub, max_sub = MIN_SUBTOPICS_SHORT, MAX_SUBTOPICS_SHORT
    elif duration_hours < 30:
        min_sub, max_sub = MIN_SUBTOPICS_MEDIUM, MAX_SUBTOPICS_MEDIUM
    else:
        min_sub, max_sub = MIN_SUBTOPICS_LONG, MAX_SUBTOPICS_LONG

    # Enhanced prompt
    prompt = f"""
    You are a world-renowned expert curriculum architect AI. Generate a comprehensive, highly detailed, and pedagogically sound course structure JSON object for the following request:

    Course Topic: "{topic}"
    {prereq_info}Requested Duration: {duration_hours} hours ({total_minutes} minutes approx.)
    Target Difficulty: {difficulty}
    Target Education level: {category}
    Target Grade/stream level: {subCategory}
    Target Subject : {categoryTopic}

    Output MUST be a single, valid JSON object adhering STRICTLY to this format:
    {{
      "subtopics": [
        {{
          "id": "temp_id_1", // TEMPORARY ID, sequential like temp_id_N
          "name": "Module Type: Descriptive Name - Specific Concept/Skill", // e.g., "Introduction: Core Concepts - Variables and Data Types", "Application: Building a Component - User Input Handling"
          "time": <integer>, // Estimated time in MINUTES (min {DEFAULT_SUBTOPIC_TIME_MINS}). Realistic allocation.
          "difficultyValue": <float>, // 0.0 (very easy) to 1.0 (very hard), nuanced reflection of '{difficulty}' target and progression.
          "conceptDensity": <float>, // 0.0 (intro/sparse) to 1.0 (dense/complex). How much new info per minute.
          "prerequisiteIds": ["temp_id_X", ...] // List temporary IDs of DIRECT prerequisites FROM THIS LIST ONLY. Ensure a logical flow. Empty for foundational topics. NO CYCLES ALLOWED.
        }}
        // ... generate {min_sub}-{max_sub} detailed subtopic objects ...
      ],
      "analysis": {{
        "difficultyCurve": [<float>, ...], // difficultyValue for each subtopic IN ORDER. Should show progression.
        "densityCurve": [<float>, ...], // conceptDensity for each subtopic IN ORDER.
        "estimatedTotalTime": <integer> // SUM of all "time" values. MUST be close to {total_minutes} mins (+/- 10% is acceptable).
      }}
    }}

    CRITICAL Guidelines:
    1.  **Content Depth:** Create logical, highly descriptive module names. Include a *type* (e.g., Introduction, Core Concept, Deep Dive, Technique, Application, Case Study, Project, Tooling, Best Practices) and specify the key concept/skill covered. Cover the topic comprehensively for the given duration and difficulty.
    2.  **Pedagogy:** Structure modules for effective learning progression. Foundational topics first, building complexity. Mix theory with application where appropriate.
    3.  **Time Allocation:** Distribute {total_minutes} mins realistically across modules. Min time per module: {DEFAULT_SUBTOPIC_TIME_MINS}. `analysis.estimatedTotalTime` MUST equal the sum of module times. Allocate more time to complex or application-focused modules.
    4.  **Prerequisites:** Use only `temp_id_N` from this generated list. Define clear dependencies creating a valid Directed Acyclic Graph (DAG). Initial modules may have empty lists.
    5.  **Nuanced Values:** Assign `difficultyValue` and `conceptDensity` thoughtfully, reflecting the content, the overall `{difficulty}` level, and progression through the course. Avoid just using 0.5.
    6.  **JSON Only:** Output ONLY the JSON object. No explanations, apologies, summaries, markdown ```json blocks, or any other text outside the single JSON structure. Ensure keys and values match the specification exactly (types, names).
    """
    return prompt


def post_process_structure(llm_output: dict, requested_duration_hours: float) -> dict:
    """Validates, cleans, assigns UUIDs, adjusts time, detects cycles, creates graph."""
    if not isinstance(llm_output, dict) or "subtopics" not in llm_output or "analysis" not in llm_output:
        raise ValueError("LLM output is not a valid dictionary or missing required keys ('subtopics', 'analysis').")

    subtopics = llm_output.get("subtopics", [])
    if not isinstance(subtopics, list): 
         raise ValueError("'subtopics' must be a list.")
    if not subtopics:
         raise ValueError("'subtopics' list is empty.")


    # --- 1. ID Replacement & Basic Validation ---
    id_map = {}
    processed_subtopics = []
    temp_ids_found = set()
    subtopics_map = {} 

    for i, st in enumerate(subtopics):
        if not isinstance(st, dict):
             logger.warning(f"Skipping subtopic at index {i}: Not a dictionary. Value: {st}")
             continue
        required_keys = ["id", "name", "time", "difficultyValue", "conceptDensity", "prerequisiteIds"]
        if not all(k in st for k in required_keys):
            missing_keys = [k for k in required_keys if k not in st]
            logger.warning(f"Skipping subtopic at index {i}: Missing keys {missing_keys}. Data: {st}")
            continue
        # Validate types
        if not isinstance(st.get("name"), str) or not st["name"].strip():
             logger.warning(f"Skipping subtopic at index {i}: Invalid or empty name.")
             continue
        st["name"] = st["name"].strip()

        if not isinstance(st.get("time"), int) or st["time"] <= 0:
             st["time"] = DEFAULT_SUBTOPIC_TIME_MINS
             logger.warning(f"Adjusted subtopic '{st['name']}' time to default minimum {DEFAULT_SUBTOPIC_TIME_MINS} mins due to invalid value ({st.get('time')}).")
        elif st["time"] < DEFAULT_SUBTOPIC_TIME_MINS:
             st["time"] = DEFAULT_SUBTOPIC_TIME_MINS
             logger.warning(f"Adjusted subtopic '{st['name']}' time to minimum {DEFAULT_SUBTOPIC_TIME_MINS} mins.")

        # Clamp float values
        st["difficultyValue"] = max(0.0, min(1.0, float(st.get("difficultyValue", 0.5))))
        st["conceptDensity"] = max(0.0, min(1.0, float(st.get("conceptDensity", 0.5))))
        if not isinstance(st.get("difficultyValue"), (int, float)): 
            logger.warning(f"Invalid difficultyValue for '{st['name']}', using 0.5.")
            st["difficultyValue"] = 0.5
        if not isinstance(st.get("conceptDensity"), (int, float)):
            logger.warning(f"Invalid conceptDensity for '{st['name']}', using 0.5.")
            st["conceptDensity"] = 0.5


        if not isinstance(st.get("prerequisiteIds"), list):
             st["prerequisiteIds"] = []
             logger.warning(f"Corrected prerequisiteIds to empty list for subtopic '{st['name']}'.")
        else:
             # Ensure all prereq IDs are strings
             st["prerequisiteIds"] = [str(pid) for pid in st["prerequisiteIds"] if isinstance(pid, (str, int))]

        temp_id = st.get("id")
        if not isinstance(temp_id, str) or not temp_id.startswith("temp_id_"):
             logger.warning(f"Subtopic '{st['name']}' has invalid temporary ID '{temp_id}'. Assigning fallback.")
             temp_id = f"temp_id_fallback_{uuid.uuid4()}"

        if temp_id in id_map:
             logger.warning(f"Duplicate temporary ID '{temp_id}' found for subtopic '{st['name']}'. Skipping duplicate entry.")
             continue

        new_id = str(uuid.uuid4())
        id_map[temp_id] = new_id
        st["id"] = new_id 
        temp_ids_found.add(temp_id)
        subtopics_map[new_id] = st 
        processed_subtopics.append(st)

    if not processed_subtopics:
         raise ValueError("LLM output contained no processable subtopics after validation.")


    # --- 2. Update prerequisite IDs & Detect Cycles ---
    all_final_ids = {st["id"] for st in processed_subtopics}
    for st in processed_subtopics:
        valid_prereqs = []
        raw_prereqs = st.get("prerequisiteIds", [])
        for temp_prereq_id in raw_prereqs:
            final_prereq_id = id_map.get(temp_prereq_id)
            if final_prereq_id:
                if final_prereq_id == st["id"]:
                     logger.warning(f"Removed self-referencing prerequisite for topic '{st['name']}' (ID: {st['id']})")
                elif final_prereq_id not in all_final_ids:
                     logger.warning(f"Prerequisite ID '{final_prereq_id}' (from temp '{temp_prereq_id}') for '{st['name']}' refers to a subtopic that was filtered out. Ignoring.")
                else:
                    valid_prereqs.append(final_prereq_id)
            else:
                logger.warning(f"Prerequisite temporary ID '{temp_prereq_id}' listed for subtopic '{st['name']}' not found in the generated subtopics list. Ignoring.")
        st["prerequisiteIds"] = valid_prereqs

    # Cycle Detection
    nodes_in_cycles = detect_cycles(subtopics_map, processed_subtopics)
    if nodes_in_cycles:
        logger.warning(f"Attempting to break detected cycles involving nodes: {nodes_in_cycles}")
        for st in processed_subtopics:
            if st['id'] in nodes_in_cycles:
                original_prereqs = st['prerequisiteIds']
                st['prerequisiteIds'] = [pid for pid in original_prereqs if pid not in nodes_in_cycles]
                if len(st['prerequisiteIds']) < len(original_prereqs):
                    removed_count = len(original_prereqs) - len(st['prerequisiteIds'])
                    logger.info(f"Removed {removed_count} cycle-related prerequisite(s) for node '{st['name']}' ({st['id']})")


    # --- 3. Time Adjustment ---
    target_total_minutes = requested_duration_hours * 60
    current_total_minutes = sum(st["time"] for st in processed_subtopics)

    if current_total_minutes <= 0:
        logger.warning("Total calculated time is zero or negative. Skipping time adjustment.")
    elif abs(current_total_minutes - target_total_minutes) > max(15, target_total_minutes * 0.10):
        ratio = target_total_minutes / current_total_minutes
        logger.info(f"Adjusting total time from {current_total_minutes}m to target {target_total_minutes}m (ratio: {ratio:.3f})")
        accumulated_remainder = 0.0
        for st in processed_subtopics:
            new_time_float = st["time"] * ratio + accumulated_remainder
            new_time_int = max(DEFAULT_SUBTOPIC_TIME_MINS, round(new_time_float))
            accumulated_remainder = new_time_float - new_time_int
            st["time"] = new_time_int
    else:
         logger.info(f"Total time {current_total_minutes}m is close enough to target {target_total_minutes}m. No major adjustment needed.")

    final_total_time = sum(st["time"] for st in processed_subtopics)


    # --- 4. Create Graph Structure (Nodes and Edges) ---
    nodes = []
    edges = []
    node_width = 180
    default_position = {"x": 0, "y": 0} 

    # Enhanced color mapping based on difficulty
    def get_node_colors(diff_val):
         if diff_val > 0.75: return {'background': '#b71c1c', 'color': '#ffffff'} # Harder Red
         if diff_val > 0.55: return {'background': '#d32f2f', 'color': '#ffffff'} # Hard Reddish
         if diff_val < 0.25: return {'background': '#2e7d32', 'color': '#ffffff'} # Easier Green
         if diff_val < 0.45: return {'background': '#388e3c', 'color': '#ffffff'} # Easy Greenish
         return {'background': '#5823c8', 'color': '#ffffff'} 

    for st in processed_subtopics:
        label_parts = st["name"].split(":", 1)
        if len(label_parts) == 2:
            node_type_prefix = label_parts[0].strip()
            main_label = label_parts[1].strip()
            display_label = f"[{node_type_prefix}]\n{main_label}"
        else:
            display_label = st["name"] 

        colors = get_node_colors(st["difficultyValue"])

        nodes.append({
            "id": st["id"],
            "position": default_position,
            "data": {"label": display_label}, 
            "style": {
                "width": node_width,
                "fontSize": '0.75rem',
                "textAlign": 'center',
                "padding": '10px 12px',
                "borderRadius": '8px', 
                "background": colors['background'],
                "color": colors['color'],
                "border": f"1px solid {colors['background']}"
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
                    "type": 'smoothstep',
                    "animated": False,
                    "markerEnd": {"type": "arrowclosed", "width": 18, "height": 18, "color": '#777'}, 
                    "style": {"strokeWidth": 1.75, "stroke": '#777'}
                })
            else:
                 logger.error(f"Consistency Error: Prerequisite ID '{prereq_id}' for node '{st['id']}' not found in node list during edge creation. This might be due to cycle breaking or earlier filtering.")


    # --- 5. Final Analysis Object ---
    final_difficulty_curve = [st.get("difficultyValue", 0.5) for st in processed_subtopics]
    final_density_curve = [st.get("conceptDensity", 0.5) for st in processed_subtopics]

    analysis = {
        "difficultyCurve": final_difficulty_curve,
        "densityCurve": final_density_curve,
        "estimatedTotalTime": int(round(final_total_time)),
        "detectedCycles": list(nodes_in_cycles), 
    }

    logger.info(f"Structure post-processing complete. Found {len(processed_subtopics)} valid subtopics. Final estimated time: {final_total_time} mins. Detected cycle nodes: {len(nodes_in_cycles)}")

    return {
        "subtopics": processed_subtopics,
        "graph": {"nodes": nodes, "edges": edges},
        "analysis": analysis
    }


def create_content_prompt(main_topic: str, subtopic_name: str, difficulty: str,category: str,subCategory: str,categoryTopic: str) -> str:
    """Creates the enhanced prompt for generating detailed subtopic HTML content."""
    # Consistent theme instructions (can be reused)
    color_theme_instructions = """
    - **Styling:** Use a single `<style>` block within the snippet.
        - Body/Container: `margin: 15px; padding: 0; background-color: #212529; color: #ffffff; font-family: sans-serif; line-height: 1.6;`
        - use those colors background:#212529 and these for others #5823c8,#ffffff and dont use any other colors !!    
    - **Responsiveness:** Ensure content flows well. Use relative units where possible. Make `pre > code` blocks horizontally scrollable. Tables should be usable on smaller screens (consider responsive table techniques if complex).
    """

    prompt = f"""
    You are an expert educator and technical writer AI assistant. Generate a comprehensive, self-contained HTML snippet (NO `<html>`, `<head>`, or `<body>` tags) for the following learning subtopic, tailored precisely for the target audience.
    Main Course Topic: "{main_topic}"
    Target Difficulty: {difficulty}
    Current Subtopic: "{subtopic_name}"
    Target Education level: {category}
    Target Grade/stream level: {subCategory}
    Target Subject : {categoryTopic}

    Structure the HTML snippet with the following sections:
    1. Use all these {category}/{subCategory}/{categoryTopic}/{subtopic_name}/{difficulty}/{main_topic} to generate Comprehensive content

    Apply these styling requirements meticulously:
    {color_theme_instructions}

    Output ONLY the raw HTML snippet (including the necessary single `<style>` block). Do not include markdown markers (like ```html) or any introductory/closing text outside the HTML structure itself. Ensure the snippet is valid and ready to be embedded directly into an iframe's `srcdoc`.
    """
    return prompt


def create_assessment_prompt(subtopic_id: str, subtopic_name: str, difficulty: str, theory_context: str) -> str:
    """Creates the enhanced prompt for generating a more comprehensive interactive HTML assessment."""

    # Consistent theme instructions, adapted for forms
    color_theme_instructions = """
    - **Styling:** Use a single `<style>` block.
        - Body/Container: `margin: 15px; padding: 0; background-color: #212529; color: #ffffff; font-family: sans-serif; line-height: 1.6;`
        - use those colors background:#212529 and these for others #5823c8,#ffffff,#2b3035 and dont use any other colors !! 
    """

    prompt = f"""
    You are an expert assessment creator and web developer AI. Generate a self-contained, interactive HTML assessment snippet focused on the subtopic below.

    Target Difficulty: {difficulty}
    Subtopic: "{subtopic_name}"
    Subtopic ID: "{subtopic_id}" // CRITICAL: Embed this exact ID in the JS postMessage call.
    Contextual Info (Optional): {theory_context if theory_context else "None provided."}
    color theme instructions: {color_theme_instructions} use the provided colors only

    Generate an HTML snippet:
        - U can Use library cdn in html included 
        - Make interactive assessment using html css js and other libraries using cdns 
    Boundary:
        - Strictly maintain the difficulty level based on difficulty.
        - Ensure interactive elements (animations, simulations, interactive questions) match the exact depth of knowledge needed.
        - The response should contain:
          - A brief, clear explanation suited to {difficulty} and {subtopic_name}.
          - An interactive simulation, animation, or visual aid to illustrate the concept.
          - A assessment or question to reinforce learning.
        - The response must not exceed the knowledge expected at {difficulty} and {subtopic_name} levels.
    Requirements:
        - Use HTML with inline CSS/JS and libraries!
        - Include interactive elements
        - Accessible semantic markup
        - Its should be interactive and educational friendly
        - Do NOT include <html> or <head> tags and ```html and not even animation name details and others just only the thing requested!
        - use those colors background:#212529 and these for others #5823c8,#ffffff and dont use any other colors !!     
        - if any assessment is provided by you give their ans as well as explanation too.
        - assessment questions should be 5-12 based on difficulty level

    final Check:
        - Check all the things interactivity and functionality should work perfectly !!

    Output ONLY the raw HTML snippet (including comprehensive `<style>` and `<script>` and cdns before script tag). No markdown markers or other text. Ensure the snippet is functional and directly usable in an iframe `srcdoc`. Pay close attention to detail in the JS logic.
    """
    return prompt


def create_review_prompt(subtopic_names: list[str]) -> str:
    """Creates the enhanced prompt for generating insightful review questions."""
    if not subtopic_names:
        return ""

    topic_list = "\n".join([f"- {name}" for name in subtopic_names])
    # Slightly increased question count
    num_questions = min(max(4, len(subtopic_names) // 2 + 1), 8)

    prompt = f"""
    You are an expert AI educator specializing in fostering deep learning and knowledge synthesis.
    Based on the following completed subtopics:
    {topic_list}

    Generate a JSON array containing exactly {num_questions} insightful, thought-provoking review questions.

    CRITICAL Requirements:
    1.  **Focus:** Questions MUST encourage synthesis, critical thinking, comparison, application, or evaluation related to the provided topics. Avoid simple recall.
    2.  **Connections:** Actively create questions that bridge concepts *between* different subtopics listed above. Ask 'how', 'why', 'compare/contrast', 'what if'.
    3.  **Clarity:** Questions must be clear, unambiguous, and concise.
    4.  **Format:** Output ONLY a single, valid JSON array of strings, where each string is a distinct question.
        Example: `["How does Concept A from Module 1 relate to Technique B in Module 3?", "Considering Topic X and Y, what are the potential trade-offs when solving Z?", "Evaluate the effectiveness of Method P discussed in Module 2 for the scenario presented in Module 4."]`
    5.  **Strict JSON:** Do not include ```json markers, comments, or any text outside the JSON array.
    """
    return prompt


def create_summary_prompt(main_topic: str, subtopic_names: list[str], total_time_mins: int) -> str:
    """Creates the enhanced prompt for generating a more motivating plan summary."""
    if not subtopic_names:
        return ""

    # List more topics for context
    if len(subtopic_names) <= 6:
        topic_list = ", ".join(subtopic_names)
    else:
        topic_list = ", ".join(subtopic_names[:5]) + f", and {len(subtopic_names)-5} more"


    hours = total_time_mins // 60
    minutes = total_time_mins % 60
    time_str = f"{hours} hours" if minutes == 0 else (f"{minutes} minutes" if hours == 0 else f"{hours} hours and {minutes} minutes")
    if hours == 1: time_str = time_str.replace("hours", "hour")
    if minutes == 1: time_str = time_str.replace("minutes", "minute")


    prompt = f"""
    You are an AI assistant crafting encouraging and informative introductions for personalized study plans.

    Main Topic: "{main_topic}"
    Estimated Duration: Approximately {time_str} ({total_time_mins} minutes)
    Key Subtopics Include: {topic_list}.

    Generate a concise (3-5 sentences) and motivating summary for this study plan.
    Requirements:
    1.  Briefly state the primary learning objective or skill gained from completing this plan related to "{main_topic}".
    2.  Mention the estimated time commitment.
    3.  Hint at the progression from foundational concepts to more advanced applications (if applicable based on subtopic names).
    4.  Maintain an encouraging and supportive tone.
    5.  Output ONLY the summary text. No titles, greetings, or extra formatting.
    """
    return prompt


# --- API Views (with enhanced logging and error handling) ---

@api_view(['POST'])
@permission_classes([AllowAny]) # Change if auth needed
@csrf_exempt # Consider CSRF protection if using session auth
def generate_course_structure(request):
    """API endpoint to generate an advanced course structure using Gemini."""
    if not model:
        return get_llm_error_response("AI Model not configured. Service unavailable.", 503)

    try:
        # Decode request body safely
        try:
            request_body = request.body.decode('utf-8')
            data = json.loads(request_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to decode request body: {e}. Body snippet: {request.body[:100]}")
            return JsonResponse({"error": "Invalid request format. Expected valid JSON."}, status=400)

        topic = data.get('topic', '').strip()
        duration_hours_str = data.get('durationHours')
        difficulty = data.get('difficulty', '').strip()
        prerequisites = data.get('prerequisites', '').strip()
        category = data.get('category', '').strip()
        subCategory = data.get('subCategory', '').strip()
        categoryTopic = data.get('categoryTopic', '').strip()

        # --- Input Validation ---
        errors = {}
        if not topic: errors['topic'] = "Topic cannot be empty."
        if len(topic) > MAX_TOPIC_LENGTH: errors['topic'] = f"Topic too long (max {MAX_TOPIC_LENGTH} chars)."
        try:
            duration_hours = float(duration_hours_str)
            if not (MIN_DURATION_HOURS <= duration_hours <= MAX_DURATION_HOURS):
                 errors['durationHours'] = f"Duration must be between {MIN_DURATION_HOURS} and {MAX_DURATION_HOURS} hours."
        except (TypeError, ValueError, AttributeError):
             errors['durationHours'] = f"Invalid duration format. Provide a number between {MIN_DURATION_HOURS}-{MAX_DURATION_HOURS}."
        if difficulty not in VALID_DIFFICULTIES:
             errors['difficulty'] = f"Invalid difficulty. Choose from: {', '.join(VALID_DIFFICULTIES)}."

        if errors:
            logger.warning(f"Structure generation validation failed: {errors}")
            return JsonResponse({"error": "Validation failed", "details": errors}, status=400)

        # --- LLM Interaction ---
        prompt = create_structure_prompt(topic, duration_hours, difficulty, prerequisites,category,subCategory,categoryTopic)
        logger.info(f"Generating structure for topic: '{topic}', duration: {duration_hours}h, difficulty: {difficulty}")
        logger.debug(f"Structure Prompt (first 500 chars): {prompt[:500]}...")

        try:
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.65, 
            )
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates:
                feedback = response.prompt_feedback
                block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                safety_ratings_str = str(getattr(feedback, 'safety_ratings', 'N/A'))
                logger.error(f"Structure generation blocked. Reason: {block_reason}. Safety Ratings: {safety_ratings_str}. Prompt Hint: '{prompt[:100]}...'")
                user_error = f"Content generation failed due to safety constraints ({block_reason}). Please revise the topic/prerequisites."
                if block_reason == 'OTHER':
                     user_error = "Content generation failed (Reason: OTHER). Simplify request or try again later."
                return get_llm_error_response(user_error, 400, details=f"Block Reason: {block_reason}, Safety: {safety_ratings_str}")

            llm_raw_text = response.text
            llm_json_output = json.loads(llm_raw_text)

        except json.JSONDecodeError as json_err:
             logger.error(f"CRITICAL: Failed JSON decode despite mime type! Raw Text: '{llm_raw_text}'. Error: {json_err}", exc_info=True)
             return get_llm_error_response("AI returned invalid structure data format.", 500, details="JSONDecodeError")
        except Exception as llm_err:
             logger.error(f"Gemini API error during structure generation: {llm_err}", exc_info=True)
             return get_llm_error_response("AI assistant communication failed. Please try again later.", 502, details=str(llm_err))

        # --- Post-processing ---
        try:
            processed_data = post_process_structure(llm_json_output, duration_hours)
            # Final check after processing
            if not processed_data.get("subtopics") or not processed_data.get("graph", {}).get("nodes"):
                 logger.error("Post-processing removed all subtopics/nodes. Original LLM JSON: %s", llm_json_output)
                 return get_llm_error_response("AI generated structure was invalid or could not be processed. Try regenerating.", 500, details="Post-processing yielded empty result")

        except ValueError as val_err:
             logger.error(f"Structure Validation/Processing Error: {val_err}. Original LLM JSON: {json.dumps(llm_json_output)}", exc_info=True)
             # Give a slightly more specific error if possible
             return get_llm_error_response(f"AI data processing failed: {val_err}. Please try regenerating.", 500, details=str(val_err))
        except Exception as proc_err:
             logger.error(f"Unexpected error during structure post-processing: {proc_err}. Original LLM JSON: {json.dumps(llm_json_output)}", exc_info=True)
             return get_llm_error_response("Internal server error during data processing.", 500, details="Unexpected post-processing error")


        logger.info(f"Successfully generated and processed structure for topic: '{topic}'.")
        return JsonResponse(processed_data, status=200)

    except Exception as e:
        logger.error(f"Unexpected error in generate_course_structure view: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def generate_subtopic_content(request):
    """API endpoint to generate detailed HTML content for a subtopic."""
    if not model:
        return get_llm_error_response("AI Model not configured. Service unavailable.", 503)

    try:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"error": "Invalid JSON request body."}, status=400)

        subtopic_id = data.get('subtopicId')
        subtopic_name = data.get('subtopicName', '').strip()
        difficulty = data.get('difficulty', '').strip()
        main_topic = data.get('mainTopic', '').strip()
        category = data.get('category', '').strip()
        subCategory = data.get('subCategory', '').strip()
        categoryTopic = data.get('categoryTopic', '').strip()


        # --- Input Validation ---
        errors = {}
        if not subtopic_id: errors['subtopicId'] = "Required field."
        if not subtopic_name: errors['subtopicName'] = "Required field."
        if not main_topic: errors['mainTopic'] = "Required field."
        if difficulty not in VALID_DIFFICULTIES: errors['difficulty'] = f"Invalid. Choose from: {', '.join(VALID_DIFFICULTIES)}."

        if errors:
            return JsonResponse({"error": "Validation failed", "details": errors}, status=400)

        prompt = create_content_prompt(main_topic, subtopic_name, difficulty,category,subCategory,categoryTopic)
        logger.info(f"Generating HTML content for subtopic: '{subtopic_name}' (ID: {subtopic_id})")
        logger.debug(f"Content Prompt (first 500 chars): {prompt[:500]}...")


        try:
            generation_config = genai.types.GenerationConfig(
                temperature=0.7, 
            )
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                 safety_ratings_str = str(getattr(feedback, 'safety_ratings', 'N/A'))
                 logger.error(f"HTML content generation blocked for '{subtopic_name}'. Reason: {block_reason}. Safety: {safety_ratings_str}")
                 return get_llm_error_response(f"HTML Content generation blocked ({block_reason}). Revise content or contact support.", 400, details=f"Block Reason: {block_reason}")

            html_content = response.text.strip()

            # Basic HTML structure validation
            if not html_content or not (html_content.startswith(('<div', '<style', '<h2')) and html_content.endswith('</div>')):
                 logger.warning(f"LLM output for '{subtopic_name}' content doesn't look like expected HTML structure: {html_content[:150]}...{html_content[-150:]}")
                 # return get_llm_error_response("AI generated invalid HTML content structure.", 500, details="HTML structure check failed")
                 logger.info("Proceeding with potentially incomplete/invalid HTML from LLM.")
            else:
                logger.info(f"Successfully generated HTML content for '{subtopic_name}'. Length: {len(html_content)} bytes.")

        except Exception as llm_err:
            logger.error(f"Gemini API error during HTML content generation for '{subtopic_name}': {llm_err}", exc_info=True)
            return get_llm_error_response("AI assistant communication failed for content generation.", 502, details=str(llm_err))
        
        cleaned_html_content = html_content.replace("```html", "").replace("```", "").strip()
        return JsonResponse({'html': cleaned_html_content}, status=200)

    except Exception as e:
        logger.error(f"Unexpected error in generate_subtopic_content: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def generate_subtopic_assessment(request):
    """API endpoint to generate a comprehensive, interactive HTML assessment."""
    if not model:
        return get_llm_error_response("AI Model not configured. Service unavailable.", 503)

    try:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"error": "Invalid JSON request body."}, status=400)

        subtopic_id = data.get('subtopicId')
        subtopic_name = data.get('subtopicName', '').strip()
        difficulty = data.get('difficulty', '').strip()
        theory_context = data.get('theoryContext', '').strip()
        

        # --- Input Validation ---
        errors = {}
        if not subtopic_id: errors['subtopicId'] = "Required field."
        if not subtopic_name: errors['subtopicName'] = "Required field."
        if difficulty not in VALID_DIFFICULTIES: errors['difficulty'] = f"Invalid. Choose from: {', '.join(VALID_DIFFICULTIES)}."

        if errors:
            return JsonResponse({"error": "Validation failed", "details": errors}, status=400)

        prompt = create_assessment_prompt(subtopic_id, subtopic_name, difficulty, theory_context)
        logger.info(f"Generating HTML assessment for: {subtopic_name} (ID: {subtopic_id}, Difficulty: {difficulty})")
        logger.debug(f"Assessment Prompt (first 500 chars): {prompt[:500]}...")

        try:
            # Higher temp for more varied questions/approaches
            generation_config = genai.types.GenerationConfig(temperature=0.7)
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                 safety_ratings_str = str(getattr(feedback, 'safety_ratings', 'N/A'))
                 logger.error(f"HTML assessment generation blocked for '{subtopic_name}'. Reason: {block_reason}. Safety: {safety_ratings_str}")
                 return get_llm_error_response(f"HTML Assessment generation blocked ({block_reason}).", 400, details=f"Block Reason: {block_reason}")

            html_content = response.text.strip()

        except Exception as llm_err:
            logger.error(f"Gemini API error during HTML assessment generation for '{subtopic_name}': {llm_err}", exc_info=True)
            return get_llm_error_response("AI assistant communication failed for assessment generation.", 502, details=str(llm_err))

        cleaned_html_content = html_content.replace("```html", "").replace("```", "").strip()
        return JsonResponse({'html': cleaned_html_content}, status=200)

    except Exception as e:
        logger.error(f"Unexpected error in generate_subtopic_assessment: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def generate_review_questions(request):
    """API endpoint to generate insightful review questions based on subtopic names."""
    if not model:
        return get_llm_error_response("AI Model not configured. Service unavailable.", 503)

    try:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"error": "Invalid JSON request body."}, status=400)

        subtopic_names = data.get('subtopicNames')

        if not isinstance(subtopic_names, list):
            return JsonResponse({"error": "Invalid request: 'subtopicNames' must be a list."}, status=400)

        # Filter and validate names
        valid_names = [str(name).strip() for name in subtopic_names if isinstance(name, (str, int, float)) and str(name).strip()]
        if not valid_names:
             return JsonResponse({"error": "'subtopicNames' list contains no valid, non-empty names."}, status=400)
        if len(valid_names) > 50: # Add a limit to prevent excessively large prompts
             return JsonResponse({"error": "Too many subtopic names provided (limit 50)."}, status=400)


        prompt = create_review_prompt(valid_names)
        logger.info(f"Generating review questions for {len(valid_names)} topics: {', '.join(valid_names[:5])}...")
        logger.debug(f"Review Prompt (first 500 chars): {prompt[:500]}...")


        try:
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.7 # Slightly higher temp for creative questions
            )
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                 safety_ratings_str = str(getattr(feedback, 'safety_ratings', 'N/A'))
                 logger.error(f"Review question generation blocked. Reason: {block_reason}. Safety: {safety_ratings_str}")
                 return get_llm_error_response(f"Review question generation blocked ({block_reason}).", 400, details=f"Block Reason: {block_reason}")

            llm_raw_text = response.text
            review_questions = json.loads(llm_raw_text)

            # Validate the output structure
            if not isinstance(review_questions, list) or not all(isinstance(q, str) for q in review_questions):
                logger.error(f"LLM returned invalid format for review questions (expected list of strings): {llm_raw_text}")
                raise ValueError("AI response was not a valid JSON list of strings.")

            # Optional: Filter empty strings just in case
            review_questions = [q for q in review_questions if q.strip()]

            if not review_questions:
                 logger.warning(f"LLM returned an empty list of review questions. Raw response: {llm_raw_text}")
                 # Return empty list or an error? Let's return empty list for now.

            logger.info(f"Successfully generated {len(review_questions)} review questions.")

        except json.JSONDecodeError:
             logger.error(f"Failed to decode JSON review questions from LLM: {llm_raw_text}", exc_info=True)
             return get_llm_error_response("AI returned invalid review question data format.", 500, details="JSONDecodeError")
        except ValueError as ve:
             logger.error(f"Validation error for review questions: {ve}. LLM Response: {llm_raw_text}", exc_info=True)
             return get_llm_error_response(f"AI returned invalid data structure: {ve}", 500, details=str(ve))
        except Exception as llm_err:
             logger.error(f"Gemini API error during review question generation: {llm_err}", exc_info=True)
             return get_llm_error_response("AI assistant communication failed for review questions.", 502, details=str(llm_err))

        return JsonResponse({'reviewQuestions': review_questions}, status=200)

    except Exception as e:
        logger.error(f"Unexpected error in generate_review_questions: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def generate_plan_summary(request):
    """API endpoint to generate an enhanced summary for the study plan."""
    if not model:
        return get_llm_error_response("AI Model not configured. Service unavailable.", 503)

    try:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"error": "Invalid JSON request body."}, status=400)

        main_topic = data.get('mainTopic', '').strip()
        subtopics = data.get('subtopics') # Expecting list of dicts from structure
        # Allow analysis object containing time, or direct time
        analysis = data.get('analysis')
        total_time = data.get('totalEstimatedTime') # Direct override

        # --- Input Validation ---
        errors = {}
        if not main_topic: errors['mainTopic'] = "Required field."
        if not isinstance(subtopics, list) and total_time is None and not isinstance(analysis, dict):
             errors['subtopics/time'] = "Requires 'subtopics' list, 'analysis' object, or 'totalEstimatedTime' number."
        if total_time is not None and not isinstance(total_time, (int, float)):
             errors['totalEstimatedTime'] = "Must be a number (minutes)."
        if analysis is not None and not isinstance(analysis, dict):
             errors['analysis'] = "Must be an object."
        if subtopics is not None and not isinstance(subtopics, list):
             errors['subtopics'] = "Must be a list."


        if errors:
            return JsonResponse({"error": "Validation failed", "details": errors}, status=400)

        # Extract names and calculate time carefully
        valid_names = []
        calculated_time = 0
        if isinstance(subtopics, list):
             valid_names = [str(st.get('name', '')).strip() for st in subtopics if isinstance(st, dict) and str(st.get('name', '')).strip()]
             try:
                 # Ensure time values are valid numbers before summing
                 calculated_time = sum(int(st.get('time', 0)) for st in subtopics if isinstance(st, dict) and isinstance(st.get('time'), (int, float)) and st.get('time', 0) > 0)
             except (TypeError, ValueError):
                 logger.warning("Could not accurately calculate total time from subtopics for summary due to invalid time values.")
                 calculated_time = 0 # Fallback

        # Determine final time: direct > analysis > calculated
        if total_time is not None:
            final_total_time_mins = int(total_time)
        elif isinstance(analysis, dict) and isinstance(analysis.get('estimatedTotalTime'), int):
            final_total_time_mins = analysis['estimatedTotalTime']
        else:
            final_total_time_mins = calculated_time

        if final_total_time_mins <= 0:
             logger.warning(f"Calculated or provided total time ({final_total_time_mins} mins) is invalid for summary generation for '{main_topic}'. Using placeholder.")
             # Generate a generic summary if time is missing/invalid
             summary_text = f"This study plan offers a structured approach to learning '{main_topic}'. Explore the modules to understand the key concepts involved."
             return JsonResponse({'planSummary': summary_text}, status=200)


        if not valid_names:
            # Generate a generic summary if no valid subtopic names, but include time if available
            logger.info(f"Generating generic summary for '{main_topic}' as no valid subtopic names were provided.")
            time_str_generic = f" in the estimated time" if final_total_time_mins <=0 else f" over approximately {create_summary_prompt('', [], final_total_time_mins).split('Approximately ')[1].split(' (')[0]}" # Hacky way to get time string
            summary_text = f"This study plan provides a focused path to understand '{main_topic}'{time_str_generic}. Dive into the details within the course structure."
            return JsonResponse({'planSummary': summary_text}, status=200)

        prompt = create_summary_prompt(main_topic, valid_names, final_total_time_mins)
        logger.info(f"Generating plan summary for: '{main_topic}' (Est. {final_total_time_mins} mins)")
        logger.debug(f"Summary Prompt: {prompt}")


        try:
            generation_config = genai.types.GenerationConfig(temperature=0.65) # Balance info and motivation
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates:
                 feedback = response.prompt_feedback
                 block_reason = feedback.block_reason.name if feedback.block_reason else "Unknown"
                 safety_ratings_str = str(getattr(feedback, 'safety_ratings', 'N/A'))
                 logger.error(f"Plan summary generation blocked for '{main_topic}'. Reason: {block_reason}. Safety: {safety_ratings_str}")
                 return get_llm_error_response(f"Plan summary generation blocked ({block_reason}).", 400, details=f"Block Reason: {block_reason}")

            summary_text = response.text.strip()

            if not summary_text:
                logger.warning(f"LLM returned empty summary for '{main_topic}'. Providing fallback.")
                # Provide a more informative fallback using calculated data
                time_str_fallback = f" over approximately {create_summary_prompt('', [], final_total_time_mins).split('Approximately ')[1].split(' (')[0]}"
                summary_text = f"Ready to master '{main_topic}'? This structured plan will guide you through key areas like {valid_names[0]} and more{time_str_fallback}. Let's get started!"

            logger.info(f"Successfully generated plan summary for '{main_topic}'.")

        except Exception as llm_err:
            logger.error(f"Gemini API error during plan summary generation for '{main_topic}': {llm_err}", exc_info=True)
            return get_llm_error_response("AI assistant communication failed for summary generation.", 502, details=str(llm_err))

        return JsonResponse({'planSummary': summary_text}, status=200)

    except Exception as e:
        logger.error(f"Unexpected error in generate_plan_summary: {e}", exc_info=True)
        return JsonResponse({"error": "An unexpected server error occurred."}, status=500)