import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

from datetime import timedelta
class UserNameDb(models.Model):
    username = models.CharField(max_length=100)
    profile_picture = models.CharField(max_length=100)
    userid = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    email = models.CharField(max_length=100, unique=False,default='visora@gmail.com')

class Project(models.Model):
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)  # Unique identifier
    name = models.CharField(max_length=255)
    description = models.TextField()
    token = models.CharField(max_length=100, unique=False,default='abcd')
    username = models.CharField(max_length=100, unique=False,default='visora')
    email = models.CharField(max_length=100, unique=False,default='visora@gmail.com')

    tabname = models.CharField(max_length=100, unique=False,default='tab')
    gradename = models.CharField(max_length=100, unique=False,default='tab')
    subjectname = models.CharField(max_length=100, unique=False,default='tab')

    def get_folder_name(self):
        sanitized_name = self.name.replace(" ", "_")
        return f"{sanitized_name}_{self.token[:7]}"

    def total_likes(self):
        return self.likes.count()

    def total_comments(self):
        return self.comments.count()

class ProjectFile(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="files")

    def file_upload_path(instance, filename):
        folder_name = instance.project.get_folder_name()
        return os.path.join("projects", folder_name, filename)

    file = models.FileField(upload_to=file_upload_path)

class ProjectComment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="comments")
    username = models.ForeignKey(UserNameDb, on_delete=models.CASCADE, related_name="usernamecomment") 
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True) 

class ProjectLike(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="likes")
    username = models.ForeignKey(UserNameDb, on_delete=models.CASCADE, related_name="usernamelike") 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project.name} ({self.username})"



class Quiz(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="quizzes")
    data = models.JSONField()

    def __str__(self):
        return f"Quiz for {self.project.name}"
    

class Theory(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="theories")
    data = models.JSONField()

    def __str__(self):
        return f"Theory for {self.project.name}"
    

class Examples(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="examples")
    data = models.JSONField()

    def __str__(self):
        return f"Examples for {self.project.name}"
    
    

class Leaderboard(models.Model):
    user = models.ForeignKey(UserNameDb, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.score}"
    
    def check_time_gap(self):
        """Check if the last update was 24 hours ago or more."""
        return now() - self.updated_at >= timedelta(seconds=5)
    

class Category(models.Model):
    name = models.CharField(max_length=255, unique=False)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children'
    )
    category_name = models.CharField(max_length=100,blank=True,null=True)

    def __str__(self):
        return f"{self.name or '' } -> {self.category_name or ''}".strip()
