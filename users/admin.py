from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserActivity

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'status', 'last_login')
    list_filter = ('role', 'status', 'is_staff', 'is_superuser')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'birth_date', 'profile_picture')}),
        ('Status', {'fields': ('role', 'status')}),
        ('Social Links', {'fields': ('facebook_link', 'twitter_link', 'linkedin_link', 'title', 'bio')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Security', {'fields': ('login_attempts', 'last_login_ip', 'last_login_device')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'role'),
        }),
    )

class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'timestamp', 'status')
    list_filter = ('activity_type', 'status', 'timestamp')
    search_fields = ('user__email', 'details')
    readonly_fields = ('timestamp',)

admin.site.register(User, CustomUserAdmin)
admin.site.register(UserActivity, UserActivityAdmin)