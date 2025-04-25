from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import logging
import uuid

logger = logging.getLogger(__name__)

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        if 'role' not in extra_fields:
            from groups.models import Role
            default_role = Role.objects.filter(is_default=True).first()
            if default_role:
                extra_fields['role'] = default_role.code
        user = self.model(email=email, **extra_fields)
        if password:
            self.validate_password(password)
            user.set_password(password)
        user.save(using=self._db)
        # Create activity log for user creation
        UserActivity.objects.create(
            user=user,
            activity_type='user_management',
            details=f'New user created with email: {email}',
            status='success'
        )
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'super_admin')
        extra_fields.setdefault('status', 'active')
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        user = self.create_user(email, password, **extra_fields)
        # Create activity log for superuser creation
        UserActivity.objects.create(
            user=user,
            activity_type='user_management',
            details=f'New superuser created with email: {email}',
            status='success'
        )
        return user

    def validate_password(self, password):
        if len(password) < 8:
            raise ValidationError(
                _("Password must be at least 8 characters long."),
                code='password_too_short',
            )

class User(AbstractUser):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
        ('deleted', 'Deleted'),
    )
    username = None
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(max_length=20, default='member')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    bio = models.TextField(blank=True)
    facebook_link = models.URLField(blank=True)
    twitter_link = models.URLField(blank=True)
    linkedin_link = models.URLField(blank=True)
    title = models.CharField(max_length=100, blank=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    last_login_device = models.CharField(max_length=200, blank=True, null=True)
    login_attempts = models.PositiveIntegerField(default=0)
    signup_date = models.DateTimeField(auto_now_add=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.get_role_display()})"

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()

    def get_short_name(self):
        return self.first_name

    def get_role_display(self):
        try:
            from groups.models import Role
            return Role.objects.get(code=self.role).name
        except Role.DoesNotExist:
            return self.role

    def get_group(self):
        from groups.models import GroupMembership  # Import here to avoid circular import
        try:
            return self.group_membership.group
        except GroupMembership.DoesNotExist:
            return None

    def set_group(self, group):
        from groups.models import GroupMembership  # Import here to avoid circular import
        if hasattr(self, 'group_membership'):
            membership = self.group_membership
            membership.group = group
            membership.save()
        else:
            GroupMembership.objects.create(user=self, group=group)
        self.role = group.role.code
        self.save()

    def increment_login_attempts(self):
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.status = 'suspended'
        self.save()

    def reset_login_attempts(self):
        self.login_attempts = 0
        self.last_login = timezone.now()
        self.save()

    def suspend_account(self, reason=""):
        self.status = 'suspended'
        self.save()
        UserActivity.objects.create(
            user=self,
            activity_type='account_suspended',
            details=reason or 'Account suspended by admin',
            status='system'
        )

    def activate_account(self):
        self.status = 'active'
        self.login_attempts = 0
        self.save()
        UserActivity.objects.create(
            user=self,
            activity_type='account_activated',
            details='Account activated by admin',
            status='success'
        )

    def delete_account(self, reason=""):
        self.status = 'deleted'
        self.email = f"deleted_{self.id}_{self.email}"
        self.is_active = False
        self.save()
        UserActivity.objects.create(
            user=self,
            activity_type='user_management',
            details=reason or 'Account deleted by admin',
            status='system'
        )

    def update_profile(self, updated_fields):
        old_data = {
            'email': self.email,
            'role': self.role,
            'status': self.status,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone': self.phone,
            'title': self.title,
            'bio': self.bio
        }
        for field, value in updated_fields.items():
            setattr(self, field, value)
        self.save()
        changes = []
        for field, new_value in updated_fields.items():
            if old_data.get(field) != new_value:
                changes.append(f"{field}: {old_data.get(field)} -> {new_value}")
        if changes:
            UserActivity.objects.create(
                user=self,
                activity_type='profile_update',
                details=f"Profile updated: {'; '.join(changes)}",
                status='success'
            )

class UserActivity(models.Model):

    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('in-progress', 'In Progress'),
        ('system', 'System'),
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='activities',
        blank=True, 
        null=True
    )
    activity_type = models.CharField(max_length=50)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    device_info = models.CharField(max_length=200, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='success'
    )

    class Meta:
        verbose_name = _('Activity Log')
        verbose_name_plural = _('Activity Logs')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', 'activity_type']),
            models.Index(fields=['activity_type', 'status']),
        ]

    def __str__(self):
        user_info = self.user.email if self.user else 'System'
        return f"{user_info} - {self.get_activity_type_display()} ({self.timestamp})"

    def save(self, *args, **kwargs):
        if not self.id:
            self.timestamp = timezone.now()
        super().save(*args, **kwargs)




class MagicToken(models.Model):
    token = models.CharField(max_length=255, unique=True)  # JWT or UUID
    unique_subscriber_id = models.CharField(max_length=50)  # Matches CMVP's unique_subscriber_id
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.expires_at