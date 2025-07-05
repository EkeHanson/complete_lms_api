# core/utils/email_config.py
from django.conf import settings
from django.core.mail import get_connection
from django_tenants.utils import get_tenant

from django.conf import settings
from django.core.mail import get_connection

# def get_email_connection():
#     try:
#         tenant = get_tenant()
#         if tenant and tenant.email_host and tenant.email_host_user:
#             return get_connection(
#                 backend='django.core.mail.backends.smtp.EmailBackend',
#                 host=tenant.email_host,
#                 port=tenant.email_port,
#                 username=tenant.email_host_user,
#                 password=tenant.email_host_password,
#                 use_ssl=tenant.email_use_ssl,
#             )
#     except Exception as e:
#         pass

#     # fallback to global settings
#     return get_connection()




def configure_email_backend(tenant):
    """
    Configure the email backend with tenant-specific settings.
    """
    # print("tenant")
    # print(tenant)
    # print(tenant.email_host)
    # print(tenant.email_host_user)
    # print(tenant.email_host_user)
    # print("tenant")
    email_settings = {
        'EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'EMAIL_HOST': tenant.email_host or getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com'),
        'EMAIL_PORT': tenant.email_port or getattr(settings, 'EMAIL_PORT', 587),
        'EMAIL_USE_SSL': tenant.email_use_ssl if tenant.email_use_ssl is not None else getattr(settings, 'EMAIL_USE_SSL', True),
        'EMAIL_HOST_USER': tenant.email_host_user or getattr(settings, 'EMAIL_HOST_USER', ''),
        'EMAIL_HOST_PASSWORD': tenant.email_host_password or getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
        'DEFAULT_FROM_EMAIL': tenant.default_from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
    }
    return get_connection(
        backend=email_settings['EMAIL_BACKEND'],
        host=email_settings['EMAIL_HOST'],
        port=email_settings['EMAIL_PORT'],
        username=email_settings['EMAIL_HOST_USER'],
        password=email_settings['EMAIL_HOST_PASSWORD'],
        use_ssl=email_settings['EMAIL_USE_SSL'],
    )