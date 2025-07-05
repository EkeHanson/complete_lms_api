

# views/tenant_message_views.py
import logging
import logging
from django.db import transaction, connection
from django.utils import timezone
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_tenants.utils import tenant_context
from users.models import  UserActivity

from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
    # ForwardMessageSerializer,   # ← keep if you already have them
    # ReplyMessageSerializer,     # ← keep if you already have them
)
from users.models import UserActivity, CustomUser

# Optional extra permission you already use elsewhere
# from .permissions import IsSubscribedAndAuthorized  

logger = logging.getLogger("messaging")




class TenantBaseView(generics.GenericAPIView):
    """Base view to handle tenant schema setting and logging."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise generics.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")


# ---------------------------------------------------------------------------
#  Message‑Type CRUD
# ---------------------------------------------------------------------------
class MessageTypeViewSet(viewsets.ModelViewSet):
    serializer_class = MessageTypeSerializer
    permission_classes = [IsAuthenticated]  #  + [IsSubscribedAndAuthorized]

    # ---------- helpers ----------------------------------------------------
    def _set_schema(self):
        tenant = self.request.tenant
        connection.set_schema(tenant.schema_name)
        return tenant

    # ---------- queryset ---------------------------------------------------
    def get_queryset(self):
        tenant = self._set_schema()
        qs = MessageType.objects.all()
        # If MessageType has a tenant FK uncomment:
        # qs = qs.filter(tenant=tenant)
        return qs

    # ---------- CRUD hooks -------------------------------------------------
    def perform_create(self, serializer):
        tenant = self._set_schema()
        with tenant_context(tenant):
            serializer.save(tenant=tenant)  # drop tenant=… if model lacks FK

    def perform_update(self, serializer):
        tenant = self._set_schema()
        with tenant_context(tenant):
            serializer.save()

    # ---------- extra action ----------------------------------------------
    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        tenant = self._set_schema()
        message_type = self.get_object()
        # … your own “set default” logic here …
        logger.info(
            "MessageType %s set as default for tenant %s",
            message_type.pk,
            tenant.schema_name,
        )
        return Response({"status": "default set"})


# ---------------------------------------------------------------------------
#  Message CRUD, read / unread, stats, forward, reply
# ---------------------------------------------------------------------------
class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]  #  + [IsSubscribedAndAuthorized]

    # ---------- helpers ----------------------------------------------------
    def _set_schema(self):
        tenant = self.request.tenant
        connection.set_schema(tenant.schema_name)
        return tenant

    # ---------- queryset ---------------------------------------------------
    def get_queryset(self):
        tenant = self._set_schema()
        user = self.request.user

        qs = (
            Message.objects.filter(
                Q(sender=user)
                | Q(recipients__recipient=user)
                | Q(recipients__recipient_group__memberships__user=user)
            )
            .distinct()
            .order_by("-sent_at")
        )

        # Optional explicit FK filter if Message has tenant field
        # qs = qs.filter(tenant=tenant)

        # ---- filtering params ----
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
                    & (
                        Q(recipients__recipient=user)
                        | Q(recipients__recipient_group__memberships__user=user)
                    )
                )

        if (df := qp.get("date_from")):
            qs = qs.filter(sent_at__gte=df)
        if (dt := qp.get("date_to")):
            qs = qs.filter(sent_at__lte=dt)

        return qs

    # ---------- serializer context ----------------------------------------
    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    # ---------- create -----------------------------------------------------
    def perform_create(self, serializer):
        tenant = self._set_schema()
        with tenant_context(tenant):
            msg = serializer.save(sender=self.request.user, tenant=tenant)
        UserActivity.objects.create(
            user=self.request.user,
            activity_type="message_sent",
            details=f'{self.request.user} sent "{msg.subject}"',
            status="success",
        )

    # ---------- extra actions ---------------------------------------------
    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        tenant = self._set_schema()
        user = request.user
        cnt = (
            MessageRecipient.objects.filter(
                Q(read=False)
                & (Q(recipient=user) | Q(recipient_group__memberships__user=user))
            )
            .distinct()
            .count()
        )
        return Response({"count": cnt})

    @action(detail=True, methods=["post"])
    def forward(self, request, pk=None):
        tenant = self._set_schema()
        message = self.get_object()
        serializer = ForwardMessageSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with tenant_context(tenant), transaction.atomic():
            fwd = Message.objects.create(
                sender=request.user,
                subject=serializer.validated_data["subject"],
                content=serializer.validated_data["content"],
                message_type=message.message_type,
                parent_message=message,
                is_forward=True,
                tenant=tenant,
            )

            # 1) individual recipients
            for user in serializer.validated_data["recipient_users"]:
                MessageRecipient.objects.create(message=fwd, recipient=user)
                UserActivity.objects.create(
                    user=request.user,
                    activity_type="message_forwarded",
                    details=f'Forwarded "{message.subject}" to {user.email}',
                    status="success",
                )

            # 2) group recipients
            for grp in serializer.validated_data.get("recipient_groups", []):
                MessageRecipient.objects.create(message=fwd, recipient_group=grp)
                UserActivity.objects.create(
                    user=request.user,
                    activity_type="message_forwarded",
                    details=f'Forwarded "{message.subject}" to group {grp.name}',
                    status="success",
                )

            # 3) copy attachments
            for att in message.attachments.all():
                MessageAttachment.objects.create(
                    message=fwd,
                    file=att.file,
                    original_filename=att.original_filename,
                    uploaded_by=request.user,
                    tenant=tenant,
                )
        return Response(self.get_serializer(fwd).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        tenant = self._set_schema()
        message = self.get_object()
        serializer = ReplyMessageSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with tenant_context(tenant):
            reply_msg = Message.objects.create(
                sender=request.user,
                subject=f"Re: {message.subject}",
                content=serializer.validated_data["content"],
                message_type="personal",
                parent_message=message,
                tenant=tenant,
            )
            MessageRecipient.objects.create(message=reply_msg, recipient=message.sender)

        UserActivity.objects.create(
            user=request.user,
            activity_type="message_replied",
            details=f'Replied to "{message.subject}"',
            status="success",
        )
        return Response(
            self.get_serializer(reply_msg).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["patch"])
    def mark_as_read(self, request, pk=None):
        tenant = self._set_schema()
        message = self.get_object()
        user = request.user

        with tenant_context(tenant), transaction.atomic():
            # individual recipient
            if (
                rec := message.recipients.filter(recipient=user).first()
            ) and not rec.read:
                rec.read = True
                rec.read_at = rec.read_at or timezone.now()
                rec.save()

            # group recipients
            group_recs = message.recipients.filter(
                recipient_group__memberships__user=user
            )
            for rec in group_recs:
                if not rec.read:
                    rec.read = True
                    rec.read_at = rec.read_at or timezone.now()
                    rec.save()

        UserActivity.objects.create(
            user=user,
            activity_type="message_read",
            details=f'Marked "{message.subject}" as read',
            status="success",
        )
        return Response({"status": "message marked as read"})

    @action(detail=False, methods=["get"])
    def stats(self, request):
        tenant = self._set_schema()
        total_messages = Message.objects.count()  # already scoped to schema
        return Response({"total_messages": total_messages})


# ---------------------------------------------------------------------------
#  Attachments
# ---------------------------------------------------------------------------
class MessageAttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated]  #  + [IsSubscribedAndAuthorized]

    # ---------- helpers ----------------------------------------------------
    def _set_schema(self):
        tenant = self.request.tenant
        connection.set_schema(tenant.schema_name)
        return tenant

    # ---------- queryset ---------------------------------------------------
    def get_queryset(self):
        tenant = self._set_schema()
        qs = MessageAttachment.objects.all()
        # If there’s a tenant FK:
        # qs = qs.filter(tenant=tenant)
        return qs

    # ---------- serializer context ----------------------------------------
    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    # ---------- create -----------------------------------------------------
    def perform_create(self, serializer):
        tenant = self._set_schema()
        uploaded_file = self.request.FILES.get("file")

        with tenant_context(tenant):
            serializer.save(
                original_filename=uploaded_file.name,
                uploaded_by=self.request.user,
                tenant=tenant,  # drop if model lacks FK
            )

