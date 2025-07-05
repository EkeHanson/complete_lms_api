from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MessageViewSet, MessageAttachmentViewSet, MessageTypeViewSet

router = DefaultRouter()
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'attachments', MessageAttachmentViewSet, basename='attachment')
router.register(r'message-types', MessageTypeViewSet, basename='message-type')

urlpatterns = [
    path('api/', include(router.urls)),  # Maps to /messaging/api/messages/, /messaging/api/attachments/, etc.
    path('api/messages/unread_count/', MessageViewSet.as_view({'get': 'unread_count'}), name='unread-message-count'),
]