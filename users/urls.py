
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    UserViewSet,
    UserActivityViewSet,
    SocialLoginCallbackView,
    AdminUserCreateView,
    RegisterView,
    ProfileView,
    generate_cmvp_token,
)

# Initialize a single router instance
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'user-activities', UserActivityViewSet, basename='user-activities')

urlpatterns = [
    path('', include(router.urls)),
    path('social/callback/', SocialLoginCallbackView.as_view(), name='social_callback'),
    path('admin/create/', AdminUserCreateView.as_view(), name='admin_user_create'),
    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/profile/', ProfileView.as_view(), name='profile'),
    path('api/auth/', include('rest_framework.urls')),
    path('api/generate-cmvp-token/', generate_cmvp_token, name='generate-cmvp-token'),
    path('stats/', UserViewSet.as_view({'get': 'stats'}), name='user-stats'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


