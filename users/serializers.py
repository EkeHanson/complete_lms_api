from rest_framework import serializers
from django_tenants.utils import tenant_context
from .models import CustomUser, UserActivity, FailedLogin, BlockedIP, VulnerabilityAlert, ComplianceReport, PasswordResetToken
from core.models import Module
from django.utils import timezone
import logging
from utils.supabase import upload_to_supabase
import uuid
from utils.storage import get_storage_service

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
        return value  # Do not hash here; hashing is handled in create_user

class AdminUserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value, tenant=self.context['request'].tenant, is_deleted=False).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def create(self, validated_data):
        tenant = self.context['request'].tenant
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 'carer'),
            tenant=tenant,
            status='active',
            is_locked=False
        )
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

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        tenant = self.context['request'].tenant
        with tenant_context(tenant):
            if not CustomUser.objects.filter(email=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"No user found with email '{value}' for this tenant.")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, min_length=8, required=True)

    def validate_token(self, value):
        tenant = self.context['request'].tenant
        with tenant_context(tenant):
            try:
                reset_token = PasswordResetToken.objects.get(token=value, tenant=tenant)
                if reset_token.expires_at < timezone.now():
                    raise serializers.ValidationError("This token has expired.")
                if reset_token.used:
                    raise serializers.ValidationError("This token has already been used.")
            except PasswordResetToken.DoesNotExist:
                raise serializers.ValidationError("Invalid token.")
        return value

    def validate_new_password(self, value):
        if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter and one number.")
        return value

class UserSerializer(serializers.ModelSerializer):
    modules = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), many=True, required=False)
    profile_picture = serializers.ImageField(required=False, allow_null=True, use_url=False)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    facebook_link = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    twitter_link = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    linkedin_link = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(write_only=True, required=True)  # Password is required for registration
    last_login = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'first_name', 'last_name', 'role', 'status', 'is_locked', 'is_active',
            'date_joined', 'last_login', 'modules', 'phone', 'title', 'bio', 'facebook_link',
            'twitter_link', 'linkedin_link', 'profile_picture', 'password', 'tenant'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_active', 'tenant']

    def validate(self, data):
        if 'password' in data and data['password'] and len(data['password']) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        if 'email' in data:
            tenant = self.context['request'].tenant
            with tenant_context(tenant):
                if CustomUser.objects.filter(email=data['email'], tenant=tenant, is_deleted=False).exists():
                    raise serializers.ValidationError("Email already exists")
        return data

    def create(self, validated_data):
        tenant = self.context['request'].tenant
        profile_picture_file = validated_data.pop('profile_picture', None)
        password = validated_data.pop('password')  # Remove password from validated_data
        logger.debug(f"Creating user with email: {validated_data.get('email')}, tenant: {tenant.schema_name}")
        # Use create_user to ensure proper password hashing
        user = CustomUser.objects.create_user(
            email=validated_data.get('email'),
            password=password,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 'carer'),
            tenant=tenant,
            status=validated_data.get('status', 'pending'),
            is_locked=validated_data.get('is_locked', False),
            phone=validated_data.get('phone', ''),
            title=validated_data.get('title', ''),
            bio=validated_data.get('bio', ''),
            facebook_link=validated_data.get('facebook_link', ''),
            twitter_link=validated_data.get('twitter_link', ''),
            linkedin_link=validated_data.get('linkedin_link', '')
        )
        # Handle modules if provided
        if 'modules' in validated_data:
            user.modules.set(validated_data['modules'])
        # Handle profile picture
        if profile_picture_file:
            file_name = f"profile_pics/{user.id}/{uuid.uuid4().hex}_{profile_picture_file.name}"
            file_url = upload_to_supabase(profile_picture_file, file_name, content_type=profile_picture_file.content_type)
            user.profile_picture = file_name
            user.save()
        logger.info(f"User created successfully: {user.email} in tenant {tenant.schema_name}")
        return user

    def update(self, instance, validated_data):
        import inspect
        request = self.context.get('request') if hasattr(self, 'context') else None
        marker = uuid.uuid4().hex[:8]
        logger.debug(f"[UserSerializer.update][{marker}] --- CALLED ---")
        if request:
            logger.debug(f"[UserSerializer.update][{marker}] request.path: {getattr(request, 'path', None)}, method: {request.method}, content_type: {request.content_type}")
        logger.debug(f"[UserSerializer.update][{marker}] validated_data: {validated_data}")
        if 'profile_picture' in validated_data:
            logger.debug(f"[UserSerializer.update][{marker}] profile_picture type: {type(validated_data['profile_picture'])}, value: {validated_data['profile_picture']}")
        profile_picture_file = validated_data.pop('profile_picture', None)
        logger.debug(f"[UserSerializer.update][{marker}] profile_picture_file type: {type(profile_picture_file)}, value: {profile_picture_file}")
        # Handle password separately if provided
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
        instance = super().update(instance, validated_data)
        if profile_picture_file:
            if instance.profile_picture:
                storage_service = get_storage_service()
                try:
                    file_path = instance.profile_picture.name if hasattr(instance.profile_picture, 'name') else str(instance.profile_picture)
                    storage_service.delete_file(file_path)
                except Exception as e:
                    logger.error(f"Error deleting {getattr(instance.profile_picture, 'name', str(instance.profile_picture))} from Supabase: {e}")
            file_name = f"profile_pics/{instance.id}/{uuid.uuid4().hex}_{profile_picture_file.name}"
            file_url = upload_to_supabase(profile_picture_file, file_name, content_type=profile_picture_file.content_type)
            instance.profile_picture = file_name
            instance.save()
        logger.debug(f"[UserSerializer.update][{marker}] --- END ---")
        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.profile_picture:
            storage_service = get_storage_service()
            rep['profile_picture'] = storage_service.get_public_url(str(instance.profile_picture))
        else:
            rep['profile_picture'] = None
        return rep