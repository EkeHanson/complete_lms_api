from .models import PaymentGateway
from .serializers import PaymentGatewaySerializer

import logging
from django.db import connection, transaction
from django_tenants.utils import tenant_context
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Count
from rest_framework.pagination import PageNumberPagination

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_tenants.utils import tenant_context
from .models import PaymentConfig, SiteConfig
from .serializers import PaymentConfigSerializer, SiteConfigSerializer
logger = logging.getLogger('payments')
from rest_framework.response import Response


class TenantBaseView(viewsets.GenericViewSet):
    """Base view to handle tenant schema setting and logging."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")


# List and manage available payment gateways
class PaymentGatewayViewSet(TenantBaseView, viewsets.ModelViewSet):

    queryset = PaymentGateway.objects.all()
    serializer_class = PaymentGatewaySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Optionally filter by active gateways only
        active = self.request.query_params.get('active')
        qs = PaymentGateway.objects.all()
        if active == 'true':
            qs = qs.filter(is_active=True)
        return qs.order_by('name')
    


    # GET /api/payment-gateways/ — returns all gateways.
    # GET /api/payment-gateways/?active=true — returns only active gateways.

    @action(detail=True, methods=['patch'], url_path='config', permission_classes=[IsAuthenticated])
    def update_config(self, request, pk=None):
        """Update the config details for a specific payment gateway."""
        tenant = request.tenant
        gateway = self.get_object()
        config_data = request.data.get('config')
        if not isinstance(config_data, dict):
            return Response({'detail': 'Config must be a dictionary.'}, status=status.HTTP_400_BAD_REQUEST)
        with tenant_context(tenant):
            payment_config = PaymentConfig.objects.first()
            if not payment_config:
                return Response({'detail': 'PaymentConfig not found.'}, status=status.HTTP_404_NOT_FOUND)
            updated = False
            for method_config in payment_config.configs:
                if method_config.get('method') == gateway.name:
                    method_config['config'] = config_data
                    updated = True
                    break
            if not updated:
                # If not found, add new config for this gateway
                payment_config.configs.append({
                    'method': gateway.name,
                    'config': config_data,
                    'isActive': gateway.is_active
                })
            payment_config.save()
            return Response({'detail': 'Config updated successfully.'}, status=status.HTTP_200_OK)


class SiteConfigViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tenant = request.tenant
        with tenant_context(tenant):
            config = SiteConfig.objects.first()
            if config:
                serializer = SiteConfigSerializer(config)
                return Response(serializer.data)
            return Response({}, status=status.HTTP_200_OK)

    def create(self, request):
        tenant = request.tenant
        with tenant_context(tenant):
            config = SiteConfig.objects.first()
            if config:
                # If config exists, update it instead of creating a new one
                serializer = SiteConfigSerializer(config, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            # If no config exists, create a new one
            serializer = SiteConfigSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        tenant = request.tenant
        with tenant_context(tenant):
            config = SiteConfig.objects.first()
            if not config:
                return Response(
                    {"detail": "No site configuration exists. Use POST to create one."},
                    status=status.HTTP_404_NOT_FOUND
                )
            serializer = SiteConfigSerializer(config, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        tenant = request.tenant
        with tenant_context(tenant):
            config = SiteConfig.objects.first()
            if not config:
                return Response(
                    {"detail": "No site configuration exists."},
                    status=status.HTTP_404_NOT_FOUND
                )
            config.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
