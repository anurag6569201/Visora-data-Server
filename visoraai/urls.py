from django.urls import path
from .views import chatbot_response,chatbot_response_visora_ai

app_name = "visoraai"


urlpatterns = [
    path("api/chatbot/", chatbot_response, name="chatbot_response"),
    path("api/chatbot/visoraai/", chatbot_response_visora_ai, name="chatbot_response_visoraai"),
]