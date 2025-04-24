import logging
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny # Changed from IsAuthenticated
from rest_framework import viewsets, status
from rest_framework.response import Response
import google.generativeai as genai
import json
import os
from django.core.exceptions import ValidationError, ObjectDoesNotExist, ImproperlyConfigured
from django.db import IntegrityError

from .models import UserProject
from .serializers import UserProjectSerializer, UserProjectListSerializer


logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
model = None

if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set! AI features will be disabled.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        logger.info(f"Gemini AI Model '{model._model_name}' configured successfully.")
    except Exception as e:
        logger.error(f"Failed to configure or initialize Gemini Model: {e}", exc_info=True)
        model = None

def generate_ai_response(prompt, expected_format="text"):
    if not model:
         raise Exception("AI Model not initialized or configuration failed.")
    try:
        logger.debug(f"Sending prompt to AI (first 500 chars):\n{prompt[:500]}...")
        response = model.generate_content(prompt)

        if not response.candidates or not response.parts:
             logger.warning(f"AI response has no candidates or parts. Response: {response}")
             raise Exception("AI returned no content.")

        response_text = "".join(part.text for part in response.parts).strip()

        if not response_text:
             logger.warning(f"AI response parts contain no text. Response: {response}")
             raise Exception("AI returned empty text content.")

        logger.debug(f"Received AI response (raw text, first 500 chars):\n{response_text[:500]}...")

        json_start = response_text.find('{')
        json_end = response_text.rfind('}')

        if json_start != -1 and json_end != -1 and json_end > json_start:
            json_string = response_text[json_start : json_end + 1]
            logger.debug(f"Extracted potential JSON string: {json_string}")
            try:
                parsed_json = json.loads(json_string)
                return parsed_json
            except json.JSONDecodeError as json_e:
                logger.error(f"Failed to parse potential AI JSON response: {json_e}. Raw text fragment: {json_string}")
                if expected_format == "json":
                     return {"error": f"AI response contained invalid JSON: {json_e}"}

        logger.debug("No valid JSON found or text format acceptable, returning cleaned text.")
        cleaned_text = response_text.replace("```json", "").replace("```html", "").replace("```css", "").replace("```javascript", "").replace("```", "").strip()
        return cleaned_text

    except Exception as e:
        logger.error(f"Error during AI content generation or processing: {str(e)}", exc_info=True)
        raise Exception(f"AI interaction failed: {str(e)}")


class UserProjectViewSet(viewsets.ModelViewSet):
    serializer_class = UserProjectSerializer
    permission_classes = [AllowAny] # Allow access without authentication

    def get_queryset(self):
        # Return all projects since authentication is skipped
        return UserProject.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return UserProjectListSerializer
        return UserProjectSerializer

    # perform_create and user association removed as auth is skipped

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
             return Response({"name": ["A project with this name already exists."]}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
             return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error creating project: {e}", exc_info=True)
            return Response( {"detail": "An server error occurred while creating the project."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR )

    def update(self, request, *args, **kwargs):
         try:
             return super().update(request, *args, **kwargs)
         except IntegrityError:
             return Response( {"name": ["Another project with this name already exists."]}, status=status.HTTP_400_BAD_REQUEST )
         except Exception as e:
            logger.error(f"Unexpected error updating project {kwargs.get('pk')}: {e}", exc_info=True)
            return Response( {"detail": "An server error occurred while updating the project."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR )


@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot_developer_generate(request):
    try:
        data = request.data
        user_message = data.get('message', '').strip()
        context_data = data.get('context', {})
        is_semantic_animation_request = data.get('is_animation_request', False)

        if not isinstance(context_data, dict): return Response({"error": "Invalid context format."}, status=status.HTTP_400_BAD_REQUEST)
        if not user_message: return Response({"error": "Message cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)
        if len(user_message) > 4000: return Response({"error": "Message too long (max 4000)"}, status=status.HTTP_400_BAD_REQUEST)

        html_context = str(context_data.get('html', ''))[:6000]
        css_context = str(context_data.get('css', ''))[:6000]
        js_context = str(context_data.get('js', ''))[:6000]

        base_prompt = f"""
        You are an expert web developer assistant specializing in HTML, CSS, and JS for interactive web experiences and animations.
        Analyze the user's request considering the provided code context.

        Current Code Context (Truncated if >6000 chars):
        HTML: ```html\n{html_context}\n```
        CSS: ```css\n{css_context}\n```
        JS: ```javascript\n{js_context}\n```

        User Request: "{user_message}"
        """

        if is_semantic_animation_request:
            task_prompt = f"""
        Task (Semantic Animation - SAA): Generate HTML, CSS, JS for an animation based on the user's request, focusing on feeling and principles.
        - Prioritize smooth, performant CSS transforms & opacity. Use appropriate easing functions (e.g., 'ease-in-out', 'cubic-bezier(...)', 'steps(...)') matching the described feel ('playful', 'smooth', 'snappy').
        - Use JS (`requestAnimationFrame` or libraries if clearly implied) for complex sequences or interactions.
        - Provide a concise explanation in the 'explanation' field detailing *why* specific timing, easing, or properties were chosen to achieve the desired semantic effect.

        Output Format: Respond ONLY with a single, valid JSON object string: {{ "html6569201": "...", "css6569201": "...", "js6569201": "...", "explanation": "..." }}. NO other text before or after. Code strings must be valid. Provide the animation-focused explanation. If the request is unclear, return empty code strings and an explanation stating so.
            """
        else:
            task_prompt = f"""
        Task (Standard Code Generation): Generate or modify HTML, CSS, and JavaScript according to the request and context.

        Output Format: Respond ONLY with a single, valid JSON object string: {{ "html6569201": "...", "css6569201": "...", "js6569201": "...", "explanation": "..." }}. NO other text. Code strings must be valid. Briefly explain the generated code's function. Return empty code strings and explanation if request is unclear.

        Guidelines: HTML: Only needed elements/modifications. CSS: Only relevant rules. JS: Only relevant code. Use modern JS (ES6+).
            """

        full_prompt = base_prompt + task_prompt
        ai_result = generate_ai_response(full_prompt, expected_format="json")

        if not isinstance(ai_result, dict):
             logger.error(f"AI response for generation was not a dict. Type: {type(ai_result)}, Value: {ai_result}")
             ai_result = {"error": "AI response was not in the expected format."}

        if "error" in ai_result or all(k in ai_result for k in ["html6569201", "css6569201", "js6569201", "explanation"]):
            response_data = {
                "html6569201": str(ai_result.get("html6569201", "")),
                "css6569201": str(ai_result.get("css6569201", "")),
                "js6569201": str(ai_result.get("js6569201", "")),
                "explanation": str(ai_result.get("explanation", "No explanation provided.")),
                "error": ai_result.get("error")
            }
            return Response(response_data, status=status.HTTP_200_OK)
        else:
             logger.error(f"AI response dict for generation missing required keys. Received: {ai_result}")
             return Response({
                 "html6569201": "", "css6569201": "", "js6569201": "",
                 "explanation": "Error: Assistant response structure was invalid.",
                 "error": "Invalid AI response structure"
             }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Developer AI error in generate: {str(e)}", exc_info=True)
        error_message = f"Assistant error: {str(e)}" if settings.DEBUG else "Assistant is currently unavailable."
        return Response({"error": error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot_developer_explain(request):
    try:
        data = request.data
        selected_code = data.get('selected_code', '').strip()
        language = data.get('language', 'unknown').strip().lower()
        context_data = data.get('context', {})

        if not selected_code: return Response({"error": "No code selected"}, status=status.HTTP_400_BAD_REQUEST)
        if len(selected_code) > 4000: return Response({"error": "Selection too long (max 4000)"}, status=status.HTTP_400_BAD_REQUEST)

        html_context = str(context_data.get('html', ''))[:5000]
        css_context = str(context_data.get('css', ''))[:5000]
        js_context = str(context_data.get('js', ''))[:5000]

        prompt = f"""
        You are an expert web developer assistant. Explain the provided code snippet clearly and concisely.

        Code Snippet to Explain ({language}):
        ```{language}
        {selected_code}
        ```

        Surrounding Code Context (Truncated if >5000 chars):
        HTML: ```html\n{html_context}\n```
        CSS: ```css\n{css_context}\n```
        JS: ```javascript\n{js_context}\n```

        Task: Provide a clear explanation of what the selected code does, its purpose, and how it might interact with the surrounding context. Use Markdown for formatting if helpful.

        Output Format: Respond ONLY with a single JSON object string: {{ "explanation": "..." }}. NO other text before or after.
        """

        ai_result = generate_ai_response(prompt, expected_format="json")

        if isinstance(ai_result, dict) and "explanation" in ai_result:
            return Response({"explanation": str(ai_result["explanation"])}, status=status.HTTP_200_OK)
        else:
            logger.error(f"AI response for explanation was not valid. Type: {type(ai_result)}, Value: {ai_result}")
            fallback_explanation = "Sorry, I couldn't generate a structured explanation."
            if isinstance(ai_result, str) and ai_result:
                fallback_explanation = ai_result
            return Response({"explanation": fallback_explanation, "error": "Invalid AI response format"}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Developer AI error in explain: {str(e)}", exc_info=True)
        error_message = f"Assistant error: {str(e)}" if settings.DEBUG else "Assistant is currently unavailable."
        return Response({"error": error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot_developer_optimize(request):
    try:
        data = request.data
        code_to_optimize = data.get('code', {})
        user_hints = data.get('hints', '').strip()

        if not isinstance(code_to_optimize, dict) or not any(code_to_optimize.values()):
             return Response({"error": "No code provided for optimization"}, status=status.HTTP_400_BAD_REQUEST)

        html_code = str(code_to_optimize.get('html', ''))[:8000]
        css_code = str(code_to_optimize.get('css', ''))[:8000]
        js_code = str(code_to_optimize.get('js', ''))[:8000]

        prompt = f"""
        You are an expert web performance and code quality assistant. Analyze the provided code for optimizations.

        Code to Optimize (Truncated if >8000 chars):
        HTML: ```html\n{html_code}\n```
        CSS: ```css\n{css_code}\n```
        JS: ```javascript\n{js_code}\n```
        User Hints (Optional): "{user_hints}"

        Task: Analyze for performance (rendering, animation, size), readability, maintainability, best practices. Provide suggestions and/or return optimized code snippets. Use Markdown in the explanation for clarity.

        Output Format: Respond ONLY with a single, valid JSON object string: {{ "html6569201": "...", "css6569201": "...", "js6569201": "...", "explanation": "..." }}.
        - Code values are optimized code (or original if no change recommended).
        - Explanation details optimizations or suggestions.
        - If no significant optimizations found, return original code and state that in explanation.
        """

        ai_result = generate_ai_response(prompt, expected_format="json")

        if isinstance(ai_result, dict) and ("error" in ai_result or all(k in ai_result for k in ["html6569201", "css6569201", "js6569201", "explanation"])):
             response_data = {
                 "html6569201": str(ai_result.get("html6569201", html_code)),
                 "css6569201": str(ai_result.get("css6569201", css_code)),
                 "js6569201": str(ai_result.get("js6569201", js_code)),
                 "explanation": str(ai_result.get("explanation", "No explanation provided.")),
                 "error": ai_result.get("error")
             }
             return Response(response_data, status=status.HTTP_200_OK)
        else:
            logger.error(f"AI response for optimization was not valid. Received: {ai_result}")
            return Response({
                 "html6569201": html_code, "css6569201": css_code, "js6569201": js_code,
                 "explanation": "Error: Assistant did not return the expected optimization structure.",
                 "error": "Invalid AI response structure"
             }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Developer AI error in optimize: {str(e)}", exc_info=True)
        error_message = f"Assistant error: {str(e)}" if settings.DEBUG else "Assistant is currently unavailable."
        return Response({"error": error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot_developer_debug(request):
    try:
        data = request.data
        code_to_debug = data.get('code', {})
        user_issue = data.get('issue_description', '').strip()
        element_context = data.get('element_context', None)

        if not isinstance(code_to_debug, dict) or not any(code_to_debug.values()): return Response({"error": "No code provided"}, status=status.HTTP_400_BAD_REQUEST)
        if not user_issue: return Response({"error": "Please describe the issue"}, status=status.HTTP_400_BAD_REQUEST)

        html_code = str(code_to_debug.get('html', ''))[:9000]
        css_code = str(code_to_debug.get('css', ''))[:9000]
        js_code = str(code_to_debug.get('js', ''))[:9000]

        element_info = f"Specific Element Context (if provided): {json.dumps(element_context)}\n" if element_context else ""

        prompt = f"""
        You are an expert Cross-Context AI Debugger (CAD). Analyze the provided code (HTML, CSS, JS) and user's issue, focusing on interactions *between* code types to find the root cause.

        Code to Debug (Truncated if >9000 chars):
        HTML: ```html\n{html_code}\n```
        CSS: ```css\n{css_code}\n```
        JS: ```javascript\n{js_code}\n```

        User's Issue Description: "{user_issue}"
        {element_info}
        Task (Cross-Context Debugging):
        1. Analyze the user's issue and the full code context.
        2. Identify potential causes considering: HTML structure/semantics, CSS layout/visibility/interaction (`z-index`, `pointer-events`), JS logic/events/timing, AND **interactions** between them (e.g., CSS hiding elements JS targets, JS class changes conflicting with CSS rules, HTML structure preventing selectors/events).
        3. Pinpoint likely problematic code sections across HTML, CSS, and JS.
        4. Suggest specific fixes or concrete debugging steps (e.g., console logs, browser dev tools checks). Use Markdown for formatting the report.

        Output Format: Respond ONLY with a single JSON object string: {{ "debug_report": "..." }}. NO other text.
        - "debug_report": A detailed Markdown string explaining potential bugs, cross-context reasoning, and suggestions.
        - If issue unclear or no bug found, state that and suggest general debugging strategies.
        """

        ai_result = generate_ai_response(prompt, expected_format="json")

        if isinstance(ai_result, dict) and "debug_report" in ai_result:
            return Response({"debug_report": str(ai_result["debug_report"])}, status=status.HTTP_200_OK)
        else:
            logger.error(f"AI response for debug was not valid. Received: {ai_result}")
            fallback_report = "Sorry, I couldn't generate a structured debug report."
            if isinstance(ai_result, str) and ai_result: fallback_report = ai_result
            return Response({"debug_report": fallback_report, "error": "Invalid AI response format"}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Developer AI error in debug: {str(e)}", exc_info=True)
        error_message = f"Assistant error: {str(e)}" if settings.DEBUG else "Assistant is currently unavailable."
        return Response({"error": error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot_developer_inspect(request):
    try:
        data = request.data
        element_info = data.get('element_info', {})
        full_code = data.get('full_code', {})

        if not isinstance(element_info, dict) or not element_info: return Response({"error": "Element info required"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(full_code, dict) or not any(full_code.values()): return Response({"error": "Code context required"}, status=status.HTTP_400_BAD_REQUEST)

        html_code = str(full_code.get('html', ''))[:12000]
        css_code = str(full_code.get('css', ''))[:12000]
        js_code = str(full_code.get('js', ''))[:12000]

        element_desc = f"Tag: {element_info.get('tag', 'N/A')}"
        if element_info.get('id'): element_desc += f", ID: #{element_info.get('id')}"
        if element_info.get('classes'): element_desc += f", Classes: .{'.'.join(element_info.get('classes', []))}"
        element_context_str = json.dumps(element_info)

        prompt = f"""
        You are an Interactive Learning Overlay (ILO) assistant. Analyze the code to identify source snippets, styles, and scripts for a specific HTML element.

        Full Code Context (Truncated if >12000 chars):
        HTML: ```html\n{html_code}\n```
        CSS: ```css\n{css_code}\n```
        JS: ```javascript\n{js_code}\n```

        Target Element Description: {element_desc}
        (Full Info from Frontend: {element_context_str})

        Task:
        1. Locate the most likely source HTML snippet for the Target Element. Include opening tag, brief content indication, and closing tag. Use placeholders like `<!-- ... -->` for large content.
        2. Identify relevant, directly applicable CSS rules (selector + properties) targeting this element (consider specificity).
        3. Identify relevant JS snippets interacting with this element (event listeners, direct manipulations).
        4. Provide a brief explanation of the element's purpose based on its code/context. Use Markdown formatting for the explanation.

        Output Format: Respond ONLY with a single, valid JSON object string: {{ "html_snippet": "...", "css_rules": "...", "js_interactions": "...", "explanation": "..." }}.
        - Format CSS/JS snippets clearly (e.g., one rule/snippet per line).
        - If identification fails, return empty strings and explain the difficulty in `explanation`.
        """

        ai_result = generate_ai_response(prompt, expected_format="json")

        if isinstance(ai_result, dict) and ("error" in ai_result or all(k in ai_result for k in ["html_snippet", "css_rules", "js_interactions", "explanation"])):
            response_data = {
                "html_snippet": str(ai_result.get("html_snippet", "")),
                "css_rules": str(ai_result.get("css_rules", "")),
                "js_interactions": str(ai_result.get("js_interactions", "")),
                "explanation": str(ai_result.get("explanation", "No explanation generated.")),
                "error": ai_result.get("error")
            }
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            logger.error(f"AI response for inspect was not valid. Received: {ai_result}")
            return Response({
                "html_snippet": "", "css_rules": "", "js_interactions": "",
                "explanation": "Error: Assistant could not analyze the element structure.",
                "error": "Invalid AI response structure"
            }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Developer AI error in inspect: {str(e)}", exc_info=True)
        error_message = f"Assistant error: {str(e)}" if settings.DEBUG else "Assistant is currently unavailable."
        return Response({"error": error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Removed legacy chatbot views (chatbot_response, chatbot_response_visora_ai)
# as they are not part of the core developer tool request. Keep them if needed elsewhere.