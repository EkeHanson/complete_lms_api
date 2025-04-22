from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Certificate, Enrollment
import uuid

@receiver(post_save, sender=Enrollment)
def create_certificate_on_completion(sender, instance, **kwargs):
    if instance.completed_at and not hasattr(instance, 'certificate'):
        certificate_id = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        Certificate.objects.create(
            enrollment=instance,
            certificate_id=certificate_id
        )