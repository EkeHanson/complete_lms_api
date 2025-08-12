from django.urls import re_path
from ai_chat.consumers import AIChatConsumer

websocket_urlpatterns = [
    re_path(r'ws/ai-chat/$', AIChatConsumer.as_asgi()),
]