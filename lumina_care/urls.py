from django.urls import path, include
from django.contrib import admin
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import TokenObtainPairView, TokenRefreshView, TokenValidateView, LogoutView

def root_view(request):
    return JsonResponse({
        'status': 'success',
        'message': 'Welcome to LUMINA Care OS API',
        'endpoints': {
            'tenants': '/api/tenant/tenants/',
            'users': '/api/users/',
            'docs': '/api/docs/',
            'token': '/api/token/',
            'schedules': '/schedule/',
            'courses': '/api/courses/',
            'messaging': '/messaging/',
            'groups': '/api/groups/',
            'adverts': '/adverts/',
            'payments': '/payments/',
            'forums': '/api/forums/'
        }
    })

urlpatterns = [
    path('', root_view, name='root'),
    path('api/tenant/', include('core.urls')),
    path('api/users/', include('users.urls')),
    path('api/activitylog/', include('activitylog.urls')),
    path('api/courses/', include('courses.urls')),
    path('api/schedule/', include('schedule.urls')),
    path('api/messaging/', include('messaging.urls')),
    path('api/ai_chat/', include('ai_chat.urls')),
    path('api/groups/', include('groups.urls')),
    path('adverts/', include('advert.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/forums/', include('forum.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/validate/', TokenValidateView.as_view(), name='token_validate'),
    path('api/logout/', LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('accounts/', include('allauth.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


