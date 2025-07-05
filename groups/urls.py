from django.urls import path, include
from rest_framework import routers
from .views import RoleViewSet, GroupViewSet, GroupMembershipViewSet

router = routers.DefaultRouter()
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'memberships', GroupMembershipViewSet, basename='groupmembership')

urlpatterns = [
    path('', include(router.urls)),
]