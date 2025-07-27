# apps/core/serializers.py
from rest_framework import serializers
from .models import Tenant, Domain, Module, TenantConfig, Branch
import re
import logging
from django.db import transaction
logger = logging.getLogger('core')
from django_tenants.utils import tenant_context

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['id', 'domain', 'is_primary']

    def validate_domain(self, value):
        logger.info(f"Validating domain: {value}")
        if not re.match(r'^[a-zA-Z0-9\-\.]+$', value):
            logger.error(f"Invalid domain format: {value}")
            raise serializers.ValidationError("Invalid domain name.")
        if self.instance:
            if Domain.objects.filter(domain=value).exclude(tenant=self.instance.tenant).exists():
                logger.error(f"Domain already exists for another tenant: {value}")
                raise serializers.ValidationError(f"Domain '{value}' already exists.")
        else:
            if Domain.objects.filter(domain=value).exists():
                logger.error(f"Domain already exists: {value}")
                raise serializers.ValidationError(f"Domain '{value}' already exists.")
        return value

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'location', 'is_head_office', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', value):
            raise serializers.ValidationError("Branch name can only contain letters, numbers, spaces, or hyphens.")
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(f"Error accessing request.user.tenant: {str(e)}")
            raise serializers.ValidationError("Tenant not found in request context")
        with tenant_context(tenant):
            if Branch.objects.filter(tenant=tenant, name=value).exists():
                raise serializers.ValidationError(f"Branch '{value}' already exists for this tenant.")
        return value

    def validate_is_head_office(self, value):
        if value:
            try:
                tenant = self.context['request'].user.tenant
            except AttributeError as e:
                logger.error(f"Error accessing request.user.tenant: {str(e)}")
                raise serializers.ValidationError("Tenant not found in request context")
            with tenant_context(tenant):
                existing_head_office = Branch.objects.filter(
                    tenant=tenant,
                    is_head_office=True
                ).exclude(id=self.instance.id if self.instance else None)
                if existing_head_office.exists():
                    raise serializers.ValidationError(
                        f"Another branch ('{existing_head_office.first().name}') is already set as head office for this tenant."
                    )
        return value

    def validate(self, data):
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(f"Error accessing request.user.tenant: {str(e)}")
            raise serializers.ValidationError("Tenant not found in request context")
        data['tenant'] = tenant
        return data

class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'name', 'is_active']
        read_only_fields = ['id']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', value):
            raise serializers.ValidationError("Module name can only contain letters, numbers, spaces, or hyphens.")
        tenant = self.context['request'].user.tenant
        with tenant_context(tenant):
            if Module.objects.filter(name=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"Module '{value}' already exists for this tenant.")
        return value

    def validate(self, data):
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(f"Error accessing request.user.tenant: {str(e)}")
            raise serializers.ValidationError("Tenant not found in request context")
        data['tenant'] = tenant
        return data

class EmailTemplateSerializer(serializers.Serializer):
    content = serializers.CharField()
    is_auto_sent = serializers.BooleanField(default=False)

class TenantConfigSerializer(serializers.ModelSerializer):
    email_templates = serializers.DictField(
        child=EmailTemplateSerializer(),
        required=False
    )

    class Meta:
        model = TenantConfig
        fields = ['logo', 'custom_fields', 'email_templates']

class TenantSerializer(serializers.ModelSerializer):
    domains = DomainSerializer(many=True, source='domain_set')
    config = TenantConfigSerializer(source='tenantconfig', read_only=True)

    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'schema_name', 'created_at',
            'email_host', 'email_port', 'email_use_ssl', 'email_host_user',
            'email_host_password', 'default_from_email', 'domains', 'config'
        ]
        read_only_fields = ['id', 'schema_name', 'created_at', 'config']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\'-]+$', value):
            raise serializers.ValidationError("Tenant name can only contain letters, numbers, spaces, apostrophes, or hyphens.")
        return value

    def validate_schema_name(self, value):
        if not re.match(r'^[a-z0-9_]+$', value):
            raise serializers.ValidationError("Schema name can only contain lowercase letters, numbers, or underscores.")
        if Tenant.objects.filter(schema_name=value).exclude(id=self.instance.id if self.instance else None).exists():
            raise serializers.ValidationError("Schema name already exists.")
        return value

    def validate_domains(self, value):
        if not value:
            raise serializers.ValidationError("At least one domain is required.")
        primary_count = sum(1 for domain in value if domain.get('is_primary', False))
        if primary_count != 1:
            raise serializers.ValidationError("Exactly one domain must be marked as primary.")
        return value

    def validate(self, data):
        schema_name = data.get('schema_name') or data['name'].lower().replace(' ', '_').replace('-', '_')
        data['schema_name'] = schema_name
        self.validate_schema_name(schema_name)
        return data

    def create(self, validated_data):
        domains_data = validated_data.pop('domain_set', [])
        schema_name = validated_data['schema_name']
        logger.info(f"Creating tenant with name: {validated_data['name']}, schema_name: {schema_name}")
        try:
            with transaction.atomic():
                tenant = Tenant.objects.create(**validated_data)
                logger.info(f"Tenant created: {tenant.id}, schema_name: {tenant.schema_name}")
                
                for domain_data in domains_data:
                    Domain.objects.create(
                        tenant=tenant,
                        domain=domain_data['domain'],
                        is_primary=domain_data.get('is_primary', False)
                    )
                    logger.info(f"Domain created: {domain_data['domain']} for tenant {tenant.id}")

                default_templates = {
                    'interviewScheduling': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'We’re pleased to invite you to an interview for the [Position] role at [Company].\n'
                            'Please let us know your availability so we can confirm a convenient time.\n\n'
                            'Best regards,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewRescheduling': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Due to unforeseen circumstances, we need to reschedule your interview originally set for [Old Date/Time]. '
                            'Kindly share a few alternative slots that work for you.\n\n'
                            'Thanks for your understanding,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewRejection': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Thank you for taking the time to interview. After careful consideration, '
                            'we have decided not to move forward.\n\n'
                            'Best wishes,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewAcceptance': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Congratulations! We are moving you to the next stage. We’ll follow up with next steps.\n\n'
                            'Looking forward,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'jobRejection': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Thank you for applying. Unfortunately, we’ve chosen another candidate at this time.\n\n'
                            'Kind regards,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'jobAcceptance': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'We’re excited to offer you the [Position] role at [Company]! '
                            'Please find the offer letter attached.\n\n'
                            'Welcome aboard!\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'passwordReset': {
                        'content': (
                            'Hello [User Name],\n\n'
                            'You have requested to reset your password for [Company]. '
                            'Please use the following link to reset your password:\n\n'
                            '[Reset Link]\n\n'
                            'This link will expire in 1 hour.\n\n'
                            'Best regards,\n[Your Name]'
                        ),
                        'is_auto_sent': True
                    }
                }

                TenantConfig.objects.create(
                    tenant=tenant,
                    email_templates=default_templates
                )
                logger.info(f"TenantConfig created for tenant {tenant.id} with default email templates")

                default_modules = [
                    'Talent Engine', 'Compliance', 'Training', 'Care Coordination',
                    'Workforce', 'Analytics', 'Integrations', 'Assets Management', 'Payroll'
                ]
                for module_name in default_modules:
                    Module.objects.create(name=module_name, tenant=tenant)
                logger.info(f"Modules created for tenant {tenant.id}")

                return tenant
        except Exception as e:
            logger.error(f"Failed to create tenant or domain: {str(e)}")
            raise

    def update(self, instance, validated_data):
        domains_data = validated_data.pop('domain_set', [])
        instance = super().update(instance, validated_data)
        if domains_data:
            instance.domain_set.all().delete()
            for domain_data in domains_data:
                Domain.objects.create(
                    tenant=instance,
                    domain=domain_data['domain'],
                    is_primary=domain_data.get('is_primary', False)
                )
        return instance