from django.urls import path,include
from .views import UploadProjectAPIView,CommentCreateView,LikeToggleView,RegisterUserNameDbView,QuizViewSet,ScoreViewSet,TheoryViewSet,CategoryListView
from staticdata import views
from rest_framework.routers import DefaultRouter
from .views import (ProjectSearchAPI, ProjectDetailAPI, 
                   ProjectMaterialsAPI, generate_ai_content)

app_name = "staticdata"
router = DefaultRouter()
router.register(r'scores', ScoreViewSet)

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),

    path("username/",RegisterUserNameDbView.as_view(), name="usernamedb"),
    path('upload/', UploadProjectAPIView.as_view(), name="upload_project"),
    path("api/projects/", views.list_projects, name="project-detail"),
    path('api/projects/<uuid:id>/', views.get_project, name='get_project'),
    path("projects/<uuid:project_id>/comments/", CommentCreateView.as_view(), name="project-comments"),
    path("projects/<uuid:project_id>/like/", LikeToggleView.as_view(), name="project-like"),

    path('api/', include(router.urls)),
    path("quizzes/<uuid:project_id>/", QuizViewSet.as_view({'get': 'list'})),
    path("theory/<uuid:project_id>/", TheoryViewSet.as_view({'get': 'list'})),

    path('materials/search/', ProjectSearchAPI.as_view(), name='project-search'),
    path('materials/<uuid:id>/', ProjectDetailAPI.as_view(), name='project-detail'),
    path('materials/<uuid:project_id>/<str:material_type>/', 
         ProjectMaterialsAPI.as_view(), name='project-materials'),
    path('<uuid:project_id>/generate/<str:content_type>/', 
         generate_ai_content, name='generate-content'),
]
