from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "staticdata"

router = DefaultRouter()
router.register(r'quizzes/project/(?P<project_id>[^/.]+)', views.QuizViewSet, basename='project-quiz')
router.register(r'theories/project/(?P<project_id>[^/.]+)', views.TheoryViewSet, basename='project-theory')
router.register(r'scores', views.ScoreViewSet, basename='leaderboard')
router.register(r'user-sessions', views.UserSessionViewSet, basename='user-session')

urlpatterns = [
    path('api/', include(router.urls)),
    path("api/projects/upload/", views.UploadProjectAPIView.as_view(), name="upload_project"),
    path("api/projects/opensource_upload/", views.OpenSourceUploadProjectAPIView.as_view(), name="opensource_upload_project"),
    path("api/projects/", views.list_projects, name="list_projects"),
    path("api/projects/list_names/", views.list_project_names_ids, name="list_project_names_ids"),
    path('api/projects/<uuid:id>/', views.get_project, name='get_project_detail'),
    path('api/projects/<uuid:id>/update/', views.update_project_code, name='update_project_code'),
    path('api/projects/<uuid:id>/delete/', views.delete_project_server, name='delete_project_server'),
    path("api/projects/<uuid:project_id>/comments/", views.CommentCreateView.as_view(), name="project_comments"),
    path("api/projects/<uuid:project_id>/likes/toggle/", views.LikeToggleView.as_view(), name="project_like_toggle"),
    path("api/users/register_visora_db/", views.RegisterUserNameDbView.as_view(), name="register_visora_db_user"),
    path('api/projects/<uuid:project_id>/ai/<str:content_type>/', views.generate_ai_content, name='generate_ai_for_project'),
    path('api/categories/', views.CategoryListView.as_view(), name='category_list'),
    path('api/projects/search/', views.ProjectSearchView.as_view(), name='project_search'),
    path('api/projects_generic/<uuid:id>/', views.ProjectDetailView.as_view(), name='project_detail_generic'),
    path('api/projects/<uuid:project_id>/materials/', views.ProjectMaterialsView.as_view(), name='project_materials'),
]