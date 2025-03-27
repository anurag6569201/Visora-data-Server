from django.urls import path
from .views import chatbot_response

app_name = "visoraai"


urlpatterns = [
    path("api/chatbot/", chatbot_response, name="chatbot_response"),
]