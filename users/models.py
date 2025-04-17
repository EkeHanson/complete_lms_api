from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import logging

logger = logging.getLogger(__name__)

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        if password:
            self.validate_password(password)
            user.set_password(password)
        
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Creates and saves a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('status', 'active')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

    def validate_password(self, password):
        """
        Validate that the password meets minimum requirements.
        """
        if len(password) < 8:
            raise ValidationError(
                _("Password must be at least 8 characters long."),
                code='password_too_short',
            )

class User(AbstractUser):
    ROLES = (
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('instructor', 'Instructor/Trainer'),
        ('learner', 'Learner'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
    )
    
    # Remove username field and make email the primary identifier
    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    # User profile fields
    role = models.CharField(max_length=20, choices=ROLES, default='learner')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    phone = models.CharField(max_length=20, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    bio = models.TextField(blank=True)
    facebook_link = models.URLField(blank=True)
    twitter_link = models.URLField(blank=True)
    linkedin_link = models.URLField(blank=True)
    title = models.CharField(max_length=100, blank=True)
    
    # Security and login fields
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    last_login_device = models.CharField(max_length=200, blank=True, null=True)
    login_attempts = models.PositiveIntegerField(default=0)
    signup_date = models.DateTimeField(auto_now_add=True)
    
    # Authentication settings
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.role})"

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def increment_login_attempts(self):
        """Increment failed login attempts counter"""
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.status = 'suspended'
        self.save()
        
    def reset_login_attempts(self):
        """Reset failed login attempts counter"""
        self.login_attempts = 0
        self.last_login = timezone.now()
        self.save()
        
    def suspend_account(self, reason=""):
        """Suspend the user account"""
        self.status = 'suspended'
        self.save()
        
        # Log suspension
        UserActivity.objects.create(
            user=self,
            activity_type='account_suspended',
            details=reason or 'Account suspended by admin',
            status='system'
        )

    def activate_account(self):
        """Activate a pending or suspended account"""
        self.status = 'active'
        self.login_attempts = 0
        self.save()

class UserActivity(models.Model):
    ACTIVITY_TYPES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('password_change', 'Password Change'),
        ('profile_update', 'Profile Update'),
        ('account_suspended', 'Account Suspended'),
        ('account_activated', 'Account Activated'),
        ('course_access', 'Course Access'),
        ('assignment_submission', 'Assignment Submission'),
        ('system', 'System Event'),
        ('user_management', 'User Management'),
    )
    
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('in-progress', 'In Progress'),
    )
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='activities',
        blank=True, 
        null=True
    )
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
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
        ]
    
    def __str__(self):
        user_info = self.user.email if self.user else 'System'
        return f"{user_info} - {self.get_activity_type_display()} ({self.timestamp})"

    def save(self, *args, **kwargs):
        """Add automatic timestamp on creation"""
        if not self.id:
            self.timestamp = timezone.now()
        super().save(*args, **kwargs)