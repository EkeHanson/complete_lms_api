from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatSessionViewSet, ChatMessageViewSet

router = DefaultRouter()
router.register(r'chat-sessions', ChatSessionViewSet, basename='chat-session')

urlpatterns = [
    path('', include(router.urls)),
    path('chat-sessions/<int:session_pk>/messages/', ChatMessageViewSet.as_view({'get': 'list', 'post': 'create'})),
]