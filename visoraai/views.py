import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
import google.generativeai as genai
import json
import os
from staticdata.models import Project,UserNameDb
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
        print('its calling')
        username =  data.get('username', '').strip()
        print(username)
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
            width: 10px !important;
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
        print(html_content)
        userdetails = UserNameDb.objects.get(username=username)
        iframe = IframeResponse.objects.create(content=html_content, user=userdetails, project=project)
        iframe_url = request.build_absolute_uri(f'/api/chatbot/iframe/{iframe.id}/')

        return JsonResponse({'html': html_content, 'iframe_url': iframe_url})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format"}, status=400)
    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Assistant is currently unavailable. Try again later."}, status=500)


from django.http import HttpResponse
from .models import IframeResponse

def serve_iframe(request, response_id):
    try:
        iframe = IframeResponse.objects.get(id=response_id)
        return HttpResponse(iframe.content, content_type='text/html')
    except IframeResponse.DoesNotExist:
        return HttpResponse("Content not found", status=404)