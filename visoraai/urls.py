from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserProjectViewSet,
    chatbot_developer_generate,
    chatbot_developer_explain,
    chatbot_developer_optimize,
    chatbot_developer_debug,
    chatbot_developer_inspect,
)
from visoraai.old_views import chatbot_response,chatbot_response_visora_ai,chatbot_developer

app_name = "visoraai"

router = DefaultRouter()

urlpatterns = [
    path("api/chatbot/", chatbot_response, name="chatbot_response"),
    path("api/chatbot/visoraai/", chatbot_response_visora_ai, name="chatbot_response_visoraai"),
    path("api/chatbot/developer/", chatbot_developer, name="chatbot_developer"),

    # Developer AI Actions
    path("api/developer/generate/", chatbot_developer_generate, name="chatbot_developer_generate"),
    path("api/developer/explain/", chatbot_developer_explain, name="chatbot_developer_explain"),
    path("api/developer/optimize/", chatbot_developer_optimize, name="chatbot_developer_optimize"),
    path("api/developer/debug/", chatbot_developer_debug, name="chatbot_developer_debug"),
    path("api/developer/inspect/", chatbot_developer_inspect, name="chatbot_developer_inspect"),

    # Project Management API
    path('api/', include(router.urls)),
]