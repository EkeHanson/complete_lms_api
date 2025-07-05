# apps/users/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from core.models import Domain, Tenant
from django_tenants.utils import tenant_context
from django.core.exceptions import ObjectDoesNotExist
import logging

logger = logging.getLogger('users')

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.user.email
        if not email:
            raise ValueError("Email not provided by social provider")

        # Extract domain from email
        email_domain = email.split('@')[1].lower()

        try:
            # Find tenant by email domain
            domain = Domain.objects.get(domain=email_domain)
            tenant = domain.tenant
        except ObjectDoesNotExist:
            logger.error(f"No tenant found for email domain: {email_domain}")
            raise ValueError(f"No tenant associated with domain {email_domain}")

        # Set tenant context for user creation
        with tenant_context(tenant):
            user = sociallogin.user
            if not user.pk:
                # New user: assign tenant and default role
                user.tenant = tenant
                user.role = 'carer'  # Default role; adjust as needed
                user.save()
                logger.info(f"Created user {email} for tenant {tenant.schema_name}")
            else:
                # Existing user: verify tenant
                if user.tenant != tenant:
                    logger.error(f"User {email} attempted login with wrong tenant")
                    raise ValueError("User belongs to a different tenant")

        sociallogin.connect(request, sociallogin.user)