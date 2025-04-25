from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('groups/api/', include('groups.urls')),  # Add this line
    path('messaging/api/', include('messaging.urls')),  # Add this line
    path('schedule/api/', include('schedule.urls')),  # Add this line
    path('adverts/api/', include('advert.urls')),  # Add this line
    path('users/', include('users.urls')),
    path('courses/', include('courses.urls')),
    path('forums/api/', include('forum.urls')),

    path('payments/', include('payments.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
