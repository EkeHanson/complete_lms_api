from django.db import models
from users.models import CustomUser

class ActivityLog(models.Model):
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('in-progress', 'In Progress'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    activity_type = models.CharField(max_length=50,)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    device_info = models.CharField(max_length=200, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
    
    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.user if self.user else 'System'}"