# apps/core/permissions.py
from rest_framework import permissions
from .models import RolePermission

class ModuleAccessPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        module_name = view.module_name  # Define module_name in view
        tenant = user.tenant
        role_perm = RolePermission.objects.filter(
            role=user.role,
            module__name=module_name,
            tenant=tenant
        ).first()
        if not role_perm:
            return False
        if request.method == 'GET':
            return role_perm.can_view
        if request.method in ['POST', 'PUT', 'PATCH']:
            return role_perm.can_create
        return role_perm.can_delete