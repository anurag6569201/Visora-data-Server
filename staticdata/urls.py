from django.urls import path,include
from .views import UploadProjectAPIView,CommentCreateView,LikeToggleView,RegisterUserNameDbView,QuizViewSet,ScoreViewSet,TheoryViewSet,CategoryListView,UserSessionViewSet
from staticdata import views
from rest_framework.routers import DefaultRouter
from .views import (generate_ai_content)

app_name = "staticdata"
router = DefaultRouter()
router.register(r'scores', ScoreViewSet)
router.register(r'user-sessions', UserSessionViewSet, basename='usersession')


urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),

    path("username/",RegisterUserNameDbView.as_view(), name="usernamedb"),
    path('upload/', UploadProjectAPIView.as_view(), name="upload_project"),
    path("api/projects/", views.list_projects, name="project-detail"),
    path('api/projects/<uuid:id>/', views.get_project, name='get_project'),
    path("projects/<uuid:project_id>/comments/", CommentCreateView.as_view(), name="project-comments"),
    path("projects/<uuid:project_id>/like/", LikeToggleView.as_view(), name="project-like"),

    path('api/', include(router.urls)),
     path("quizzes/<uuid:project_id>/", QuizViewSet.as_view({'get': 'list', 'post': 'create'}), name='quiz-list'),
     path("theory/<uuid:project_id>/", TheoryViewSet.as_view({'get': 'list', 'post': 'create'}), name='theory-list'),
     # Search projects (now includes pagination)
    path('api/projects/search/', views.ProjectSearchView.as_view(), name='project-search'),

    # Get details for a specific project
    path('api/projects/<int:id>/', views.ProjectDetailView.as_view(), name='project-detail'),

    # Get materials for a specific project (using query parameter for type)
    path('api/projects/<int:project_id>/materials/', views.ProjectMaterialsView.as_view(), name='project-materials'),

    path('<uuid:project_id>/generate/<str:content_type>/', 
         generate_ai_content, name='generate-content'),

]
