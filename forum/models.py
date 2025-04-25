from django.db import models
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from groups.models import Group
from users.models import User, UserActivity
import logging

logger = logging.getLogger(__name__)

class Forum(models.Model):
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    allowed_groups = models.ManyToManyField(
        Group,
        related_name='forums',
        blank=True,
        help_text="Groups that can access this forum"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_forums'
    )

    class Meta:
        ordering = ['title']
        verbose_name = _('Forum')
        verbose_name_plural = _('Forums')

    def __str__(self):
        return self.title

    def clean(self):
        if not self.title:
            raise ValidationError("Forum title cannot be empty")

    def save(self, *args, **kwargs):
        created = not self.pk
        self.full_clean()
        super().save(*args, **kwargs)

        activity_type = 'forum_created' if created else 'forum_updated'
        UserActivity.objects.create(
            activity_type=activity_type,
            user=self.created_by,
            details=f'Forum "{self.title}" was {"created" if created else "updated"}',
            status='success'
        )

    def delete(self, *args, **kwargs):
        UserActivity.objects.create(
            activity_type='forum_deleted',
            user=self.created_by,
            details=f'Forum "{self.title}" was deleted',
            status='system'
        )
        super().delete(*args, **kwargs)

class ForumPost(models.Model):
    forum = models.ForeignKey(
        Forum,
        on_delete=models.CASCADE,
        related_name='posts'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='forum_posts'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=False)
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_posts'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Forum Post')
        verbose_name_plural = _('Forum Posts')

    def __str__(self):
        return f"Post in {self.forum.title} by {self.author.email if self.author else 'Deleted User'}"

    def save(self, *args, **kwargs):
        created = not self.pk
        super().save(*args, **kwargs)

        if created:
            UserActivity.objects.create(
                activity_type='forum_post_created',
                user=self.author,
                details=f'Created post in forum "{self.forum.title}"',
                status='success'
            )

from django.db import models
from django.utils.translation import gettext as _
from users.models import User, UserActivity
import logging

logger = logging.getLogger(__name__)

class ModerationQueue(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    content_type = models.CharField(max_length=100)  # e.g., 'forum_post', 'comment'
    content_id = models.PositiveIntegerField()
    content = models.TextField()
    reported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reported_items'
    )
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    moderation_notes = models.TextField(blank=True)
    moderated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_items'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Moderation Queue')
        verbose_name_plural = _('Moderation Queues')

    def __str__(self):
        return f"{self.content_type} {self.content_id} - {self.status}"

    def save(self, *args, **kwargs):
        created = not self.pk
        super().save(*args, **kwargs)

        if created:
            UserActivity.objects.create(
                activity_type='moderation_item_created',
                user=self.reported_by,
                details=f'Reported {self.content_type} {self.content_id}',
                status='success'
            )
        elif self.status != 'pending':
            UserActivity.objects.create(
                activity_type='moderation_item_updated',
                user=self.moderated_by,
                details=f'Moderated {self.content_type} {self.content_id} as {self.status}',
                status='success'
            )