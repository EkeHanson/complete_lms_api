# apps/subscriptions/models.py
from django.db import models
from core.models import Tenant
import uuid

class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='subscriptions')
    module = models.CharField(
        max_length=50,
        choices=[
            ('talent_engine', 'Talent Engine'),
            ('compliance', 'Compliance'),
            ('training', 'Training'),
            ('care_coordination', 'Care Coordination'),
            ('workforce', 'Workforce'),
            ('analytics', 'Analytics'),
            ('integrations', 'Integrations'),
        ]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'module')
        db_table = 'subscriptions_subscription'

    def __str__(self):
        return f"{self.tenant.name} - {self.module}"