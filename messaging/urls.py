from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import MessageViewSet, MessageAttachmentViewSet, MessageTypeViewSet

router = DefaultRouter()
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'attachments', MessageAttachmentViewSet, basename='attachment')
router.register(r'message-types', MessageTypeViewSet)

urlpatterns = router.urls