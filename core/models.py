from django_tenants.models import TenantMixin, DomainMixin
from django.db import models
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

class Branch(models.Model):
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)  # For interview locations
    is_head_office = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'name')

    def __str__(self):
        return f"{self.tenant.name} - {self.name}"

class Module(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)

class RolePermission(models.Model):
    role = models.CharField(max_length=20, choices=[
        ('admin', 'Admin'),
        ('hr', 'HR'),
        ('carer', 'Carer'),
        ('client', 'Client'),
        ('family', 'Family'),
        ('auditor', 'Auditor'),
        ('tutor', 'Tutor'),
        ('assessor', 'Assessor'),
        ('iqa', 'IQA'),
        ('eqa', 'EQA'),
        ('recruiter', 'Recruiter'),
        ('team_manager', 'Team Manager'),
    ])
    module = models.ForeignKey('Module', on_delete=models.CASCADE)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)

class AIDecisionLog(models.Model):
    decision_type = models.CharField(max_length=100)
    confidence_score = models.FloatField()
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)

class TenantConfig(models.Model):
    tenant = models.OneToOneField('Tenant', on_delete=models.CASCADE)
    logo = models.ImageField(upload_to='tenant_logos/', null=True, blank=True)
    custom_fields = models.JSONField(default=dict)
    email_templates = models.JSONField(default=dict)


