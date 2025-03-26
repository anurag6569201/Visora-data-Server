import uuid
from django.db import models
from staticdata.models import UserNameDb,Project

class IframeResponse(models.Model):
    user = models.ForeignKey(UserNameDb, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)