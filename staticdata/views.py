from rest_framework import permissions, viewsets
from .models import ProjectFile
from .serializers import ProjectFileSerializer

class ProjectFileViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectFileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ProjectFile.objects.filter(project__user=self.request.user)
    
    def perform_create(self, serializer):
        # Calculate checksum
        file = serializer.validated_data.get('file')
        content = serializer.validated_data.get('content', '')
        checksum = calculate_checksum(file, content)
        
        serializer.save(
            project=self.request.user.projects.first(),
            checksum=checksum
        )

def calculate_checksum(file=None, content=''):
    # Implement SHA-256 hashing
    ...