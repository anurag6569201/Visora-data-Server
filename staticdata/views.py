from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import os
from django.core.files.base import ContentFile
from django.conf import settings
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .serializers import ProjectCommentSerializer, ProjectLikeSerializer,ProjectSerializer
from .models import Project, ProjectFile,ProjectComment,ProjectLike,UserNameDb
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.decorators import api_view
from rest_framework import generics, permissions

class UploadProjectAPIView(APIView):
    def post(self, request):

        name = request.data.get("project_name")
        description = request.data.get("project_description")
        token = request.data.get("token")
        username = request.data.get("username")
        email = request.data.get("email")
        files = request.FILES.getlist("files")

        if not all([name, description, token]) or not files:
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        # Create or get the project
        project, created = Project.objects.get_or_create(name=name, description=description, token=token,email=email,username=username)

        html_content, css_content, js_content = "", "", ""

        for file in files:
            ext = os.path.splitext(file.name)[1].lower()

            if ext == ".html":
                html_content = file.read().decode("utf-8")
            elif ext == ".css":
                css_content = file.read().decode("utf-8")
            elif ext == ".js":
                js_content = file.read().decode("utf-8")

        # Generate the combined HTML file
        combined_html = f"""
        <html>
          <head>
            <style>{css_content}</style>
          </head>
          <body>
            {html_content}
            <script>{js_content}</script>
          </body>
        </html>
        """

        # Save the combined file to the server
        combined_file_path = os.path.join("projects", project.get_folder_name(), "combined.html")
        ProjectFile.objects.create(project=project, file=ContentFile(combined_html.encode("utf-8"), name="combined.html"))

        return Response({"message": "Project uploaded successfully"}, status=status.HTTP_201_CREATED)

def list_projects(request):

    auth_header = request.headers.get("Authorization")
    if auth_header:
        projects = Project.objects.filter(username=auth_header)
        projects_data = []
        for project in projects:
            folder_path = os.path.join(settings.MEDIA_ROOT, "projects", project.get_folder_name())
            combined_file_path = os.path.join(folder_path, "combined.html")

            if os.path.exists(combined_file_path):
                try:
                    with open(combined_file_path, "r", encoding="utf-8") as f:
                        combined_html = f.read()
                except Exception as e:
                    print(f"Error reading combined.html: {e}")
                    combined_html = ""
            else:
                combined_html = ""

            projects_data.append({
                "id": project.id,
                "name": project.name,
                "combined_html": combined_html,  
            })
    else:
        projects = Project.objects.all()
        projects_data = []
        for project in projects:
            folder_path = os.path.join(settings.MEDIA_ROOT, "projects", project.get_folder_name())
            combined_file_path = os.path.join(folder_path, "combined.html")

            if os.path.exists(combined_file_path):
                try:
                    with open(combined_file_path, "r", encoding="utf-8") as f:
                        combined_html = f.read()
                except Exception as e:
                    print(f"Error reading combined.html: {e}")
                    combined_html = ""
            else:
                combined_html = ""

            projects_data.append({
                "id": project.id,
                "name": project.name,
                "combined_html": combined_html,  
            })

    return JsonResponse({"projects": projects_data})


@api_view(['GET'])
def get_project(request, id):
    try:
        project = Project.objects.get(id=id)  # Django will now match the UUID correctly
        serializer = ProjectSerializer(project)
        return Response(serializer.data)  # DRF handles JSON serialization
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=404)
    except ValueError:
        return Response({"error": "Invalid UUID format"}, status=400)
    
    
class CommentCreateView(APIView):
    serializer_class = ProjectCommentSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, project_id):
        """Fetch all comments for a specific project"""
        project = get_object_or_404(Project, id=project_id)
        comments = ProjectComment.objects.filter(project=project).order_by("-created_at")
        serializer = self.serializer_class(comments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, project_id):
        """Create a new comment for a project"""
        token = request.headers.get("Authorization")
        print("comment Token received:", token)
        if not token:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        user = UserNameDb.objects.filter(username=token).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        project = get_object_or_404(Project, id=project_id)
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            serializer.save(username=user, project=project)  # Save user instance
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




@method_decorator(csrf_exempt, name='dispatch')
class LikeToggleView(View):
    def get(self, request, project_id):
        """Return the like count and whether the user has liked the project"""
        token = request.headers.get("Authorization")
        print("Token received:", token)

        if not token:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        user = UserNameDb.objects.filter(username=token).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        project = get_object_or_404(Project, id=project_id)
        total_likes = ProjectLike.objects.filter(project=project).count()
        is_liked = ProjectLike.objects.filter(username=user, project=project).exists()

        return JsonResponse({"total_likes": total_likes, "is_liked": is_liked})

    def post(self, request, project_id):
        """Toggle like status using get_or_create"""
        token = request.headers.get("Authorization")
        print("Token received:", token)

        if not token:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        user = UserNameDb.objects.filter(username=token).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        project = get_object_or_404(Project, id=project_id)

        like, created = ProjectLike.objects.get_or_create(username=user, project=project)

        if not created:
            like.delete()
            liked = False
        else:
            liked = True

        total_likes = ProjectLike.objects.filter(project=project).count()
        return JsonResponse({"liked": liked, "likes_count": total_likes})
    

@method_decorator(csrf_exempt, name='dispatch')
class RegisterUserNameDbView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode("utf-8"))  # Corrected
            username = data.get("username")
            email = data.get("email")

            if UserNameDb.objects.filter(username=username).exists():
                return JsonResponse({"error": "User already exists in Visiora-Data."}, status=400)

            user = UserNameDb.objects.create(username=username, email=email)
            user.save()

            return JsonResponse({"message": "User created in Visiora-Data."}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        

from rest_framework import viewsets
from .models import Quiz
from .serializers import QuizSerializer
class QuizViewSet(viewsets.ModelViewSet):
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer
    lookup_field = 'id'