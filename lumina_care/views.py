import logging
from django.db import connection
from django_tenants.utils import tenant_context, get_public_schema_name
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken
from rest_framework import status, exceptions
from django.conf import settings
from core.models import Domain, Tenant
from users.models import CustomUser, UserActivity, FailedLogin
from users.serializers import CustomUserSerializer
from rest_framework import serializers

logger = logging.getLogger('lumina_care')

class HeaderJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning(f"[{request.path}] No or invalid Authorization header")
            return None
        try:
            access_token = auth_header.split(' ')[1]
            validated_token = self.get_validated_token(access_token)
            tenant_id = validated_token.get('tenant_id')
            tenant_schema = validated_token.get('tenant_schema')
            if not tenant_id or not tenant_schema:
                logger.warning(f"[{request.path}] Missing tenant_id or tenant_schema in token: {validated_token}")
                return None
            tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
            connection.set_schema(tenant.schema_name)
            user = self.get_user(validated_token)
            logger.debug(f"[{request.path}] Authenticated user: {user.email}, Tenant: {tenant.schema_name}")
            return (user, validated_token)
        except Exception as e:
            logger.error(f"[{request.path}] Token validation failed: {str(e)}", exc_info=True)
            return None

class TenantBaseView(APIView):
    """Base view to handle tenant schema setting and logging."""
    authentication_classes = [HeaderJWTAuthentication]
    
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            logger.error("No tenant associated with the request")
            raise exceptions.ValidationError({"detail": "Tenant not found."})
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")



class CustomTokenSerializer(TokenObtainPairSerializer):
    """Custom token serializer for tenant-aware authentication with login attempt tracking."""
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            logger.warning("Missing email or password in token request")
            raise serializers.ValidationError({
                "email": "Email is required.",
                "password": "Password is required."
            })

        try:
            email_domain = email.split('@')[1].lower()
            logger.debug(f"[{email_domain}] Email domain extracted")
        except IndexError:
            logger.warning("Invalid email format provided")
            raise serializers.ValidationError({"email": "Invalid email format."})

        domain = Domain.objects.filter(domain=email_domain).first()
        if not domain:
            logger.error(f"No domain found for: {email_domain}")
            raise serializers.ValidationError({"email": "No tenant found for this email domain."})

        tenant = domain.tenant
        logger.info(f"[{tenant.schema_name}] Authenticating user: {email}")

        with tenant_context(tenant):
            user = CustomUser.objects.filter(email=email).first()
            if not user:
                logger.error(f"[{tenant.schema_name}] User not found: {email}")
                raise exceptions.AuthenticationFailed({"detail": "Invalid credentials."})

            if user.status == 'suspended':
                logger.warning(f"[{tenant.schema_name}] Suspended user attempted login: {email}")
                raise exceptions.AuthenticationFailed({"detail": "Account suspended. Please contact admin."})

            if not user.check_password(password):
                user.increment_login_attempts()
                UserActivity.objects.create(
                    user=user,
                    activity_type='login',
                    details=f'Failed login attempt for {email}',
                    ip_address=self.context['request'].META.get('REMOTE_ADDR'),
                    device_info=self.context['request'].META.get('HTTP_USER_AGENT'),
                    status='failed'
                )
                attempts_remaining = 5 - user.login_attempts
                logger.warning(f"[{tenant.schema_name}] Invalid password for {email}. {attempts_remaining} attempts remaining")
                if user.login_attempts >= 5:
                    user.status = 'suspended'
                    user.save()

                    FailedLogin.objects.create(
                        user=user,  # Associate with the CustomUser instance
                        username=email,
                        ip_address=self.context['request'].META.get('REMOTE_ADDR'),
                        attempts=user.login_attempts,
                        status='active'  # Use 'active' as per model choices
                    )
                    
                    UserActivity.objects.create(
                        user=user,
                        activity_type='account_suspended',
                        details='Account suspended due to too many failed login attempts',
                        status='failed'
                    )
                    raise exceptions.AuthenticationFailed({"detail": "Account suspended due to too many failed login attempts."})
                raise exceptions.AuthenticationFailed({
                    "detail": f"Invalid credentials. {attempts_remaining} attempts remaining before account suspension.",
                    "remaining_attempts": attempts_remaining
                })

            if not user.is_active:
                logger.error(f"[{tenant.schema_name}] Inactive user: {email}")
                raise exceptions.AuthenticationFailed({"detail": "User account is inactive."})

            try:
                data = super().validate(attrs)
                user.reset_login_attempts()
                user.last_login_ip = self.context['request'].META.get('REMOTE_ADDR')
                user.last_login_device = self.context['request'].META.get('HTTP_USER_AGENT')
                user.save()

                refresh = RefreshToken.for_user(user)
                refresh['tenant_id'] = str(tenant.id)
                refresh['tenant_schema'] = tenant.schema_name
                data['refresh'] = str(refresh)
                data['access'] = str(refresh.access_token)
                data['tenant_id'] = str(tenant.id)
                data['tenant_schema'] = tenant.schema_name
                data['user'] = CustomUserSerializer(user).data

                UserActivity.objects.create(
                    user=user,
                    activity_type='login',
                    details=f'Successful login for {email}',
                    ip_address=self.context['request'].META.get('REMOTE_ADDR'),
                    device_info=self.context['request'].META.get('HTTP_USER_AGENT'),
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Successful login for user: {email}")
                return data
            except exceptions.AuthenticationFailed as e:
                logger.error(f"[{tenant.schema_name}] Authentication failed: {str(e)}")
                raise





class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """Custom token refresh serializer for tenant-aware token refresh."""
    def validate(self, attrs):
        try:
            refresh = RefreshToken(attrs['refresh'])
        except Exception as e:
            logger.error(f"Invalid refresh token: {str(e)}")
            raise serializers.ValidationError({"refresh": "Invalid refresh token."})

        tenant_id = refresh.get('tenant_id')
        tenant_schema = refresh.get('tenant_schema')
        if not tenant_id or not tenant_schema:
            logger.warning("Refresh token missing tenant info")
            raise serializers.ValidationError({"refresh": "Invalid token: tenant info missing."})

        try:
            tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: id={tenant_id}, schema={tenant_schema}")
            raise serializers.ValidationError({"refresh": "Invalid tenant."})

        with tenant_context(tenant):
            try:
                data = super().validate(attrs)
                data['tenant_id'] = str(tenant.id)
                data['tenant_schema'] = tenant.schema_name
                logger.info(f"[{tenant.schema_name}] Token refreshed successfully")
                return data
            except Exception as e:
                logger.error(f"[{tenant.schema_name}] Token refresh failed: {str(e)}")
                raise serializers.ValidationError({"refresh": "Token refresh failed."})

class TokenObtainPairView(TenantBaseView, TokenObtainPairView):
    serializer_class = CustomTokenSerializer

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            response['Access-Control-Allow-Origin'] = settings.FRONTEND_URL
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Vary'] = 'Origin'
            logger.info(f"[{request.tenant.schema_name}] Token obtained successfully")
            return response
        except exceptions.AuthenticationFailed as e:
            logger.error(f"[{request.tenant.schema_name}] Authentication failed: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"[{request.tenant.schema_name}] Error obtaining token: {str(e)}", exc_info=True)
            return Response({"detail": f"Something went wrong. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TokenRefreshView(TenantBaseView, TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            response = Response({
                "access": data.get('access'),
                "refresh": data.get('refresh'),
                "detail": "Token refreshed successfully"
            })
            response['Access-Control-Allow-Origin'] = settings.FRONTEND_URL
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Vary'] = 'Origin'
            logger.info(f"[{request.tenant.schema_name}] Token refresh successful")
            return response
        except Exception as e:
            logger.error(f"[{request.tenant.schema_name}] Token refresh failed: {str(e)}", exc_info=True)
            return Response({"detail": f"Token refresh failed: {str(e)}"}, status=status.HTTP_401_UNAUTHORIZED)

class TokenValidateView(TenantBaseView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [HeaderJWTAuthentication]

    def get(self, request):
        try:
            logger.info(f"[{request.tenant.schema_name}] Validating token for user: {request.user.email}")
            return Response({
                'user': CustomUserSerializer(request.user).data,
                'tenant_id': str(request.tenant.id),
                'tenant_schema': request.tenant.schema_name
            })
        except Exception as e:
            logger.error(f"[{request.tenant.schema_name}] Token validation failed: {str(e)}", exc_info=True)
            return Response({'detail': f'Invalid token: {str(e)}'}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(TenantBaseView):
    def post(self, request):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            logger.error("No tenant associated with logout request")
            return Response({"detail": "Tenant not found"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                    logger.info(f"[{tenant.schema_name}] Refresh token blacklisted for user: {request.user.email if request.user.is_authenticated else 'anonymous'}")
                except Exception as e:
                    logger.warning(f"[{tenant.schema_name}] Failed to blacklist refresh token: {str(e)}")
            with tenant_context(tenant):
                UserActivity.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    activity_type='logout',
                    details='User logged out',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    device_info=request.META.get('HTTP_USER_AGENT'),
                    status='success'
                )
            logger.info(f"[{tenant.schema_name}] Logout successful")
            return Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Logout error: {str(e)}", exc_info=True)
            return Response({"detail": f"Logout failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)