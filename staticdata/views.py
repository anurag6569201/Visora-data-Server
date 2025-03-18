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

from .serializers import ProjectCommentSerializer, ProjectLikeSerializer
from .models import Project, ProjectFile,ProjectComment,ProjectLike


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



class CommentCreateView(APIView):
    serializer_class = ProjectCommentSerializer

    def get_queryset(self):
        project_id = self.kwargs["project_id"]
        return ProjectComment.objects.filter(project__id=project_id)

    def perform_create(self, serializer):
        project = get_object_or_404(Project, id=self.kwargs["project_id"])
        serializer.save(user=self.request.user, project=project)


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
class LikeToggleView(View):
    def get(self, request, project_id):
        """Return the like count and whether the user has liked the project"""
        token = request.headers.get("Authorization")
        print(token)
        if not token:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        project = get_object_or_404(Project, id=project_id)
        total_likes = ProjectLike.objects.filter(project=project).count()
        is_liked = ProjectLike.objects.filter(user_token=token, project=project).exists()

        return JsonResponse({"total_likes": total_likes, "is_liked": is_liked})

    def post(self, request, project_id):
        """Toggle like status using get_or_create"""
        token = request.headers.get("Authorization")
        print(token)
        if not token:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        project = get_object_or_404(Project, id=project_id)

        like, created = ProjectLike.objects.get_or_create(user_token=token, project=project)

        if not created:
            like.delete()
            liked = False
        else:
            liked = True

        total_likes = ProjectLike.objects.filter(project=project).count()
        return JsonResponse({"liked": liked, "likes_count": total_likes})