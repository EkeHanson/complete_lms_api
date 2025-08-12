from django.urls import re_path
from .consumers import MessageConsumer
from ai_chat.consumers import AIChatConsumer

websocket_urlpatterns = [
    re_path(r"ws/messaging/$", MessageConsumer.as_asgi()),
    re_path(r"ws/ai-chat/$", AIChatConsumer.as_asgi()),
]

