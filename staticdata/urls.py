from django.urls import path
from .views import UploadProjectAPIView,CommentCreateView,LikeToggleView,RegisterUserNameDbView
from staticdata import views

app_name = "staticdata"


urlpatterns = [
    path("username/",RegisterUserNameDbView.as_view(), name="usernamedb"),
    path('upload/', UploadProjectAPIView.as_view(), name="upload_project"),
    path("api/projects/", views.list_projects, name="project-detail"),
    path('api/projects/<uuid:id>/', views.get_project, name='get_project'),
    path("projects/<uuid:project_id>/comments/", CommentCreateView.as_view(), name="project-comments"),
    path("projects/<uuid:project_id>/like/", LikeToggleView.as_view(), name="project-like"),
]
