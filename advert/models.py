# models.py
from django.db import models
from django.utils import timezone
from users.models import CustomUser, UserActivity

class Advert(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('retired', 'Retired'),
    ]
    
    TARGET_CHOICES = [
        ('all', 'All Users'),
        ('learners', 'Learners Only'),
        ('instructors', 'Instructors Only'),
        ('admins', 'Admins Only'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    link = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='adverts/', blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.PositiveIntegerField(default=1)
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    creator = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='created_adverts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.status})"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Log activity
        activity_type = 'advert_created' if is_new else 'advert_updated'
        UserActivity.objects.create(
            user=self.creator,
            activity_type=activity_type,
            details=f'Advert "{self.title}" {"created" if is_new else "updated"}',
            status='success'
        )
    
    def delete(self, *args, **kwargs):
        # Log activity before deletion
        UserActivity.objects.create(
            user=self.creator,
            activity_type='advert_deleted',
            details=f'Advert "{self.title}" deleted',
            status='success'
        )
        super().delete(*args, **kwargs)