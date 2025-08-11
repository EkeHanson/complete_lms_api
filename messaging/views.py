import logging
from django.db import transaction, connection
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework import serializers, viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_tenants.utils import tenant_context
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()

from groups.models import Group

from core.models import Tenant
from .models import (
    Message,
    MessageRecipient,
    MessageAttachment,
    MessageType,
)
from .serializers import (
    MessageSerializer,
    MessageAttachmentSerializer,
    MessageTypeSerializer,
    # ForwardMessageSerializer,  # Keep if defined
    # ReplyMessageSerializer,   # Keep if defined
)
from users.models import UserActivity, CustomUser
from utils.storage import get_storage_service

logger = logging.getLogger("messaging")

class TenantBaseView(viewsets.ViewSetMixin, generics.GenericAPIView):
    """Base view to handle tenant schema setting and logging for multitenancy."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise generics.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")

    def get_tenant(self):
        """Helper to get the current tenant."""
        return self.request.tenant

# ---------------------------------------------------------------------------
#  Message-Type CRUD
# ---------------------------------------------------------------------------

class MessageTypeViewSet(TenantBaseView):
    serializer_class = MessageTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return queryset (tenant context handled by middleware)."""
        with tenant_context(self.get_tenant()):
            return MessageType.objects.all()  # No tenant filter needed if no tenant FK

    def list(self, request, *args, **kwargs):
        """List all message types within the tenant context."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Create a new MessageType within the tenant context."""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=False)  # Do not raise exception, check validity manually
            if serializer.is_valid():
                with tenant_context(self.get_tenant()):
                    serializer.save()
                logger.info(f"MessageType created for tenant {self.get_tenant().schema_name}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"Validation failed for MessageType creation: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            logger.error(f"Validation error for MessageType creation: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """Update an existing MessageType within the tenant context."""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with tenant_context(self.get_tenant()):
            serializer.save()
        logger.info(f"MessageType {instance.id} updated for tenant {self.get_tenant().schema_name}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Delete a MessageType within the tenant context."""
        instance = self.get_object()
        with tenant_context(self.get_tenant()):
            self.perform_destroy(instance)
        logger.info(f"MessageType {instance.id} deleted for tenant {self.get_tenant().schema_name}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        """Set a MessageType as default within the tenant context."""
        instance = self.get_object()
        with tenant_context(self.get_tenant()):
            # Add your custom logic here (e.g., update a default flag)
            logger.info(f"MessageType {instance.pk} set as default for tenant {self.get_tenant().schema_name}")
        return Response({"status": "default set"})


# ---------------------------------------------------------------------------
#  Message CRUD, read/unread, stats, forward, reply
# ---------------------------------------------------------------------------


class MessageViewSet(TenantBaseView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return queryset filtered by the current tenant and user."""
        user = self.request.user
        with tenant_context(self.get_tenant()):
            # Only include messages where the recipient row for this user is NOT deleted
            return Message.objects.filter(
                (
                    Q(recipients__recipient=user) |
                    Q(recipients__group_member=user)
                ),
                Q(recipients__deleted=False)
            ).distinct().order_by("-sent_at")

    def list(self, request, *args, **kwargs):
        """List messages with pagination."""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_serializer_context(self):
        """Add request to serializer context."""
        return {"request": self.request}

    def create(self, request, *args, **kwargs):
        """Create a new Message within the tenant context and notify recipients."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with tenant_context(self.get_tenant()):
            message = serializer.save(sender=request.user)
        UserActivity.objects.create(
            user=request.user,
            activity_type="message_sent",
            details=f"{request.user} sent '{message.subject}'",
            status="success",
        )
        # Notify recipients after transaction commit
        transaction.on_commit(lambda: self._notify_recipients(message))
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _notify_recipients(self, message):
        recipients = set()
        for mr in message.recipients.all():
            if mr.recipient:
                recipients.add(mr.recipient.id)
            if mr.recipient_group:
                recipients.update(mr.recipient_group.memberships.values_list('user_id', flat=True))

        # Serialize the message for notification
        message_data = MessageSerializer(message, context=self.get_serializer_context()).data

        # Send event to each recipient
        for user_id in recipients:
            async_to_sync(channel_layer.group_send)(
                f"{self.get_tenant().schema_name}_user_{user_id}",
                {
                    "type": "new_message",
                    "message": message_data
                }
            )

    @action(detail=False, methods=['get'], url_path='unread_count')
    def unread_count(self, request):
        tenant = request.tenant
        user = request.user
        with tenant_context(tenant):
            count = Message.objects.filter(
                recipients__recipient=user,
                recipients__read=False
            ).count()
        return Response({'count': count})

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        tenant = request.tenant
        user = request.user
        with tenant_context(tenant):
            total = Message.objects.filter(recipients__recipient=user).count()
            unread = Message.objects.filter(recipients__recipient=user, recipients__read=False).count()
            sent = Message.objects.filter(sender=user).count()
        return Response({
            'total': total,
            'unread': unread,
            'sent': sent
        })

    @action(detail=False, methods=['post'], url_path='send_to_group')
    def send_to_group(self, request):
        tenant = request.tenant
        group_id = request.data.get('group_id')
        subject = request.data.get('subject')
        content = request.data.get('content')
        message_type_id = request.data.get('message_type')
        with tenant_context(tenant):
            group = Group.objects.get(id=group_id)
            message_type = MessageType.objects.get(id=message_type_id)
            message = Message.objects.create(
                sender=request.user,
                subject=subject,
                content=content,
                message_type=message_type,
                status='sent'
            )
            MessageRecipient.objects.create(message=message, recipient_group=group)
        return Response({'message': 'Message sent to group.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path='mark_as_read')
    def mark_as_read(self, request, pk=None):
        tenant = request.tenant
        user = request.user
        with tenant_context(tenant):
            try:
                message = self.get_object()
                # Mark all MessageRecipient rows for this user and message as read
                MessageRecipient.objects.filter(
                    message=message, recipient=user
                ).update(read=True, read_at=timezone.now())
                return Response({'status': 'marked as read'})
            except Message.DoesNotExist:
                return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['patch'], url_path='delete_for_user')
    def delete_for_user(self, request, pk=None):
        tenant = request.tenant
        user = request.user
        with tenant_context(tenant):
            try:
                message = self.get_object()
                MessageRecipient.objects.filter(message=message, recipient=user).update(deleted=True)
                return Response({'status': 'deleted for user'})
            except Message.DoesNotExist:
                return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
#  Attachments
# ---------------------------------------------------------------------------
class MessageAttachmentViewSet(TenantBaseView):
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return queryset (tenant context handled by middleware)."""
        with tenant_context(self.get_tenant()):
            return MessageAttachment.objects.all()  # No tenant filter needed if no tenant FK

    def get_serializer_context(self):
        """Add request to serializer context."""
        return {"request": self.request}

    def create(self, request, *args, **kwargs):
        """Create a new MessageAttachment within the tenant context."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with tenant_context(self.get_tenant()):
            serializer.save(uploaded_by=request.user)
        logger.info(f"MessageAttachment created for tenant {self.get_tenant().schema_name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Update an existing MessageAttachment within the tenant context."""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with tenant_context(self.get_tenant()):
            serializer.save()
        logger.info(f"MessageAttachment {instance.id} updated for tenant {self.get_tenant().schema_name}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Delete a MessageAttachment within the tenant context."""
        instance = self.get_object()
        # Delete associated attachments from storage
        storage_service = get_storage_service()
        for attachment in instance.attachments.all():
            if attachment.file:
                storage_service.delete_file(attachment.file)
        with tenant_context(self.get_tenant()):
            self.perform_destroy(instance)
        logger.info(f"MessageAttachment {instance.id} deleted for tenant {self.get_tenant().schema_name}")
        return Response(status=status.HTTP_204_NO_CONTENT)


