# serializers.py
from rest_framework import serializers
from .models import ProjectFile

class ProjectFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = ['file_name', 'file_type', 'content', 'file']
        extra_kwargs = {
            'content': {'write_only': True},
            'file': {'write_only': True}
        }
