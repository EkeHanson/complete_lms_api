# messaging/routing.py
from django.urls import path
from .consumers import MessageConsumer

websocket_urlpatterns = [
    path("ws/messaging/", MessageConsumer.as_asgi()),
]

