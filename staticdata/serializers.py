from rest_framework import serializers
from .models import Project, ProjectFile,ProjectLike,ProjectComment

class ProjectFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = ['id', 'file']

class ProjectSerializer(serializers.ModelSerializer):
    files = ProjectFileSerializer(many=True, read_only=True)
    total_likes = serializers.ReadOnlyField()
    total_comments = serializers.ReadOnlyField()
    
    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'token', 'files','total_likes','total_comments']


class ProjectCommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = ProjectComment
        fields = ["id", "user", "text", "created_at"]

class ProjectLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLike
        fields = ["id", "user", "project", "created_at"]