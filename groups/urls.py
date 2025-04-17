from django.urls import path, include
from rest_framework import routers
from .views import RoleViewSet, GroupViewSet, GroupMembershipViewSet

router = routers.DefaultRouter()
router.register(r'roles', RoleViewSet)
router.register(r'groups', GroupViewSet)
router.register(r'memberships', GroupMembershipViewSet)

urlpatterns = [
    path('', include(router.urls)),
]