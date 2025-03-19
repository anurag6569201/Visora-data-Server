from rest_framework import serializers
from .models import Project, ProjectFile,ProjectLike,ProjectComment,Quiz

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
    username = serializers.CharField(source="username.username", read_only=True)  # Fetch from username FK

    class Meta:
        model = ProjectComment
        fields = ["id", "username", "text", "created_at"]

class ProjectLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLike
        fields = ["id", "user", "project", "created_at"]




class QuizSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())

    class Meta:
        model = Quiz
        fields = ['id', 'project', 'data']