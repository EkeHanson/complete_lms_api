# payments/views.py
from rest_framework import viewsets, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from .models import PaymentConfig, SiteConfig
from .serializers import PaymentConfigSerializer, SiteConfigSerializer

class PaymentConfigViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    def list(self, request):
        config = PaymentConfig.objects.first()
        if config:
            serializer = PaymentConfigSerializer(config)
            return Response(serializer.data)
        return Response({}, status=status.HTTP_200_OK)

    def create(self, request):
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
        config = PaymentConfig.objects.first()
        if not config:
            return Response(
                {"detail": "No payment configuration exists."},
                status=status.HTTP_404_NOT_FOUND
            )
        config.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class SiteConfigViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    def list(self, request):
        config = SiteConfig.objects.first()
        if config:
            serializer = SiteConfigSerializer(config)
            return Response(serializer.data)
        return Response({}, status=status.HTTP_200_OK)

    def create(self, request):
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
        config = SiteConfig.objects.first()
        if not config:
            return Response(
                {"detail": "No site configuration exists."},
                status=status.HTTP_404_NOT_FOUND
            )
        config.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)