from django.db import models
from django.utils.translation import gettext as _

class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list)
    is_default = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')

class Group(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    role = models.ForeignKey('groups.Role', on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Group')
        verbose_name_plural = _('Groups')

class GroupMembership(models.Model):
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    group = models.ForeignKey('groups.Group', on_delete=models.CASCADE, related_name='memberships')
    role = models.ForeignKey('groups.Role', on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.user.email} in {self.group.name}"

    class Meta:
        verbose_name = _('Group Membership')
        verbose_name_plural = _('Group Memberships')
        unique_together = ['user', 'group']


