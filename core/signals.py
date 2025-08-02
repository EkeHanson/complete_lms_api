import logging
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_tenants.utils import tenant_context
from core.models import Tenant
from payments.models import PaymentGateway, SiteConfig, PaymentConfig
from payments.payment_configs import PAYMENT_GATEWAY_CONFIGS

logger = logging.getLogger('core')

@receiver(post_save, sender=Tenant)
def prepopulate_payment_models(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        # Ensure schema is created before prepopulating
        instance.create_schema(check_if_exists=True)
        with tenant_context(instance):
            payment_configs = []
            for gateway_data in PAYMENT_GATEWAY_CONFIGS:
                PaymentGateway.objects.create(
                    name=gateway_data['name'],
                    description=gateway_data['description'],
                    is_active=gateway_data['is_active'],
                    is_test_mode=gateway_data['is_test_mode'],
                    is_default=gateway_data['is_default']
                )
                logger.info(f"Created payment gateway {gateway_data['name']} for tenant {instance.schema_name}")
                payment_configs.append({
                    'method': gateway_data['name'],
                    'config': gateway_data['config'],
                    'isActive': gateway_data['is_active']
                })
            SiteConfig.objects.create(
                currency='USD',
                title='US Dollar'
            )
            logger.info(f"Created default site configuration for tenant {instance.schema_name}")
            PaymentConfig.objects.create(
                configs=payment_configs
            )
            logger.info(f"Created default payment configuration for tenant {instance.schema_name}")
    except Exception as e:
        logger.error(f"Failed to prepopulate payment models for tenant {instance.schema_name}: {str(e)}")
