from django.db import models
from django.db.models import Q
from django.db import transaction


class PaymentGateway(models.Model):
    name = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=256, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_test_mode = models.BooleanField(default=True, help_text="Toggle between test and live mode for this gateway.")
    is_default = models.BooleanField(default=False, help_text="Set as the default payment gateway for the application.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment Gateway"
        verbose_name_plural = "Payment Gateways"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Ensure only one PaymentGateway is active at a time."""
        if self.is_active:
            with transaction.atomic():
                # Deactivate all other gateways
                PaymentGateway.objects.filter(~Q(id=self.id)).update(is_active=False)
        super().save(*args, **kwargs)


class SiteConfig(models.Model):
    currency = models.CharField(
        max_length=10,
        default='USD'
    )
    title = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Optional descriptive name for the currency, e.g. 'Nigerian Naira', 'US Dollar'"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Configuration"
        verbose_name_plural = "Site Configurations"

    def __str__(self):
        return f"Site Config (Currency: {self.currency})"


class PaymentConfig(models.Model):
    configs = models.JSONField(default=list)  # List of payment method configs
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment Configuration"
        verbose_name_plural = "Payment Configurations"

    def __str__(self):
        return "Payment Config"

    def save(self, *args, **kwargs):
        """Ensure only one payment method is active in configs."""
        if self.configs:
            active_count = sum(1 for config in self.configs if config.get('isActive', False))
            if active_count > 1:
                raise ValueError("Only one payment method can be active at a time.")
            # If setting a new active method, deactivate others
            for config in self.configs:
                if config.get('isActive', False):
                    # Ensure only one is active
                    for other_config in self.configs:
                        if other_config != config:
                            other_config['isActive'] = False
        super().save(*args, **kwargs)