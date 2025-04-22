# payments/admin.py
from django.contrib import admin
from .models import PaymentConfig, SiteConfig

@admin.register(PaymentConfig)
class PaymentConfigAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ['currency', 'updated_at']
    readonly_fields = ['updated_at']