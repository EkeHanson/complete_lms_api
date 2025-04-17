from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import logging
from users.models import UserActivity

logger = logging.getLogger(__name__)

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.SlugField(max_length=20, unique=True, help_text="Short code for the role (e.g., 'admin', 'instructor')")
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list, blank=True, help_text="List of permission codes for this role")
    is_default = models.BooleanField(default=False, help_text="Set as default role for new users")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')

    def __str__(self):
        return self.name

    def clean(self):
        if self.is_default:
            existing_default = Role.objects.filter(is_default=True).exclude(pk=self.pk).first()
            if existing_default:
                raise ValidationError(
                    f"{existing_default} is already set as default. Only one role can be default."
                )


    def save(self, *args, **kwargs):
        created = not self.pk
        self.full_clean()
        super().save(*args, **kwargs)
        
        if created:
            UserActivity.objects.create(
                activity_type='role_created',
                details=f'Role "{self.name}" was created',
                status='success'
            )
        else:
            UserActivity.objects.create(
                activity_type='role_updated',
                details=f'Role "{self.name}" was updated',
                status='success'
            )

    def delete(self, *args, **kwargs):
        UserActivity.objects.create(
            activity_type='role_deleted',
            details=f'Role "{self.name}" was deleted',
            status='system'
        )
        super().delete(*args, **kwargs)

class Group(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    role = models.ForeignKey(
        Role, 
        on_delete=models.PROTECT, 
        related_name='groups',
        null=False,  # Make role required
        blank=False
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Group')
        verbose_name_plural = _('Groups')

    def __str__(self):
        return f"{self.name} ({self.role.name if self.role else 'No role'})"

    def clean(self):
        if not self.role:
            raise ValidationError("A role must be assigned to the group")
        

# groups/models.py
class GroupMembership(models.Model):
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='group_memberships'  # Changed from 'group_membership'
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,  # Changed from PROTECT
        related_name='memberships'
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Group Membership')
        verbose_name_plural = _('Group Memberships')
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'group'],  # Changed to composite unique
                name='unique_user_group_membership'
            )
        ]

    def __str__(self):
        return f"{self.user.email} in {self.group.name}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            # Remove this check since we now allow multiple groups
            self.user.role = self.group.role.code
            self.user.save()
        super().save(*args, **kwargs)
    user = models.OneToOneField(
        'users.User',  # Use string literal instead of importing User
        on_delete=models.CASCADE,
        related_name='group_membership'
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name='memberships'
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Group Membership')
        verbose_name_plural = _('Group Memberships')
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='unique_user_membership'
            )
        ]

    def __str__(self):
        return f"{self.user.email} in {self.group.name}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            if GroupMembership.objects.filter(user=self.user).exists():
                raise ValidationError(_("User already belongs to a group"))
            self.user.role = self.group.role.code
            self.user.save()
        super().save(*args, **kwargs)