import logging
import uuid
from datetime import datetime, timedelta

import pandas as pd
from rest_framework import serializers
import requests
from django.db import transaction, connection
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.socialaccount.models import SocialAccount
from django_tenants.utils import tenant_context
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Count, Q
from core.models import Tenant
from .models import CustomUser, UserProfile, UserActivity
from .serializers import (
    UserSerializer,
    AdminUserCreateSerializer,
    UserActivitySerializer,
)

logger = logging.getLogger('users')

class TenantBaseView(generics.GenericAPIView):
    """Base view to handle tenant schema setting and logging."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise generics.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'page_size': self.get_page_size(self.request),
            'results': data
        })

class SocialLoginCallbackView(TenantBaseView, APIView):
    """Handle social login callback and issue JWT tokens."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.tenant
        user = request.user
        try:
            with tenant_context(tenant):
                social_account = SocialAccount.objects.get(user=user)
                refresh = RefreshToken.for_user(user)
                logger.info(f"[{tenant.schema_name}] Social login successful for user {user.email}")
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'tenant_id': tenant.id,
                    'tenant_schema': tenant.schema_name,
                })
        except SocialAccount.DoesNotExist:
            logger.warning(f"[{tenant.schema_name}] No social account found for user {user.email}")
            return Response({"detail": "Social account not found"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error in social login callback: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RegisterView(TenantBaseView, generics.CreateAPIView):
    """Register a new user in the tenant's schema."""
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[{tenant.schema_name}] User registration validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            user = serializer.save()
            UserActivity.objects.create(
                user=user,
                activity_type='user_registered',
                details=f'User "{user.email}" registered',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] User registered: {user.email}")
        return Response({
            'detail': 'User created successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)

class ProfileView(TenantBaseView, APIView):
    """Retrieve the authenticated user's profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                serializer = UserSerializer(request.user)
                logger.info(f"[{tenant.schema_name}] Profile retrieved for user {request.user.email}")
                return Response(serializer.data)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error retrieving profile for user {request.user.email}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LogoutView(TenantBaseView, APIView):
    """Handle user logout by blacklisting refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = request.tenant
        try:
            refresh_token = request.data.get("refresh") or request.COOKIES.get('refresh_token')
            if not refresh_token:
                logger.warning(f"[{tenant.schema_name}] No refresh token provided for logout by user {request.user.email}")
                return Response({"detail": "No refresh token provided"}, status=status.HTTP_400_BAD_REQUEST)
            with tenant_context(tenant):
                token = RefreshToken(refresh_token)
                token.blacklist()
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='user_logout',
                    details=f'User "{request.user.email}" logged out',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] User {request.user.email} logged out")
            response = Response({"detail": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            return response
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Logout error for user {request.user.email}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AdminUserCreateView(TenantBaseView, APIView):
    """Create an admin user in the tenant's schema."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        tenant = request.tenant
        serializer = AdminUserCreateSerializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Admin user creation validation failed: {str(e)}")
            raise
        try:
            with tenant_context(tenant), transaction.atomic():
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                UserActivity.objects.create(
                    user=user,
                    activity_type='admin_user_created',
                    details=f'Admin user "{user.email}" created by {request.user.email}',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Admin user created: {user.email}")
                return Response({
                    'detail': f'Admin user {user.email} created successfully',
                    'data': {
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'job_role': user.job_role,
                        'tenant_id': tenant.id,
                        'tenant_schema': tenant.schema_name,
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error creating admin user: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage users in the tenant's schema with filtering and statistics."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['role', 'status']
    search_fields = ['first_name', 'last_name', 'email']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = CustomUser.objects.filter(tenant=tenant, is_deleted=False).select_related('tenant')
            role = self.request.query_params.get('role')
            status = self.request.query_params.get('status')
            search = self.request.query_params.get('search')
            date_from = self.request.query_params.get('date_from')
            date_to = self.request.query_params.get('date_to')
            if role and role != 'all':
                queryset = queryset.filter(role=role)
            if status and status != 'all':
                queryset = queryset.filter(status=status)
            if search:
                queryset = queryset.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(email__icontains=search)
                )
            if date_from:
                try:
                    queryset = queryset.filter(signup_date__gte=datetime.fromisoformat(date_from))
                except ValueError:
                    logger.warning(f"[{tenant.schema_name}] Invalid date_from format: {date_from}")
                    raise serializers.ValidationError("Invalid date_from format")
            if date_to:
                try:
                    queryset = queryset.filter(signup_date__lte=datetime.fromisoformat(date_to))
                except ValueError:
                    logger.warning(f"[{tenant.schema_name}] Invalid date_to format: {date_to}")
                    raise serializers.ValidationError("Invalid date_to format")
            logger.debug(f"[{tenant.schema_name}] User query: {queryset.query}")
            return queryset.order_by('-signup_date')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        if request.user.role != 'admin' and not request.user.is_superuser:
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted to create user")
            return Response({"detail": "Only admins or superusers can create users"}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[{tenant.schema_name}] User creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            user = serializer.save()
            UserActivity.objects.create(
                user=user,
                activity_type='user_created',
                details=f'User "{user.email}" created by {request.user.email}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] User created: {user.email}")
            return Response({
                'detail': 'User created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        user = self.get_object()
        if request.user.role != 'admin' and not request.user.is_superuser and request.user != user:
            logger.warning(f"[{tenant.schema_name}] User {request.user.email} attempted to update user {user.email}")
            return Response({"detail": "You do not have permission to update this user"}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(user, data=request.data, partial=kwargs.get('partial', False))
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[{tenant.schema_name}] User update validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            serializer.save()
            UserActivity.objects.create(
                user=user,
                activity_type='user_updated',
                details=f'User "{user.email}" updated by {request.user.email}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] User updated: {user.email}")
            return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        user = self.get_object()
        if request.user.role != 'admin' and not request.user.is_superuser:
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted to delete user {user.email}")
            return Response({"detail": "Only admins or superusers can delete users"}, status=status.HTTP_403_FORBIDDEN)
        with tenant_context(tenant), transaction.atomic():
            user.delete_account(reason="Deleted via API")
            UserActivity.objects.create(
                user=user,
                activity_type='user_deleted',
                details=f'User "{user.email}" soft-deleted by {request.user.email}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] User soft-deleted: {user.email}")
            return Response({"detail": "User deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                stats = {
                    'total_users': CustomUser.objects.filter(tenant=tenant, is_deleted=False).count(),
                    'active_users': CustomUser.objects.filter(tenant=tenant, is_deleted=False, status='active').count(),
                    'new_signups': CustomUser.objects.filter(tenant=tenant, is_deleted=False, signup_date__gte=thirty_days_ago).count(),
                    'suspicious_activity': CustomUser.objects.filter(tenant=tenant, is_deleted=False, login_attempts__gt=3).count(),
                }
                logger.info(f"[{tenant.schema_name}] User stats retrieved")
                return Response(stats)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error retrieving user stats: {str(e)}", exc_info=True)
            return Response({"detail": "Error retrieving user stats"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def role_stats(self, request):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                roles = CustomUser.objects.filter(tenant=tenant, is_deleted=False).values('role').annotate(
                    total=Count('id'),
                    active=Count('id', filter=Q(status='active')),
                    pending=Count('id', filter=Q(status='pending')),
                    suspended=Count('id', filter=Q(status='suspended'))
                )
                thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                role_info = {
                    'admin': {'description': 'Full system access', 'permissions': 'Can manage all users, modules, and system settings'},
                    'hr': {'description': 'Manages human resources tasks', 'permissions': 'Can manage staff, job roles, and HR-related modules'},
                    'carer': {'description': 'Provides care services', 'permissions': 'Can access client data and care-related modules'},
                    'client': {'description': 'Receives care services', 'permissions': 'Can view personal care plans and communicate with carers'},
                    'family': {'description': 'Family members of clients', 'permissions': 'Can view client updates and communicate with carers'},
                    'auditor': {'description': 'Audits system activities', 'permissions': 'Can view audit logs and compliance reports'},
                    'tutor': {'description': 'Provides training', 'permissions': 'Can manage training modules and learner progress'},
                    'assessor': {'description': 'Assesses training outcomes', 'permissions': 'Can evaluate assessments and provide feedback'},
                    'iqa': {'description': 'Internal Quality Assurer', 'permissions': 'Can review assessment quality and compliance'},
                    'eqa': {'description': 'External Quality Assurer', 'permissions': 'Can perform external quality checks and audits'}
                }
                result = [
                    {
                        'role': role['role'],
                        'total': role['total'],
                        'active': role['active'],
                        'pending': role['pending'],
                        'suspended': role['suspended'],
                        'last_30_days': CustomUser.objects.filter(
                            tenant=tenant, is_deleted=False, role=role['role'], signup_date__gte=thirty_days_ago
                        ).count(),
                        'description': role_info.get(role['role'], {}).get('description', ''),
                        'permissions': role_info.get(role['role'], {}).get('permissions', '')
                    } for role in roles
                ]
                logger.info(f"[{tenant.schema_name}] Role stats retrieved")
                return Response(result)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error retrieving role stats: {str(e)}", exc_info=True)
            return Response({"detail": "Error retrieving role stats"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def bulk_upload(self, request):
        tenant = request.tenant
        if request.user.role != 'admin' and not request.user.is_superuser:
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted bulk upload")
            return Response({"detail": "Only admins or superusers can perform bulk uploads"}, status=status.HTTP_403_FORBIDDEN)
        if 'file' not in request.FILES:
            logger.warning(f"[{tenant.schema_name}] No file uploaded for bulk user upload")
            return Response({"detail": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        file = request.FILES['file']
        valid_extensions = ['.xlsx', '.xls', '.csv']
        if not any(file.name.lower().endswith(ext) for ext in valid_extensions):
            logger.warning(f"[{tenant.schema_name}] Invalid file type uploaded: {file.name}")
            return Response({"detail": "Invalid file type", "allowed_types": valid_extensions}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with tenant_context(tenant), transaction.atomic():
                df = pd.read_csv(file) if file.name.lower().endswith('.csv') else pd.read_excel(file)
                required_columns = ['firstName', 'lastName', 'email', 'password', 'role']
                if not all(col in df.columns for col in required_columns):
                    logger.warning(f"[{tenant.schema_name}] Missing required columns in uploaded file: {file.name}")
                    return Response({"detail": "Missing required columns", "required_columns": required_columns}, status=status.HTTP_400_BAD_REQUEST)
                created_users = []
                errors = []
                for index, row in df.iterrows():
                    try:
                        user_data = {
                            'email': row['email'],
                            'password': row['password'],
                            'first_name': row['firstName'],
                            'last_name': row['lastName'],
                            'role': row['role'].lower(),
                            'status': row.get('status', 'active').lower(),
                            'tenant': tenant
                        }
                        for field in ['phone', 'birth_date', 'title', 'bio']:
                            if field in row and pd.notna(row[field]):
                                user_data[field] = row[field]
                        user = CustomUser.objects.create_user(**user_data)
                        UserProfile.objects.create(user=user)
                        created_users.append({'id': user.id, 'email': user.email, 'name': user.get_full_name()})
                    except Exception as e:
                        errors.append({'row': index + 2, 'error': str(e), 'data': dict(row)})
                UserActivity.objects.bulk_create([
                    UserActivity(
                        user=CustomUser.objects.get(id=user['id']),
                        activity_type='user_management',
                        details=f'New user created with email: {user["email"]}',
                        status='success'
                    ) for user in created_users
                ])
                logger.info(f"[{tenant.schema_name}] Bulk uploaded {len(created_users)} users")
                return Response({
                    'detail': f'Created {len(created_users)} users',
                    'created_count': len(created_users),
                    'created_users': created_users,
                    'error_count': len(errors),
                    'errors': errors
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error processing bulk upload: {str(e)}", exc_info=True)
            return Response({"detail": f"Error processing file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def impersonate(self, request, pk=None):
        tenant = request.tenant
        if not request.user.is_superuser:
            logger.warning(f"[{tenant.schema_name}] Non-superuser {request.user.email} attempted to impersonate")
            return Response({"detail": "Only superusers can impersonate"}, status=status.HTTP_403_FORBIDDEN)
        try:
            with tenant_context(tenant):
                user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
                token = RefreshToken.for_user(user)
                UserActivity.objects.create(
                    user=user,
                    activity_type='user_impersonated',
                    details=f'User "{user.email}" impersonated by {request.user.email}',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Superuser {request.user.email} impersonated user {user.email}")
                return Response({'token': str(token.access_token)})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error impersonating user with pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserActivityViewSet(TenantBaseView, viewsets.ReadOnlyModelViewSet):
    """Retrieve user activity logs for a tenant."""
    serializer_class = UserActivitySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['activity_type', 'status']
    search_fields = ['user__email', 'details']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = UserActivity.objects.filter(user__tenant=tenant).select_related('user').order_by('-timestamp')
            user_id = self.request.query_params.get('user_id')
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            logger.debug(f"[{tenant.schema_name}] User activity query: {queryset.query}")
            return queryset

    def list(self, request, *args, **kwargs):
        tenant = request.tenant
        try:
            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page if page is not None else queryset, many=True)
            logger.info(f"[{tenant.schema_name}] Retrieved {queryset.count()} user activity records")
            return self.get_paginated_response(serializer.data) if page is not None else Response({
                'detail': f'Retrieved {queryset.count()} user activity record(s)',
                'data': serializer.data
            })
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error listing user activities: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserProfileUpdateView(TenantBaseView, generics.GenericAPIView):
    """Update the authenticated user's profile."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = request.tenant
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Profile update validation failed for user {user.email}: {str(e)}")
            raise
        try:
            with tenant_context(tenant), transaction.atomic():
                updated_fields = {k: v for k, v in serializer.validated_data.items() if k in [
                    'first_name', 'last_name', 'phone', 'birth_date', 'profile_picture',
                    'bio', 'facebook_link', 'twitter_link', 'linkedin_link', 'title'
                ]}
                user.update_profile(updated_fields)
                UserActivity.objects.create(
                    user=user,
                    activity_type='profile_updated',
                    details=f'User "{user.email}" updated profile',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Profile updated for user {user.email}")
                return Response({
                    'detail': 'Profile updated successfully',
                    'data': UserSerializer(user, context={'request': request}).data
                })
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error updating profile for user {user.email}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserAccountSuspendView(TenantBaseView, generics.GenericAPIView):
    """Suspend a user account in the tenant's schema."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
                if user.status == 'suspended':
                    logger.warning(f"[{tenant.schema_name}] User {user.email} already suspended")
                    return Response({"detail": "User is already suspended"}, status=status.HTTP_400_BAD_REQUEST)
                with transaction.atomic():
                    user.suspend_account(reason="Suspended via API")
                    UserActivity.objects.create(
                        user=user,
                        activity_type='user_suspended',
                        details=f'User "{user.email}" suspended by {request.user.email}',
                        status='success'
                    )
                    logger.info(f"[{tenant.schema_name}] User {user.email} suspended")
                    return Response({"detail": f"User {user.email} suspended successfully"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error suspending user with pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserAccountActivateView(TenantBaseView, generics.GenericAPIView):
    """Activate a user account in the tenant's schema."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
                if user.status == 'active':
                    logger.warning(f"[{tenant.schema_name}] User {user.email} already active")
                    return Response({"detail": "User is already active"}, status=status.HTTP_400_BAD_REQUEST)
                with transaction.atomic():
                    user.activate_account()
                    UserActivity.objects.create(
                        user=user,
                        activity_type='user_activated',
                        details=f'User "{user.email}" activated by {request.user.email}',
                        status='success'
                    )
                    logger.info(f"[{tenant.schema_name}] User {user.email} activated")
                    return Response({"detail": f"User {user.email} activated successfully"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error activating user with pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserAccountBulkDeleteView(TenantBaseView, generics.GenericAPIView):
    """Bulk soft-delete users in the tenant's schema."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        tenant = request.tenant
        ids = request.data.get('ids', [])
        if not isinstance(ids, list):
            logger.warning(f"[{tenant.schema_name}] Invalid input for bulk delete: ids must be a list")
            return Response({"detail": "ids must be a list"}, status=status.HTTP_400_BAD_REQUEST)
        if not ids:
            logger.warning(f"[{tenant.schema_name}] No user IDs provided for bulk delete")
            return Response({"detail": "No user IDs provided"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with tenant_context(tenant), transaction.atomic():
                users = CustomUser.objects.filter(id__in=ids, tenant=tenant, is_deleted=False)
                if not users.exists():
                    logger.warning(f"[{tenant.schema_name}] No active users found for IDs {ids}")
                    return Response({"detail": "No active users found"}, status=status.HTTP_404_NOT_FOUND)
                deleted_count = 0
                for user in users:
                    user.delete_account(reason="Bulk deleted via API")
                    UserActivity.objects.create(
                        user=user,
                        activity_type='user_deleted',
                        details=f'User "{user.email}" soft-deleted by {request.user.email}',
                        status='success'
                    )
                    deleted_count += 1
                logger.info(f"[{tenant.schema_name}] Soft-deleted {deleted_count} users")
                return Response({"detail": f"Soft-deleted {deleted_count} user(s)"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error during bulk delete of users: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def generate_cmvp_token(request):
    """Generate a CMVP token for magic link login."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        logger.error("No tenant associated with the request")
        return JsonResponse({"detail": "Tenant not found"}, status=400)
    try:
        with tenant_context(tenant):
            user_email = "ekenehanson@gmail.com"  # Should be dynamically obtained
            token = str(uuid.uuid4())
            response = requests.post(
                "http://127.0.0.1:9091/api/accounts/auth/api/register-token/",
                json={"token": token, "user_email": user_email}
            )
            if response.status_code == 201:
                magic_link = f"http://localhost:3000/MagicLoginPage?token={token}"
                logger.info(f"[{tenant.schema_name}] CMVP token generated for user {user_email}")
                return JsonResponse({"magic_link": magic_link})
            logger.warning(f"[{tenant.schema_name}] CMVP token registration failed for user {user_email}: {response.text}")
            return JsonResponse({"detail": "Token registration failed"}, status=400)
    except Exception as e:
        logger.error(f"[{tenant.schema_name}] Error generating CMVP token: {str(e)}", exc_info=True)
        return JsonResponse({"detail": str(e)}, status=500)