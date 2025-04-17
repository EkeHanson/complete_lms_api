from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import routers
from users.views import UserViewSet, UserActivityViewSet, CustomTokenObtainPairView, RegisterView, ProfileView
# from messaging.views import MessageViewSet
# from groups.views import UserGroupViewSet
# from activitylog.views import ActivityLogViewSet

router = routers.DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'user-activities', UserActivityViewSet)
# router.register(r'messages', MessageViewSet)
# router.register(r'groups', UserGroupViewSet)
# router.register(r'activity-logs', ActivityLogViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/profile/', ProfileView.as_view(), name='profile'),
    path('api/auth/', include('rest_framework.urls')),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)