from django.urls import path
from .views import UploadProjectAPIView,CommentCreateView,LikeToggleView
from staticdata import views

app_name = "staticdata"


urlpatterns = [
    path('upload/', UploadProjectAPIView.as_view(), name="upload_project"),
    path("api/projects/", views.list_projects, name="project-detail"),
    path("projects/<uuid:project_id>/comments/", CommentCreateView.as_view(), name="project-comments"),
    path("projects/<uuid:project_id>/like/", LikeToggleView.as_view(), name="project-like"),
]
