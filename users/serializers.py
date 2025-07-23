from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django_tenants.utils import tenant_context
from .models import CustomUser, UserProfile, UserActivity, FailedLogin, BlockedIP, VulnerabilityAlert, ComplianceReport
from core.models import Module
from groups.models import Role
import logging

logger = logging.getLogger(__name__)

class CustomUserSerializer(serializers.ModelSerializer):
    last_login = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)
    class Meta:
        model = CustomUser
        fields = "__all__"
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        return make_password(value)

class AdminUserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['email', 'first_name', 'last_name', 'password', 'role', 'job_role']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value, tenant=self.context['request'].tenant, is_deleted=False).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate_role(self, value):
        tenant = self.context['request'].tenant
        with tenant_context(tenant):
            valid_roles = Role.objects.filter(is_active=True).values_list('code', flat=True)
            if value not in valid_roles:
                raise serializers.ValidationError(f"Invalid role. Must be one of {list(valid_roles)}")
        return value

    def create(self, validated_data):
        tenant = self.context['request'].tenant
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 'carer'),
            job_role=validated_data.get('job_role', 'staff'),
            tenant=tenant,
            status='active',
            is_locked=False
        )
        return user

class UserSerializer(serializers.ModelSerializer):
    modules = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), many=True, required=False)
    password = serializers.CharField(write_only=True)
    is_superuser = serializers.BooleanField(default=False, required=False)
    last_login = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = CustomUser
        fields = "__all__"
        read_only_fields = ['id', 'date_joined']

    def validate(self, data):
        try:
            tenant = self.context['request'].tenant
        except AttributeError:
            raise serializers.ValidationError("Request context or tenant is missing.")
        
        with tenant_context(tenant):
            # Validate modules
            modules = data.get('modules', [])
            for module in modules:
                if module.tenant != tenant:
                    raise serializers.ValidationError(f"Module {module.name} does not belong to tenant {tenant.name}.")

            # Validate role
            role = data.get('role')
            valid_roles = Role.objects.filter(is_active=True).values_list('code', flat=True)
            if role and role not in valid_roles:
                raise serializers.ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}.")

            # Check module assignment restrictions
            if role in ['client', 'family'] and modules:
                raise serializers.ValidationError(f"Role '{role}' cannot be assigned modules.")

            # Validate password
            if 'password' in data:
                if len(data['password']) < 8:
                    raise serializers.ValidationError("Password must be at least 8 characters long")
                data['password'] = make_password(data['password'])

        return data

    def create(self, validated_data):
        modules = validated_data.pop('modules', [])
        is_superuser = validated_data.pop('is_superuser', False)
        tenant = self.context['request'].tenant
        user = CustomUser.objects.create_user(
            **validated_data,
            tenant=tenant,
            is_superuser=is_superuser,
            is_staff=is_superuser
        )
        profile = UserProfile.objects.create(user=user)
        profile.modules.set(modules)
        return user

class UserActivitySerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M")

    class Meta:
        model = UserActivity
        fields = '__all__'

class FailedLoginSerializer(serializers.ModelSerializer):
    class Meta:
        model = FailedLogin
        fields = ['id', 'ip_address', 'username', 'timestamp', 'attempts', 'status']

class BlockedIPSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedIP
        fields = ['id', 'ip_address', 'action', 'reason', 'timestamp']
        read_only_fields = ['id', 'timestamp']

    def validate_ip_address(self, value):
        import re
        ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}$'
        if not (re.match(ipv4_pattern, value) or re.match(ipv6_pattern, value)):
            raise serializers.ValidationError("Invalid IP address format")
        return value

class VulnerabilityAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = VulnerabilityAlert
        fields = ['id', 'severity', 'title', 'component', 'detected', 'status']

class ComplianceReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceReport
        fields = ['id', 'type', 'status', 'last_audit', 'next_audit']
