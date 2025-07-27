from rest_framework import serializers
from .models import ActivityLog

class ActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ActivityLog
        fields = ['id', 'user', 'user_email', 'activity_type', 'details', 'ip_address', 'device_info', 'timestamp', 'status']
        read_only_fields = ['timestamp']

    def validate_status(self, value):
        if value not in dict(ActivityLog.STATUS_CHOICES):
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(dict(ActivityLog.STATUS_CHOICES).keys())}")
        return value

    def validate(self, data):
        tenant = self.context.get('tenant')
        if not tenant:
            raise serializers.ValidationError("Tenant context is required.")
        return data