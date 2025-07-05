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
# In payments/views.py
from rest_framework.views import APIView
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



class PaymentConfigView(TenantBaseView):
    def get(self, request):
        tenant = request.tenant
        with tenant_context(tenant):
            # Replace with actual logic to fetch payment config
            config = {"payment_methods": ["Paystack", "Paypal"]}  # Example
            logger.info(f"[{tenant.schema_name}] Retrieved payment config")
            return Response(config)

class PaymentConfigViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tenant = request.tenant
        with tenant_context(tenant):
            config = PaymentConfig.objects.first()
            if config:
                serializer = PaymentConfigSerializer(config)
                return Response(serializer.data)
            return Response({}, status=status.HTTP_200_OK)

    def create(self, request):
        tenant = request.tenant
        with tenant_context(tenant):
            if PaymentConfig.objects.exists():
                return Response(
                    {"detail": "A payment configuration already exists. Use PATCH to update."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer = PaymentConfigSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        tenant = request.tenant
        with tenant_context(tenant):
            config = PaymentConfig.objects.first()
            if not config:
                return Response(
                    {"detail": "No payment configuration exists. Use POST to create one."},
                    status=status.HTTP_404_NOT_FOUND
                )
            serializer = PaymentConfigSerializer(config, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        tenant = request.tenant
        with tenant_context(tenant):
            config = PaymentConfig.objects.first()
            if not config:
                return Response(
                    {"detail": "No payment configuration exists."},
                    status=status.HTTP_404_NOT_FOUND
                )
            config.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


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
            if SiteConfig.objects.exists():
                return Response(
                    {"detail": "A site configuration already exists. Use PATCH to update."},
                    status=status.HTTP_400_BAD_REQUEST
                )
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
