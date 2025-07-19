from rest_framework import serializers
from .models import CustomUser, UserProfile, UserActivity
from core.models import Module, Tenant, Domain
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from rest_framework import exceptions
from django.utils import timezone
from django_tenants.utils import tenant_context
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




# class AdminUserCreateSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True, style={'input_type': 'password'})

#     class Meta:
#         model = CustomUser
#         fields = "__all__"
#         extra_kwargs = {
#             'role': {'required': False, 'default': 'admin'},
#             'email': {'required': True},
#         }

#     def validate_email(self, value):
#         try:
#             domain = value.split('@')[1].lower()
#         except IndexError:
#             raise serializers.ValidationError("Invalid email format.")
#         if not Domain.objects.filter(domain=domain).exists():
#             raise serializers.ValidationError(f"No tenant found for domain '{domain}'.")
#         if CustomUser.objects.filter(email=value).exists():
#             raise serializers.ValidationError(f"User with email '{value}' already exists.")
#         return value

#     def validate_password(self, value):
#         if len(value) < 8:
#             raise serializers.ValidationError("Password must be at least 8 characters long")
#         return make_password(value)

#     def create(self, validated_data):
#         email = validated_data['email']
#         domain = email.split('@')[1].lower()
#         domain_obj = Domain.objects.get(domain=domain)
#         tenant = domain_obj.tenant
#         password = validated_data.pop('password')
#         from django_tenants.utils import tenant_context
#         with tenant_context(tenant):
#             user = CustomUser.objects.create_superuser(
#                 email=validated_data['email'],
#                 password=password,
#                 role='admin',
#                 tenant=tenant,
#                 is_active=True,
#                 is_staff=True,
#                 is_superuser=True,
#                 **{k: v for k, v in validated_data.items() if k != 'email'}
#             )
#         return user


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
        valid_roles = [r[0] for r in CustomUser.ROLES]
        if value not in valid_roles:
            raise serializers.ValidationError(f"Invalid role. Must be one of {valid_roles}")
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
        read_only_fields = ['id', 'signup_date']

    def validate(self, data):
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError:
            raise serializers.ValidationError("Request context or user tenant is missing.")
        modules = data.get('modules', [])
        for module in modules:
            if module.tenant != tenant:
                raise serializers.ValidationError(f"Module {module.name} does not belong to tenant {tenant.name}.")
        role = data.get('role')
        valid_roles = [role[0] for role in CustomUser.ROLES]
        if role and role not in valid_roles:
            raise serializers.ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}.")
        if role in ['client', 'family'] and modules:
            raise serializers.ValidationError(f"Role '{role}' cannot be assigned modules.")
        if 'password' in data:
            if len(data['password']) < 8:
                raise serializers.ValidationError("Password must be at least 8 characters long")
            data['password'] = make_password(data['password'])
        return data

    def create(self, validated_data):
        modules = validated_data.pop('modules', [])
        is_superuser = validated_data.pop('is_superuser', False)
        tenant = self.context['request'].user.tenant
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