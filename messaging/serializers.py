from django.db import transaction
from django_tenants.utils import tenant_context
from rest_framework import serializers
from .models import Message, MessageRecipient, MessageAttachment, MessageType
from users.models import CustomUser
from groups.models import Group
from utils.storage import get_storage_service
import uuid
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  MessageType
# ---------------------------------------------------------------------------
class MessageTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageType
        fields = ["id", "value", "label", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_value(self, value):
        if not value.isidentifier():
            raise serializers.ValidationError(
                "Value may contain only letters, digits and underscores."
            )
        return value.lower()

    def create(self, validated_data):
        tenant = self.context["request"].tenant
        with tenant_context(tenant):
            return MessageType.objects.create(**validated_data)

    def update(self, instance, validated_data):
        tenant = self.context["request"].tenant
        with tenant_context(tenant):
            return super().update(instance, validated_data)

# ---------------------------------------------------------------------------
#  MessageAttachment
# ---------------------------------------------------------------------------
class MessageAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = MessageAttachment
        fields = [
            "id",
            "file",
            "file_url",
            "original_filename",
            "uploaded_at",
        ]
        read_only_fields = ["original_filename", "uploaded_at", "file_url"]

    def get_file_url(self, obj):
        if obj.file:
            storage_service = get_storage_service()
            return storage_service.get_public_url(str(obj.file))
        return None

    def create(self, validated_data):
        tenant = self.context["request"].tenant
        file_obj = validated_data.pop("file", None)
        original_filename = validated_data.get("original_filename", None)
        if file_obj:
            file_name = f"messaging/{tenant.schema_name}/{uuid.uuid4().hex}_{file_obj.name}"
            storage_service = get_storage_service()
            try:
                storage_service.upload_file(file_obj, file_name, getattr(file_obj, "content_type", "application/octet-stream"))
                validated_data["file"] = file_name
                validated_data["original_filename"] = original_filename or file_obj.name
            except Exception as e:
                logger.error(f"[{tenant.schema_name}] Failed to upload attachment: {str(e)}")
                raise serializers.ValidationError("Failed to upload attachment")
        with tenant_context(tenant):
            return MessageAttachment.objects.create(**validated_data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.file:
            storage_service = get_storage_service()
            rep['file_url'] = storage_service.get_public_url(instance.file)
        return rep

# ---------------------------------------------------------------------------
#  MessageRecipient
# ---------------------------------------------------------------------------
class MessageRecipientSerializer(serializers.ModelSerializer):
    recipient = serializers.StringRelatedField(read_only=True)
    recipient_group = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = MessageRecipient
        fields = ["id", "recipient", "recipient_group", "read", "read_at"]

# ---------------------------------------------------------------------------
#  Message
# ---------------------------------------------------------------------------
class MessageSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()
    message_type = serializers.PrimaryKeyRelatedField(queryset=MessageType.objects.all())
    sender = serializers.StringRelatedField(read_only=True)
    recipients = MessageRecipientSerializer(many=True, read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    parent_message = serializers.PrimaryKeyRelatedField(queryset=Message.objects.all(), allow_null=True, required=False)
    recipient_users = serializers.PrimaryKeyRelatedField(many=True, queryset=CustomUser.objects.all(), write_only=True, required=False)
    recipient_groups = serializers.PrimaryKeyRelatedField(many=True, queryset=Group.objects.all(), write_only=True, required=False)

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "subject",
            "content",
            "message_type",
            "sent_at",
            "status",
            "parent_message",
            "is_forward",
            "recipients",
            "attachments",
            "recipient_users",
            "recipient_groups",
            'is_read',
        ]
        read_only_fields = [
            "sender",
            "sent_at",
            "recipients",
            "attachments",
        ]

    def create(self, validated_data):
        tenant = self.context["request"].tenant
        recipient_users = validated_data.pop("recipient_users", [])
        recipient_groups = validated_data.pop("recipient_groups", [])
        attachments_data = self.context["request"].FILES.getlist("attachments")
        validated_data.pop("sender", None)
        with tenant_context(tenant), transaction.atomic():
            message = Message.objects.create(sender=self.context["request"].user, **validated_data)
            recipients = []
            # Individual users
            for user in recipient_users:
                recipients.append(MessageRecipient(message=message, recipient=user))
            # Groups: add all group members as recipients
            for group in recipient_groups:
                user_ids = group.memberships.values_list('user_id', flat=True)
                for user_id in user_ids:
                    recipients.append(MessageRecipient(message=message, recipient_id=user_id, recipient_group=group))
            MessageRecipient.objects.bulk_create(recipients)
            # Attachments
            for file_obj in attachments_data:
                file_name = f"messaging/{tenant.schema_name}/{uuid.uuid4().hex}_{file_obj.name}"
                storage_service = get_storage_service()
                try:
                    storage_service.upload_file(file_obj, file_name, getattr(file_obj, "content_type", "application/octet-stream"))
                    MessageAttachment.objects.create(
                        message=message,
                        file=file_name,
                        original_filename=file_obj.name
                    )
                except Exception as e:
                    logger.error(f"[{tenant.schema_name}] Failed to upload attachment: {str(e)}")
                    raise serializers.ValidationError("Failed to upload attachment")
        return message

    def update(self, instance, validated_data):
        tenant = self.context["request"].tenant
        attachments_data = self.context["request"].FILES.getlist("attachments")
        with tenant_context(tenant), transaction.atomic():
            # Optionally handle updating attachments here
            return super().update(instance, validated_data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['attachments'] = MessageAttachmentSerializer(instance.attachments.all(), many=True, context=self.context).data
        return rep

    def get_recipient_users(self, obj):
        return obj.recipient_users.values_list('id', flat=True)

    def get_recipient_groups(self, obj):
        return obj.recipient_groups.values_list('id', flat=True)

    def get_recipient_groups(self, obj):
        return obj.recipient_groups.values_list('id', flat=True)

    def create(self, validated_data):
        tenant = self.context["request"].tenant
        recipient_users = validated_data.pop("recipient_users", [])
        recipient_groups = validated_data.pop("recipient_groups", [])
        attachments_data = self.context["request"].FILES.getlist("attachments")
        validated_data.pop("sender", None)
        with tenant_context(tenant), transaction.atomic():
            message = Message.objects.create(sender=self.context["request"].user, **validated_data)
            recipients = []
            # Individual users
            for user in recipient_users:
                recipients.append(MessageRecipient(message=message, recipient=user))
            # Groups: add all group members as recipients
            for group in recipient_groups:
                user_ids = group.memberships.values_list('user_id', flat=True)
                for user_id in user_ids:
                    recipients.append(MessageRecipient(message=message, recipient_id=user_id, recipient_group=group))
            MessageRecipient.objects.bulk_create(recipients)
            # Attachments
            for file_obj in attachments_data:
                file_name = f"messaging/{tenant.schema_name}/{uuid.uuid4().hex}_{file_obj.name}"
                storage_service = get_storage_service()
                try:
                    storage_service.upload_file(file_obj, file_name, getattr(file_obj, "content_type", "application/octet-stream"))
                    MessageAttachment.objects.create(
                        message=message,
                        file=file_name,
                        original_filename=file_obj.name
                    )
                except Exception as e:
                    logger.error(f"[{tenant.schema_name}] Failed to upload attachment: {str(e)}")
                    raise serializers.ValidationError("Failed to upload attachment")
        return message


    def get_is_read(self, obj):
        user = self.context["request"].user
        # Find the MessageRecipient for this user and message
        mr = obj.recipients.filter(recipient=user).first()
        return mr.read if mr else False