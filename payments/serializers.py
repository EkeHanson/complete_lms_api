# payments/serializers.py
from rest_framework import serializers
from .models import PaymentConfig, SiteConfig

class PaymentMethodConfigSerializer(serializers.Serializer):
    method = serializers.CharField(max_length=50)
    config = serializers.DictField(child=serializers.CharField(allow_blank=True))
    isActive = serializers.BooleanField(default=False)

class PaymentConfigSerializer(serializers.ModelSerializer):
    configs = PaymentMethodConfigSerializer(many=True)

    class Meta:
        model = PaymentConfig
        fields = ['id', 'configs', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_configs(self, value):
        valid_methods = {'Paystack', 'Paypal', 'Remita', 'Stripe', 'Flutterwave'}
        for config in value:
            if config['method'] not in valid_methods:
                raise serializers.ValidationError(f"Invalid payment method: {config['method']}")
        return value

class SiteConfigSerializer(serializers.ModelSerializer):
    currency = serializers.ChoiceField(choices=['USD', 'NGN', 'EUR', 'GBP', 'KES', 'GHS'])

    class Meta:
        model = SiteConfig
        fields = ['id', 'currency', 'updated_at']
        read_only_fields = ['id', 'updated_at']