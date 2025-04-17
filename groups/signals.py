# groups/signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Group, GroupMembership
from users.models import UserActivity

@receiver(post_save, sender=Group)
def log_group_activity(sender, instance, created, **kwargs):
    if created:
        UserActivity.objects.create(
            activity_type='group_created',
            details=f'Group "{instance.name}" was created',
            status='success'
        )
    else:
        UserActivity.objects.create(
            activity_type='group_updated',
            details=f'Group "{instance.name}" was updated',
            status='success'
        )

@receiver(post_delete, sender=Group)
def log_group_deletion(sender, instance, **kwargs):
    UserActivity.objects.create(
        activity_type='group_deleted',
        details=f'Group "{instance.name}" was deleted',
        status='system'
    )

@receiver(post_save, sender=GroupMembership)
def log_membership_activity(sender, instance, created, **kwargs):
    if created:
        UserActivity.objects.create(
            user=instance.user,
            activity_type='group_member_added',
            details=f'User added to group "{instance.group.name}"',
            status='success'
        )
    else:
        UserActivity.objects.create(
            user=instance.user,
            activity_type='group_member_updated',
            details=f'Membership in group "{instance.group.name}" was updated',
            status='success'
        )

@receiver(post_delete, sender=GroupMembership)
def log_membership_removal(sender, instance, **kwargs):
    UserActivity.objects.create(
        user=instance.user,
        activity_type='group_member_removed',
        details=f'User removed from group "{instance.group.name}"',
        status='system'
    )