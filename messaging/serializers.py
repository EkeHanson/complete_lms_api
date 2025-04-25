# messaging/serializers.py
from rest_framework import serializers
from .models import Message, MessageRecipient, MessageAttachment, MessageType
from users.serializers import UserSerializer
from groups.serializers import GroupSerializer
from django.utils import timezone
from django.db.models import Q
from users.models import User
from groups.models import Group

class MessageTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageType
        fields = ['id', 'value', 'label', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_value(self, value):
        if not value.isidentifier():
            raise serializers.ValidationError(
                "Value can only contain letters, numbers and underscores"
            )
        return value.lower()

class MessageAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageAttachment
        fields = ['id', 'file', 'file_url', 'original_filename', 'uploaded_at']
        read_only_fields = ['original_filename', 'uploaded_at', 'file_url']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

class MessageRecipientSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)
    recipient_group = GroupSerializer(read_only=True)
    
    class Meta:
        model = MessageRecipient
        fields = ['id', 'recipient', 'recipient_group', 'read', 'read_at']

class MessageSerializer(serializers.ModelSerializer):
    message_type = serializers.PrimaryKeyRelatedField(queryset=MessageType.objects.all())
    sender = UserSerializer(read_only=True)
    message_type_display = serializers.CharField(source='message_type.label', read_only=True)
    sender_display = serializers.SerializerMethodField(read_only=True)
    recipients = MessageRecipientSerializer(many=True, read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    parent_message = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(), 
        required=False, 
        allow_null=True
    )
    recipient_users = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        write_only=True,
        required=False
    )
    recipient_groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Group.objects.all(),
        write_only=True,
        required=False
    )
    is_read = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'sender_display','subject', 'content', 'message_type','message_type_display',
            'sent_at', 'status', 'parent_message', 'is_forward',
            'recipients', 'attachments', 'recipient_users', 'recipient_groups',
            'is_read'
        ]
        read_only_fields = ['sender','sender_display', 'message_type_display','sent_at', 'recipients', 'attachments', 'is_read']
    
    def get_is_read(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        # Check if current user has read this message
        recipient = obj.recipients.filter(
            Q(recipient=request.user) | 
            Q(recipient_group__memberships__user=request.user)  # Corrected line
        ).first()
        return recipient.read if recipient else None
    
    def get_sender_display(self, obj):
        """Get formatted sender name"""
        if obj.sender:
            # print("Sender found")
            return f"{obj.sender.first_name} {obj.sender.last_name}"
        return None
    
    def create(self, validated_data):
        recipient_users = validated_data.pop('recipient_users', [])
        recipient_groups = validated_data.pop('recipient_groups', [])
        
        message = Message.objects.create(
           # sender=self.context['request'].user,
            **validated_data
        )
        
        # Create recipients
        for user in recipient_users:
            MessageRecipient.objects.create(
                message=message,
                recipient=user
            )
        
        for group in recipient_groups:
            MessageRecipient.objects.create(
                message=message,
                recipient_group=group
            )
        
        return message
    