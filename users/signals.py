from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
from django_tenants.utils import tenant_context
from .models import FailedLogin
import logging
from django.db.models.signals import m2m_changed
from django.contrib.auth.models import Group
from courses.models import Instructor, CustomUser

logger = logging.getLogger('users')

@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        logger.error("No tenant associated with failed login attempt")
        return
    try:
        with tenant_context(tenant):
            ip_address = request.META.get('REMOTE_ADDR', 'unknown')
            username = credentials.get('username', 'unknown')
            FailedLogin.objects.create(
                tenant=tenant,
                ip_address=ip_address,
                username=username,
                attempts=1,  # Increment if tracking multiple attempts per IP/username
                status='failed'
            )
            logger.info(f"[{tenant.schema_name}] Recorded failed login for username {username} from IP {ip_address}")
    except Exception as e:
        logger.error(f"[{tenant.schema_name}] Error recording failed login: {str(e)}", exc_info=True)

@receiver(m2m_changed, sender=CustomUser.groups.through)
def create_instructor_profile(sender, instance, action, pk_set, **kwargs):
    if action == 'post_add':
        instructor_group = Group.objects.filter(name="Instructor").first()
        if instructor_group:
            if instructor_group.pk in pk_set:
                # Create Instructor profile if not exists
                Instructor.objects.get_or_create(
                    user=instance,
                    defaults={'bio': '', 'is_active': True}
                )