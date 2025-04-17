# messaging/serializers.py
from rest_framework import serializers
from .models import Message, MessageRecipient, MessageAttachment
from users.serializers import UserSerializer
from users.serializers import UserSerializer
from users.models import User
from groups.serializers import UserGroupSerializer
from django.utils import timezone


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ['id', 'file', 'original_filename', 'uploaded_at']
        read_only_fields = ['original_filename', 'uploaded_at']

class MessageRecipientSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)
    recipient_group = UserGroupSerializer(read_only=True)
    
    class Meta:
        model = MessageRecipient
        fields = ['id', 'recipient', 'recipient_group', 'read', 'read_at']

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
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
        queryset=UserGroup.objects.all(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'subject', 'content', 'message_type', 
            'sent_at', 'status', 'parent_message', 'is_forward',
            'recipients', 'attachments', 'recipient_users', 'recipient_groups'
        ]
        read_only_fields = ['sender', 'sent_at', 'recipients', 'attachments']
    
    def create(self, validated_data):
        recipient_users = validated_data.pop('recipient_users', [])
        recipient_groups = validated_data.pop('recipient_groups', [])
        
        message = Message.objects.create(
            sender=self.context['request'].user,
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
    
    def update(self, instance, validated_data):
        # Handle updating read status separately
        if 'read' in validated_data:
            recipient = instance.recipients.filter(
                recipient=self.context['request'].user
            ).first()
            if recipient:
                recipient.read = validated_data['read']
                if validated_data['read'] and not recipient.read_at:
                    recipient.read_at = timezone.now()
                recipient.save()
            return instance
        
        return super().update(instance, validated_data)

class ForwardMessageSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200)
    content = serializers.CharField()
    recipient_users = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all()
    )
    recipient_groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=UserGroup.objects.all(),
        required=False
    )

class ReplyMessageSerializer(serializers.Serializer):
    content = serializers.CharField()