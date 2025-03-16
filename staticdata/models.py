import os
from django.db import models

class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    token = models.CharField(max_length=100, unique=False)

    def get_folder_name(self):
        sanitized_name = self.name.replace(" ", "_")
        return f"{sanitized_name}_{self.token[:7]}"

class ProjectFile(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="files")
    
    def file_upload_path(instance, filename):
        folder_name = instance.project.get_folder_name()
        return os.path.join("projects", folder_name, filename)

    file = models.FileField(upload_to=file_upload_path)
