from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Project, ProjectFile

class UploadProjectAPIView(APIView):
    def post(self, request):
        print("Received Data:", request.data)  # Debug: Print request payload
        print("Received Files:", request.FILES)  # Debug: Print uploaded files

        name = request.data.get("project_name")
        description = request.data.get("project_description")
        token = request.data.get("token")
        files = request.FILES.getlist("files")

        if not all([name, description, token]) or not files:
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        project, created = Project.objects.get_or_create(name=name, description=description, token=token)

        for file in files:
            ProjectFile.objects.create(project=project, file=file)

        return Response({"message": "Project uploaded successfully"}, status=status.HTTP_201_CREATED)
