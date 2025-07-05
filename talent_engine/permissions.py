# apps/talent_engine/permissions.py
from rest_framework import permissions
from subscriptions.models import Subscription
from core.models import Tenant
import logging

logger = logging.getLogger('talent_engine')

class IsSubscribedAndAuthorized(permissions.BasePermission):
    def has_permission(self, request, view):
        try:
            tenant = request.user.tenant
            # print("request.tenant")
            # print(request.tenant)
            # print("request.tenant")
            # print("request.user")
            # print(request.user.tenant)
            # print("request.user")

            if not isinstance(tenant, Tenant):
                logger.error("No tenant associated with request")
                return False

            # Check if tenant is subscribed to talent_engine module
            if not Subscription.objects.filter(tenant=tenant, module='talent_engine', is_active=True).exists():
                logger.warning(f"Tenant {tenant.schema_name} is not subscribed to talent_engine module")
                return False

            # Allow safe methods (GET, HEAD, OPTIONS) for all authenticated users
            if request.method in permissions.SAFE_METHODS:
                return request.user.is_authenticated

            # For non-safe methods (POST, PUT, DELETE), require admin role
            # return request.user.is_authenticated and request.user.role == 'admin'
            return request.user.is_authenticated
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}")
            return False