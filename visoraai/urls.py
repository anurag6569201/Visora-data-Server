from django.urls import path
from .views import chatbot_response,serve_iframe

app_name = "visoraai"


urlpatterns = [
    path("api/chatbot/", chatbot_response, name="chatbot_response"),
    path('api/chatbot/iframe/<uuid:response_id>/',serve_iframe,name='serve_iframe'),
]