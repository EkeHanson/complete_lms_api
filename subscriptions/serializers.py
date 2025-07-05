# apps/subscriptions/serializers.py
from rest_framework import serializers
from .models import Subscription
from core.models import Tenant

class SubscriptionSerializer(serializers.ModelSerializer):
    tenant = serializers.SlugRelatedField(
        slug_field='schema_name',
        queryset=Tenant.objects.all()
    )

    class Meta:
        model = Subscription
        fields = ['id', 'tenant', 'module', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']