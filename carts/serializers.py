from rest_framework import serializers
from .models import Cart, Wishlist, Coupon
from courses.serializers import CourseSerializer

class CartSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    course = CourseSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Cart._meta.get_field('course').related_model.objects.all(),
        source='course',
        write_only=True
    )

    class Meta:
        model = Cart
        fields = ['id', 'user', 'course', 'course_id', 'added_at']

class WishlistSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    course = CourseSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Wishlist._meta.get_field('course').related_model.objects.all(),
        source='course',
        write_only=True
    )

    class Meta:
        model = Wishlist
        fields = ['id', 'user', 'course', 'course_id', 'added_at']

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['id', 'code', 'discount_percent', 'valid_from', 'valid_to', 'active']