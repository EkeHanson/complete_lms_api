# messaging/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import MessageViewSet, MessageAttachmentViewSet

router = DefaultRouter()
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'attachments', MessageAttachmentViewSet, basename='attachment')

urlpatterns = router.urls