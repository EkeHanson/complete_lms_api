import logging
from django.db import connection
from django_tenants.utils import tenant_context
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken
from rest_framework import status, exceptions
from django.conf import settings
from core.models import Domain, Tenant
from users.models import CustomUser, UserActivity
from users.serializers import CustomUserSerializer
from rest_framework import serializers

logger = logging.getLogger(__name__)
import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_tenants.utils import tenant_context
from core.models import Tenant
from django.db import connection

logger = logging.getLogger('lumina_care')

class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        access_token = request.COOKIES.get('access_token')
        if not access_token:
            logger.warning(f"[{request.path}] No access token in cookies")
            return None
        try:
            validated_token = self.get_validated_token(access_token)
            tenant_id = validated_token.get('tenant_id')
            tenant_schema = validated_token.get('tenant_schema')
            if not tenant_id or not tenant_schema:
                logger.warning(f"[{request.path}] Missing tenant_id or tenant_schema in token")
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
    authentication_classes = [CookieJWTAuthentication]
    
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
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

                # Add explicit null checks
        if not email or not password:
            logger.warning("Missing email or password in token request")
            raise serializers.ValidationError({
                "email": "Email is required.",
                "password": "Password is required."
            })

        # if not email:
        #     logger.warning("Missing email in token request")
        #     raise serializers.ValidationError({"email": "Email is required."})

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
                    UserActivity.objects.create(
                        user=user,
                        activity_type='account_suspended',
                        details='Account suspended due to too many failed login attempts',
                        status='failed'
                    )
                    raise exceptions.AuthenticationFailed({"detail": "Account suspended due to too many failed login attempts."})
                raise exceptions.AuthenticationFailed({
                    "detail": f"Invalid credentials. {attempts_remaining} attempts remaining before account suspension."
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

class CookieTokenObtainPairView(TenantBaseView, TokenObtainPairView):
    serializer_class = CustomTokenSerializer

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            data = response.data
            access_token = data.pop('access', None)
            refresh_token = data.pop('refresh', None)

            print("access_token :",  access_token)
            print("refresh_token: ", refresh_token)

            if access_token and refresh_token:
                secure = not settings.DEBUG
                samesite = 'None'
                response.set_cookie(
                    key='access_token',
                    value=access_token,
                    httponly=True,
                    secure=secure,
                    samesite=samesite,
                    max_age=60 * 60 * 2,
                    path='/',
                    domain=None
                )
                response.set_cookie(
                    key='refresh_token',
                    value=refresh_token,
                    httponly=True,
                    secure=secure,
                    samesite=samesite,
                    max_age=60 * 60 * 24 * 7,
                    path='/',
                    domain=None
                )
                logger.info(f"[{request.tenant.schema_name}] Set-Cookie headers sent: access_token={access_token[:10]}..., refresh_token={refresh_token[:10]}..., secure={secure}, samesite={samesite}")
                logger.debug(f"[{request.tenant.schema_name}] Full response headers: {dict(response.headers)}")
            else:
                logger.warning(f"[{request.tenant.schema_name}] Token generation failed: no access or refresh token")
                return Response({"detail": "Failed to generate tokens"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{request.tenant.schema_name}] Error obtaining token: {str(e)}", exc_info=True)
            return Response({"detail": f"Error obtaining token: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)       
class CookieTokenRefreshView(APIView):
    def options(self, request, *args, **kwargs):
        return Response(status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        logger.debug(f"Refresh token received: {refresh_token[:10]}... (truncated)")
        if not refresh_token:
            logger.warning("No refresh token provided in cookies")
            return Response({"detail": "No refresh token provided"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            untyped_token = UntypedToken(refresh_token)
            tenant_id = untyped_token.payload.get('tenant_id')
            logger.debug(f"Tenant ID from token: {tenant_id}")
            if not tenant_id:
                logger.error("Missing tenant_id in refresh token")
                return Response({"detail": "Missing tenant_id in token"}, status=status.HTTP_401_UNAUTHORIZED)
            tenant = Tenant.objects.get(id=tenant_id)
            connection.set_schema(tenant.schema_name)
            logger.debug(f"[{tenant.schema_name}] Schema set for token refresh")
            token = RefreshToken(refresh_token)
            user_id = token.get('user_id')
            logger.debug(f"User ID from token: {user_id}")
            user = CustomUser.objects.get(id=user_id)
            new_refresh = RefreshToken.for_user(user)
            new_access = new_refresh.access_token
            new_refresh['tenant_id'] = str(tenant.id)
            new_refresh['tenant_schema'] = tenant.schema_name
            new_access['tenant_id'] = str(tenant.id)
            new_access['tenant_schema'] = tenant.schema_name
            response = Response({
                "access": str(new_access),
                "tenant_id": str(tenant.id),
                "tenant_schema": tenant.schema_name
            })
            secure = not settings.DEBUG
            samesite = 'None'
            response.set_cookie(
                'access_token',
                str(new_access),
                httponly=True,
                secure=secure,
                samesite=samesite,
                max_age=60 * 60 * 2,
                path='/',
                domain=None
            )
            response.set_cookie(
                'refresh_token',
                str(new_refresh),
                httponly=True,
                secure=secure,
                samesite=samesite,
                max_age=60 * 60 * 24 * 7,
                path='/',
                domain=None
            )
            logger.info(f"[{tenant.schema_name}] Token refreshed successfully for user_id: {user_id}")
            return response
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}", exc_info=True)
            return Response({"detail": f"Token refresh failed: {str(e)}"}, status=status.HTTP_401_UNAUTHORIZED)

class TokenValidateView(TenantBaseView, APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

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
            return Response({'detail': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        

class LogoutView(TenantBaseView, APIView):
    """Handle user logout by blacklisting the refresh token."""
    def post(self, request):
        tenant = request.tenant
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                    logger.info(f"[{tenant.schema_name}] Refresh token blacklisted for user: {request.user.email if request.user.is_authenticated else 'anonymous'}")
                except Exception as e:
                    logger.warning(f"[{tenant.schema_name}] Failed to blacklist refresh token: {str(e)}")
            response = Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)
            response.delete_cookie('access_token', path='/')
            response.delete_cookie('refresh_token', path='/')
            with tenant_context(tenant):
                UserActivity.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    activity_type='logout',
                    details='User logged out',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    device_info=request.META.get('HTTP_USER_AGENT'),
                    status='success'
                )
            return response
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Logout error: {str(e)}", exc_info=True)
            return Response({"detail": f"Logout failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)