# apps/core/models.py
from django_tenants.models import TenantMixin, DomainMixin
from django.db import models
from users.models import CustomUser
import logging
logger = logging.getLogger('core')

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    schema_name = models.CharField(max_length=63, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    email_host = models.CharField(max_length=255, null=True, blank=True)
    email_port = models.IntegerField(null=True, blank=True)
    email_use_ssl = models.BooleanField(default=True)
    email_host_user = models.EmailField(null=True, blank=True)
    email_host_password = models.CharField(max_length=255, null=True, blank=True)
    default_from_email = models.EmailField(null=True, blank=True)
    auto_create_schema = True

    def save(self, *args, **kwargs):
        if not self.schema_name or self.schema_name.strip() == '':
            self.schema_name = self.name.lower().replace(' ', '_').replace('-', '_')
        logger.info(f"Saving tenant with schema_name: {self.schema_name}")
        super().save(*args, **kwargs)

class Domain(DomainMixin):
    tenant = models.ForeignKey('core.Tenant', related_name='domain_set', on_delete=models.CASCADE)

# apps/core/models.py
class Module(models.Model):
    name = models.CharField(max_length=100)  # e.g., Talent Engine, Compliance
    is_active = models.BooleanField(default=True)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)

# apps/core/models.py
class RolePermission(models.Model):
    role = models.CharField(max_length=20, choices=CustomUser.ROLES)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)

#Log AI decisions in a dedicated model:
class AIDecisionLog(models.Model):
    decision_type = models.CharField(max_length=100)  # e.g., 'candidate_match'
    confidence_score = models.FloatField()
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)

# apps/core/models.py Tenant Customization
class TenantConfig(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE)
    logo = models.ImageField(upload_to='tenant_logos/')
    custom_fields = models.JSONField(default=dict)