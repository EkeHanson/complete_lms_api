# payments/serializers.py
from rest_framework import serializers
from .models import PaymentConfig, SiteConfig,PaymentGateway 

class PaymentGatewaySerializer(serializers.ModelSerializer):
    config = serializers.SerializerMethodField()

    class Meta:
        model = PaymentGateway
        fields = ['id', 'name', 'description', 'is_active', 'is_test_mode', 'is_default', 'created_at', 'updated_at', 'config']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_config(self, obj):
        # Get the current tenant from context if available
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None) if request else None
        from .models import PaymentConfig
        if tenant:
            payment_config = PaymentConfig.objects.filter().first()
            if payment_config and payment_config.configs:
                for config in payment_config.configs:
                    if config.get('method') == obj.name:
                        return config.get('config')
        return None


class PaymentMethodConfigSerializer(serializers.Serializer):
    method = serializers.CharField(max_length=50)
    config = serializers.DictField(child=serializers.CharField(allow_blank=True))
    isActive = serializers.BooleanField(default=False)

class PaymentConfigSerializer(serializers.ModelSerializer):
    configs = PaymentMethodConfigSerializer(many=True)

    class Meta:
        model = PaymentConfig
        fields = ['id', 'configs', 'created_at', 'updated_at', 'title']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_configs(self, value):
        valid_methods = {'Paystack', 'Paypal', 'Remita', 'Stripe', 'Flutterwave'}
        for config in value:
            if config['method'] not in valid_methods:
                raise serializers.ValidationError(f"Invalid payment method: {config['method']}")
        return value

class SiteConfigSerializer(serializers.ModelSerializer):
    # Allow any currency string, not limited to choices
    currency = serializers.CharField(max_length=4, required=True)
    title = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = SiteConfig
        fields = ['id', 'currency', 'title', 'updated_at']
        read_only_fields = ['id', 'updated_at']