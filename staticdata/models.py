import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.conf import settings

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




class UserSessionData(models.Model):
    """
    Stores a learning session state, associated with an anonymous user ID.
    Allows multiple session records per anonymous ID.
    """
    # Anonymous User Identifier (replaces ForeignKey to user)
    anonymous_user_id = models.UUIDField(
        db_index=True, # Index for faster lookups
        help_text="UUID identifying the anonymous user/browser."
    )

    # Optional name for the session (e.g., derived from topic)
    name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="User-friendly name for the session."
    )

    # --- Keep other fields as they are ---
    version = models.CharField(max_length=20, default='5.5-html')
    topic = models.CharField(max_length=255, blank=True, default='')
    prerequisites = models.TextField(blank=True, default='')
    duration = models.CharField(max_length=50, blank=True, default='1')
    difficulty = models.CharField(max_length=50, blank=True, default='intermediate')
    theme_mode = models.CharField(max_length=20, default='dark')
    font_size_factor = models.FloatField(default=1.0)
    high_contrast = models.BooleanField(default=False)
    reduce_animations = models.BooleanField(default=False)
    subtopics = models.JSONField(default=list, blank=True)
    plan_data = models.JSONField(default=dict, blank=True)
    review_schedule = models.JSONField(default=dict, blank=True)
    plan_analysis = models.JSONField(null=True, blank=True)
    user_points = models.IntegerField(default=0)
    study_streak = models.IntegerField(default=0)
    earned_badges = models.JSONField(default=list, blank=True)
    last_study_date = models.DateField(null=True, blank=True)
    chat_history = models.JSONField(default=list, blank=True)
    journal_prompts = models.JSONField(default=dict, blank=True)
    selected_subtopic_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        session_name = self.name or f"Session on '{self.topic[:30]}...'" if self.topic else f"Session {self.pk}"
        return f"{session_name} for anon_id {str(self.anonymous_user_id)[:8]}..."

    class Meta:
        verbose_name = "User Session Data"
        verbose_name_plural = "User Session Data"
        # Order by anonymous user, then by update time (latest first)
        ordering = ['anonymous_user_id', '-updated_at']
        # Add index for faster latest session retrieval
        indexes = [
            models.Index(fields=['anonymous_user_id', '-updated_at']),
        ]
