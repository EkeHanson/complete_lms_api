from django.db import models
from django.utils import timezone
from users.models import CustomUser, UserActivity
from groups.models import Group

class Schedule(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.TextField(blank=True, null=True)
    is_all_day = models.BooleanField(default=False)
    creator = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='created_schedules'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.title} ({self.start_time} - {self.end_time})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Log activity
        activity_type = 'schedule_created' if is_new else 'schedule_updated'
        UserActivity.objects.create(
            user=self.creator,
            activity_type=activity_type,
            details=f'Schedule "{self.title}" {"created" if is_new else "updated"}',
            status='success'
        )

    def delete(self, *args, **kwargs):
        # Log activity before deletion
        UserActivity.objects.create(
            user=self.creator,
            activity_type='schedule_deleted',
            details=f'Schedule "{self.title}" deleted',
            status='success'
        )
        super().delete(*args, **kwargs)

class ScheduleParticipant(models.Model):
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='schedule_participations'
    )
    group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='group_schedules'
    )
    is_optional = models.BooleanField(default=False)
    response_status = models.CharField(
        max_length=20,
        choices=(
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('declined', 'Declined'),
            ('tentative', 'Tentative'),
        ),
        default='pending'
    )

    class Meta:
        unique_together = [['schedule', 'user'], ['schedule', 'group']]
    
    def __str__(self):
        participant = self.user.email if self.user else self.group.name
        return f"Participant: {participant} for {self.schedule}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Log activity for response status changes
        if 'response_status' in kwargs.get('update_fields', []):
            UserActivity.objects.create(
                user=self.user if self.user else None,
                activity_type='schedule_response',
                details=f'Responded "{self.response_status}" to schedule "{self.schedule.title}"',
                status='success'
            )