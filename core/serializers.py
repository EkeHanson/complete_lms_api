# apps/core/serializers.py
from rest_framework import serializers
from .models import Tenant, Domain, Module, TenantConfig
import re
import logging

logger = logging.getLogger('core')

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['id', 'domain', 'is_primary']

class TenantSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(write_only=True, required=True)
    domains = DomainSerializer(many=True, read_only=True, source='domain_set')

    class Meta:
        model = Tenant
        fields = "__all__"
        #fields = ['id', 'name', 'schema_name', 'created_at', 'domain', 'domains']
        read_only_fields = ['id', 'schema_name', 'created_at', 'domains']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\'-]+$', value):
            raise serializers.ValidationError("Tenant name can only contain letters, numbers, spaces, apostrophes, or hyphens.")
        return value

    def validate_schema_name(self, value):
        if not re.match(r'^[a-z0-9_]+$', value):
            raise serializers.ValidationError("Schema name can only contain lowercase letters, numbers, or underscores.")
        if Tenant.objects.filter(schema_name=value).exists():
            raise serializers.ValidationError("Schema name already exists.")
        return value

    def validate_domain(self, value):
        if not re.match(r'^[a-zA-Z0-9\-\.]+$', value):
            raise serializers.ValidationError("Invalid domain name.")
        if Domain.objects.filter(domain=value).exists():
            raise serializers.ValidationError(f"Domain '{value}' already exists.")
        return value

    def create(self, validated_data):
        domain_name = validated_data.pop('domain')
        schema_name = validated_data.get('schema_name') or validated_data['name'].lower().replace(' ', '_').replace('-', '_')
        validated_data['schema_name'] = schema_name
        logger.info(f"Creating tenant with name: {validated_data['name']}, schema_name: {schema_name}, domain: {domain_name}")
        try:
            tenant = Tenant.objects.create(**validated_data)
            logger.info(f"Tenant created: {tenant.id}, schema_name: {tenant.schema_name}")
            domain = Domain.objects.create(tenant=tenant, domain=domain_name, is_primary=True)
            logger.info(f"Domain created: {domain.domain} for tenant {tenant.id}")
            TenantConfig.objects.create(tenant=tenant)
            default_modules = ['Talent Engine', 'Compliance', 'Training', 'Care Coordination', 'Workforce', 'Analytics', 'Integrations']
            for module_name in default_modules:
                Module.objects.create(name=module_name, tenant=tenant)
            logger.info(f"Modules and config created for tenant {tenant.id}")
            try:
                domains = tenant.domain_set.all()
                logger.info(f"Domains for tenant {tenant.id}: {[d.domain for d in domains]}")
            except AttributeError as e:
                logger.error(f"domain_set access failed: {str(e)}")
                domains = Domain.objects.filter(tenant=tenant)
                logger.info(f"Fallback domains for tenant {tenant.id}: {[d.domain for d in domains]}")
            return tenant
        except Exception as e:
            logger.error(f"Failed to create tenant or domain: {str(e)}")
            raise