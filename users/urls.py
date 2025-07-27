from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from .views import (CurrentUserView,ProfilePictureView,
    UserViewSet, FailedLoginViewSet, BlockedIPViewSet, VulnerabilityAlertViewSet, ComplianceReportViewSet,
    UserActivityViewSet, SocialLoginCallbackView, AdminUserCreateView, RegisterView, ProfileView, generate_cmvp_token,
 PasswordResetRequestView, PasswordResetConfirmView, TenantUsersListView)


router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'user-activities', UserActivityViewSet, basename='user-activities')
router.register(r'failed-logins', FailedLoginViewSet, basename='failed-logins')
router.register(r'blocked-ips', BlockedIPViewSet, basename='blocked-ips')
router.register(r'vulnerability-alerts', VulnerabilityAlertViewSet, basename='vulnerability-alerts')
router.register(r'compliance-reports', ComplianceReportViewSet, basename='compliance-reports')

urlpatterns = [
    path('', include(router.urls)),
    path('user/me/', CurrentUserView.as_view(), name='current-user'),
    path('users/<int:pk>/profile_picture/', ProfilePictureView.as_view(), name='profile-picture'),
    path('social/callback/', SocialLoginCallbackView.as_view(), name='social_callback'),
    path('admin/create/', AdminUserCreateView.as_view(), name='admin_user_create'),
    path('register/', RegisterView.as_view(), name='register'),
    path('api/profile/', ProfileView.as_view(), name='profile'),
    path('api/auth/', include('rest_framework.urls')),
    path('api/generate-cmvp-token/', generate_cmvp_token, name='generate-cmvp-token'),
    path('stats/', UserViewSet.as_view({'get': 'stats'}), name='user-stats'),
    path('recent-events/', UserActivityViewSet.as_view({'get': 'recent_events'}), name='recent-security-events'),
    path('dashboard/stats/', UserViewSet.as_view({'get': 'stats'}), name='dashboard-stats'),
    path('tenant-users/', TenantUsersListView.as_view(), name='tenant_users_list'),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)






