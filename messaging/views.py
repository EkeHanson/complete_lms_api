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
            qs = Message.objects.filter(
                Q(sender=user)
                | Q(recipients__recipient=user)
                | Q(recipients__recipient_group__memberships__user=user)
            ).distinct().order_by("-sent_at")
            qp = self.request.query_params
            if (mt := qp.get("type")) and mt != "all":
                qs = qs.filter(message_type=mt)
            if (stat := qp.get("status")) and stat != "all":
                qs = qs.filter(status=stat)
            if (search := qp.get("search")):
                qs = qs.filter(
                    Q(subject__icontains=search)
                    | Q(content__icontains=search)
                    | Q(sender__email__icontains=search)
                    | Q(sender__first_name__icontains=search)
                    | Q(sender__last_name__icontains=search)
                )
            if (rs := qp.get("read_status")) and rs != "all":
                if rs == "read":
                    qs = qs.filter(recipients__read=True, recipients__recipient=user)
                else:
                    qs = qs.filter(
                        Q(recipients__read=False)
                        & (Q(recipients__recipient=user) | Q(recipients__recipient_group__memberships__user=user))
                    )
            if (df := qp.get("date_from")):
                qs = qs.filter(sent_at__gte=df)
            if (dt := qp.get("date_to")):
                qs = qs.filter(sent_at__lte=dt)
            return qs

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
        """Create a new Message within the tenant context."""
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
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Return the count of unread messages for the current user."""
        user = request.user
        with tenant_context(self.get_tenant()):
            unread_count = MessageRecipient.objects.filter(
                message__sent_at__lte=timezone.now(),
                recipient=user,
                read=False
            ).count()
        return Response({'unread_count': unread_count})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Return basic message statistics for the current tenant."""
        with tenant_context(self.get_tenant()):
            total_messages = Message.objects.count()
            unread_messages = MessageRecipient.objects.filter(read=False).count()
        return Response({
            'total_messages': total_messages,
            'unread_messages': unread_messages
        })


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
        with tenant_context(self.get_tenant()):
            self.perform_destroy(instance)
        logger.info(f"MessageAttachment {instance.id} deleted for tenant {self.get_tenant().schema_name}")
        return Response(status=status.HTTP_204_NO_CONTENT)
    

