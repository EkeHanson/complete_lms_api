from .views import CartViewSet, WishlistViewSet, CouponViewSet, apply_coupon
from rest_framework.routers import DefaultRouter
from django.urls import path, include
router = DefaultRouter()
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'wishlist', WishlistViewSet, basename='wishlist')
router.register(r'coupons', CouponViewSet, basename='coupon')

urlpatterns = router.urls + [
    path('apply-coupon/', apply_coupon, name='apply-coupon'),
]