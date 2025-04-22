# payments/models.py
from django.db import models

class SiteConfig(models.Model):
    currency = models.CharField(
        max_length=10,
        choices=[(c, c) for c in ['USD', 'NGN', 'EUR', 'GBP', 'KES', 'GHS']],
        default='USD'
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