
from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import PaymentGatewayViewSet, SiteConfigViewSet

router = DefaultRouter()
router.register(r'site-currency', SiteConfigViewSet, basename='site-currency')
router.register(r'payment-gateways', PaymentGatewayViewSet, basename='payment-gateway')

urlpatterns = [
    path('', include(router.urls)),
]

#You can now update the configuration details for a payment gateway directly from the PaymentGateway API using the new endpoint:
# PATCH /api/payment-gateways/{id}/config/
# {
#   "config": {
#     ...your config fields...
#   }
# }