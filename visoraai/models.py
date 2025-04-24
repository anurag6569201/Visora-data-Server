import uuid
from django.db import models
# Removed User model import as auth is skipped for now
# from django.conf import settings

class UserProject(models.Model):
    # user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='visora_projects') # Temporarily removed
    name = models.CharField(max_length=100, default='Untitled Project')
    description = models.TextField(blank=True, default='')
    html_content = models.TextField(blank=True, default='')
    css_content = models.TextField(blank=True, default='')
    js_content = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        # unique_together = ('user', 'name') # Removed constraint as user is removed

    def __str__(self):
        # return f"{self.name} ({self.user.username})" # Modified due to user removal
        return f"{self.name}"