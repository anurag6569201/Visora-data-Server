import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
import google.generativeai as genai
import json
import os
from staticdata.models import Project
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes

logger = logging.getLogger(__name__)

# Configure Gemini only once at startup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

@api_view(['POST'])
def chatbot_response(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        user_message = data.get('message', '').strip()
        project_id = data.get('currentAnimation', '').strip()
        username =  data.get('username', '').strip()
        if not username:
            return JsonResponse({"error": "Username is required"}, status=400)

        if not user_message:
            return JsonResponse({"error": "Message cannot be empty"}, status=400)
        if len(user_message) > 500:
            return JsonResponse({"error": "Message too long (max 500 characters)"}, status=400)

        # Fetch project
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return JsonResponse({"error": "Animation project not found"}, status=404)
        except ValidationError:
            return JsonResponse({"error": "Invalid project ID format"}, status=400)

        # Generate AI response
        prompt = f"""
        You are an expert animation educator assistant. Generate an interactive HTML response for:
        Animation Title: {project.name}
        Description: {project.description}
        User Question: {user_message}

        Requirements:
        - Use HTML with inline CSS/JS and libraries!
        - Include interactive elements
        - Accessible semantic markup
        - Its should be interactive and educational friendly
        - Do NOT include <html> or <head> tags and ```html and not even animation name details and others just only the thing requested!
        - use those colors background:#212529 and these for others #5823c8,#ffffff and dont use any other colors !!     
        - create mobile friendly only.
        - content should be vertical align top start and left and overflow-x hidden as well as mobile friendly screens only
        - if any assessment is provided by you give their ans as well as explanation too.
        """

        response = model.generate_content(prompt)

        html_content = response.text.replace("```html", "").replace("```", "").strip() # Ensure this is only body content
        style = """
        <style>
        *::-webkit-scrollbar {
            width: 8px !important;
        }
        *::-webkit-scrollbar-track {
            background-color: #121212;
        }
        *::-webkit-scrollbar-thumb {
            background-color: rgb(73, 72, 72);
        }
        </style>
        """
        html_content = f"{style}{html_content}"
        return JsonResponse({
            'html': html_content, 
        })
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format"}, status=400)
    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Assistant is currently unavailable. Try again later."}, status=500)





@api_view(['POST'])
def chatbot_response_visora_ai(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        user_message = data.get('message', '').strip()
        category = data.get('category', '').strip()
        subcategory = data.get('subcategory', '').strip()
        topic = data.get('topic', '').strip()
        username =  data.get('username', '').strip()
        
        if not username:
            return JsonResponse({"error": "Username is required"}, status=400)

        if not user_message:
            return JsonResponse({"error": "Message cannot be empty"}, status=400)
        if len(user_message) > 500:
            return JsonResponse({"error": "Message too long (max 500 characters)"}, status=400)

        # Generate AI response
        prompt = f"""
        You are an expert animation educator assistant. Generate an interactive HTML response for:
        Category: {category} (Defines the broad difficulty level, e.g., School, College, Research)
        SubCategory: {subcategory} (Defines the specific grade/class/year/level of complexity within the category, e.g., Grade 8, Undergraduate, Advanced Research)
        Subject: {topic} (Defines the specific subject matter, e.g., Newton’s Laws, Fourier Transform, Quantum Mechanics)
        User Question: {user_message} (Defines what the user is asking, e.g., "How does gravity work?" "Explain Fourier series.")


        Boundary:
        - Strictly maintain the difficulty level based on Category and SubCategory.
        - Ensure interactive elements (animations, simulations, interactive questions) match the exact depth of knowledge needed.
        - The response should contain:
          - A brief, clear explanation suited to {category} and {subcategory}.
          - An interactive simulation, animation, or visual aid to illustrate the concept.
          - A small assessment or question to reinforce learning.
        - The response must not exceed the knowledge expected at {category} and {subcategory} levels.

        Requirements:
        - Use HTML with inline CSS/JS and libraries!
        - Include interactive elements
        - Accessible semantic markup
        - Its should be interactive and educational friendly
        - Do NOT include <html> or <head> tags and ```html and not even animation name details and others just only the thing requested!
        - use those colors background:#212529 and these for others #5823c8,#ffffff and dont use any other colors !!     
        - create mobile friendly only.
        - content should be vertical align top start and left and overflow-x hidden as well as mobile friendly screens only
        - if any assessment is provided by you give their ans as well as explanation too.
        """

        response = model.generate_content(prompt)

        html_content = response.text.replace("```html", "").replace("```", "").strip() # Ensure this is only body content
        style = """
        <style>
        *::-webkit-scrollbar {
            width: 8px !important;
        }
        *::-webkit-scrollbar-track {
            background-color: #121212;
        }
        *::-webkit-scrollbar-thumb {
            background-color: rgb(73, 72, 72);
        }
        </style>
        """
        html_content = f"{style}{html_content}"
        return JsonResponse({
            'html': html_content, 
        })
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format"}, status=400)
    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Assistant is currently unavailable. Try again later."}, status=500)






@api_view(['POST'])
def chatbot_developer(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        user_message = data.get('message', '').strip()
        context_string = data.get('context', '{}').strip() 

        if not user_message:
            return JsonResponse({"error": "Message cannot be empty"}, status=400)
        if len(user_message) > 500:
            return JsonResponse({"error": "Message too long (max 500 characters)"}, status=400)

        prompt = f"""
        You are an expert animation creator.
        Context: {context_string} (Analyze the user's request based on this code context.)
        User Question: {user_message} (Generate code based on this request.)

        Boundary:
        - Generate top-level quality HTML, CSS, and JS code.
        - Ensure NO comments are included in the generated code snippets ('html6569201', 'css'6569201, 'js6569201' values).
        - Ensure the generated code is functional and aims to be error-free.

        Output Format Instructions:
        - IMPORTANT: Respond ONLY with a single, valid JSON object string.
        - The JSON object MUST have exactly these keys: "html6569201", "css6569201", "js6569201".
        - The values for "html", "css", and "js" MUST be strings containing the respective code.
        - Example of the EXACT output format required: {{ "html6569201": "<p>Example</p>", "css6569201": "p {{ color: blue; }}", "js6569201": "console.log('example');" }}
        - Do NOT include any text, explanations, apologies, or markdown fences (like ```json ... ```) before or after the JSON object string.
        - If the request cannot be fulfilled, return: {{ "html6569201": "", "css6569201": "", "js6569201": "" }}

        Requirements:
        - The 'html' value should typically contain only the inner HTML content suitable for the <body>, without <html>, <head>, or <body> tags unless essential and specifically implied by the request.
        - Include CDN links (<script src="...">, <link href="...">) within the 'html6569201' string *only if* necessary for the generated 'js6569201' or 'css6569201' to function.
        - The 'js6569201' value should contain only the raw JavaScript code, without <script> tags.
        """

        response = model.generate_content(prompt)
        ai_response_text = response.text.strip()

        # --- Parse the AI Response ---
        try:
            json_start = ai_response_text.find('{')
            json_end = ai_response_text.rfind('}')

            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_string = ai_response_text[json_start : json_end + 1]
                # Parse the extracted JSON string into a Python dictionary
                parsed_code_dict = json.loads(json_string)

                # Basic validation of the parsed structure
                if not isinstance(parsed_code_dict, dict) or \
                   "html6569201" not in parsed_code_dict or \
                   "css6569201" not in parsed_code_dict or \
                   "js6569201" not in parsed_code_dict:
                    raise ValueError("AI response JSON missing required keys (html6569201, css6569201, js6569201).")

                 # Ensure values are strings (or default to empty string)
                parsed_code_dict["html6569201"] = str(parsed_code_dict.get("html6569201", ""))
                parsed_code_dict["css6569201"] = str(parsed_code_dict.get("css6569201", ""))
                parsed_code_dict["js6569201"] = str(parsed_code_dict.get("js6569201", ""))

            else:
                 raise ValueError("Could not find valid JSON object in AI response.")

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error processing AI response: {e}")
            print(f"Problematic AI response text: {ai_response_text}")
            return JsonResponse({"html6569201": "", "css6569201": "", "js6569201": ""})

        return JsonResponse(parsed_code_dict, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in request body"}, status=400)
    except Exception as e:
        import traceback
        print("------ UNEXPECTED ERROR ------")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")
        traceback.print_exc()
        print("-----------------------------")
        return JsonResponse({"error": "An internal server error occurred. Check server logs."}, status=500)