# users/permissions.py
from rest_framework.permissions import BasePermission

class IsOwnerUser(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == 'owner'
    
class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == 'admin'

class IsInstructorUser(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == 'instructor'

class IsLearnerUser(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == 'learner'