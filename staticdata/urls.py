from django.urls import path
from .views import UploadProjectAPIView

app_name = "staticdata"


urlpatterns = [
    path('upload/', UploadProjectAPIView.as_view(), name="upload_project"),
]
