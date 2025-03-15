# models.py
from django.conf import settings
from django.db import models

class UserProject(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

class ProjectFile(models.Model):
    project = models.ForeignKey(UserProject, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=[
        ('html', 'HTML'),
        ('css', 'CSS'),
        ('js', 'JavaScript'),
        ('media', 'Media')
    ])
    content = models.TextField(blank=True)  # For code files
    file = models.FileField(upload_to='user_uploads/%Y/%m/%d/', null=True, blank=True)  # For media
    version = models.PositiveIntegerField(default=1)
    checksum = models.CharField(max_length=64)  # SHA-256 hash
    created_at = models.DateTimeField(auto_now_add=True)