from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_tenants.utils import tenant_context
from .models import Cart, Wishlist, Coupon
from .serializers import CartSerializer, CouponSerializer, WishlistSerializer
from courses.views import StandardResultsPagination, TenantBaseView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError

class CartViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Cart.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        tenant = self.request.tenant
        with tenant_context(tenant):
            serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            return Response(
                {"detail": "This course is already in your cart."},
                status=status.HTTP_400_BAD_REQUEST
            )

class WishlistViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Wishlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        tenant = self.request.tenant
        with tenant_context(tenant):
            serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            return Response(
                {"detail": "This course is already in your wishlist."},
                status=status.HTTP_400_BAD_REQUEST
            )

class CouponViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CouponSerializer
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Coupon.objects.filter(tenant=tenant)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_coupon(request):
    tenant = request.tenant
    code = request.data.get('code')
    now = timezone.now()
    with tenant_context(tenant):
        try:
            coupon = Coupon.objects.get(code=code, tenant=tenant, active=True, valid_from__lte=now, valid_to__gte=now)
            return Response({'valid': True, 'discount_percent': coupon.discount_percent})
        except Coupon.DoesNotExist:
            return Response({'valid': False, 'error': 'Invalid or expired coupon.'}, status=400)
