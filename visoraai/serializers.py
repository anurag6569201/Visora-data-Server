from rest_framework import serializers
from .models import UserProject

class UserProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProject
        fields = ['id', 'name', 'description', 'html_content', 'css_content', 'js_content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class UserProjectListSerializer(serializers.ModelSerializer):
     class Meta:
        model = UserProject
        fields = ['id', 'name', 'updated_at'] # Lighter for list view