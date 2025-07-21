from django.urls import path, include
from rest_framework import routers
from .views import ForumViewSet, ForumPostViewSet
from .views import ModerationQueueViewSet

router = routers.DefaultRouter()
router.register(r'forums', ForumViewSet)
router.register(r'posts', ForumPostViewSet)
router.register(r'queue', ModerationQueueViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

