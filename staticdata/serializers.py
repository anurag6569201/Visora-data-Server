from rest_framework import serializers
from .models import Project, ProjectFile,ProjectLike,ProjectComment,Quiz,Leaderboard,Theory,Examples,Category

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

class TheorySerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())

    class Meta:
        model = Quiz
        fields = ['id', 'project', 'data']

        
class ExamplesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Examples
        fields = '__all__'

class ScoreSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")  # Extract username
    userpic = serializers.CharField(source="user.profile_picture")  # Extract username
    userid = serializers.IntegerField(source="user.userid")  # Extract user ID

    class Meta:
        model = Leaderboard
        fields = ['id', 'username','userpic','userid', 'score', 'updated_at']


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['name', 'children']

    def get_children(self, obj):
        children = obj.children.all()
        return CategorySerializer(children, many=True).data