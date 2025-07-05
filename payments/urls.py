from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentConfigViewSet, SiteConfigViewSet

router = DefaultRouter()
router.register(r'payment-config', PaymentConfigViewSet, basename='payment-config')
router.register(r'site-config', SiteConfigViewSet, basename='site-config')

urlpatterns = [
    path('', include(router.urls)),
    path('payment-config', PaymentConfigViewSet.as_view({'get': 'list', 'post': 'create'}), name='payment-config'),
    path('payment-config/update', PaymentConfigViewSet.as_view({'patch': 'partial_update'}), name='payment-config-update'),
    path('payment-config/delete', PaymentConfigViewSet.as_view({'delete': 'destroy'}), name='payment-config-delete'),
    path('site-config', SiteConfigViewSet.as_view({'get': 'list', 'post': 'create'}), name='site-config'),
    path('site-config/update', SiteConfigViewSet.as_view({'patch': 'partial_update'}), name='site-config-update'),
    path('site-config/delete', SiteConfigViewSet.as_view({'delete': 'destroy'}), name='site-config-delete'),
]