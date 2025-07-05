from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import logging
from users.models import CustomUser, UserActivity

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
        help_text="The role assigned to users in this group"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Group')
        verbose_name_plural = _('Groups')

    def __str__(self):
        return f"{self.name}"

class GroupMembership(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='group_memberships'
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='memberships',
        null=True,
        blank=True
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(
        default=False,
        help_text="Primary group determines the user's main role"
    )

    class Meta:
        verbose_name = _('Group Membership')
        verbose_name_plural = _('Group Memberships')
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'group'],
                name='unique_user_group_membership'
            ),
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_primary=True),
                name='unique_user_primary_group'
            )
        ]

    def __str__(self):
        return f"{self.user.email} in {self.group.name} (Role: {self.role.name if self.role else 'None'})"

    def clean(self):
        # Validate that the role matches the group's role
        if self.role and self.group and self.role != self.group.role:
            raise ValidationError(
                f"Role '{self.role.name}' does not match group's role '{self.group.role.name}'"
            )
        
        # Validate primary group assignment
        if self.is_primary and not self.role:
            raise ValidationError("Primary membership must have a role assigned")

    def save(self, *args, **kwargs):
        self.full_clean()
        
        # If this is being set as primary, ensure no other primary exists
        if self.is_primary:
            GroupMembership.objects.filter(user=self.user, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
            
            # Update user's main role if this is primary
            if self.role:
                self.user.role = self.role.code
                self.user.save()
        
        super().save(*args, **kwargs)