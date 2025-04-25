from rest_framework import serializers
from .models import User, UserActivity
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import exceptions
from django.utils import timezone
from .models import User, UserActivity

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        user = User.objects.filter(email=email).first()

        if user:
            # Check if account is suspended due to too many failed attempts
            if user.login_attempts >= 5 and user.status != 'suspended':
                user.status = 'suspended'
                user.save()
                
                # Log this activity
                UserActivity.objects.create(
                    user=user,
                    activity_type='account_suspended',
                    details='Account suspended due to too many failed login attempts',
                    status='failed'
                )
            
            if user.status == 'suspended':
                raise exceptions.AuthenticationFailed(
                    'Account suspended. Please contact admin.'
                )

        try:
            data = super().validate(attrs)
            
            # Reset login attempts on successful login
            if user and user.login_attempts > 0:
                user.login_attempts = 0
                user.last_login = timezone.now()
                user.save()
            
            # Log successful login
            UserActivity.objects.create(
                user=self.user,
                activity_type='login',
                details='Successful login',
                ip_address=self.context['request'].META.get('REMOTE_ADDR'),
                device_info=self.context['request'].META.get('HTTP_USER_AGENT'),
                status='success'
            )
            
            return data
            
        except exceptions.AuthenticationFailed:
            # Increment failed login attempts
            if user:
                user.login_attempts += 1
                user.save()
                
                # Log failed attempt
                UserActivity.objects.create(
                    user=user,
                    activity_type='login',
                    details='Failed login attempt',
                    ip_address=self.context['request'].META.get('REMOTE_ADDR'),
                    device_info=self.context['request'].META.get('HTTP_USER_AGENT'),
                    status='failed'
                )
                
                if user.login_attempts >= 3:
                    raise exceptions.AuthenticationFailed(
                        f'Invalid credentials. {5-user.login_attempts} attempts remaining before account suspension.'
                    )
            
            raise


class UserSerializer(serializers.ModelSerializer):
    last_login = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)
    class Meta:
        model = User
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def get_first_name(self, obj):
        return obj.get_first_name()
    
    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        return make_password(value)

class RoleStatsSerializer(serializers.Serializer):
    role = serializers.CharField()
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    pending = serializers.IntegerField()
    suspended = serializers.IntegerField()
    last_30_days = serializers.IntegerField()
    description = serializers.CharField()
    permissions = serializers.CharField()

class UserActivitySerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
    
    class Meta:
        model = UserActivity
        fields = '__all__'