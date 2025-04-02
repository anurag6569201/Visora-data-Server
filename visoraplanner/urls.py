from django.urls import path
from . import views

app_name='visoraplanner'

urlpatterns = [
    path('api/generate-course-structure/', views.generate_course_structure, name='generate_structure'),
    path('api/generate-subtopic-content/', views.generate_subtopic_content, name='generate_content'),
    path('api/generate-subtopic-assessment/', views.generate_subtopic_assessment, name='generate_assessment'),
    path('api/generate-review-questions/', views.generate_review_questions, name='generate_review'), # <<< New
    path('api/generate-plan-summary/', views.generate_plan_summary, name='generate_summary'),       # <<< New
]