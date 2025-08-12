import logging
from django.db import transaction, connection
from django_tenants.utils import tenant_context
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import ChatSession, ChatMessage
from core.models import Tenant
from .serializers import ChatSessionSerializer, ChatMessageSerializer

logger = logging.getLogger("ai_chat")

class TenantBaseView(viewsets.GenericViewSet):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise serializers.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        self.tenant = tenant
        logger.debug(f"[{tenant.schema_name}] Schema set for request")

    def get_tenant(self):
        return self.tenant

# ---------------------------------------------------------------------------
#  ChatSession CRUD
# ---------------------------------------------------------------------------

class ChatSessionViewSet(TenantBaseView):
    serializer_class = ChatSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # No need for tenant_context here, schema is already set
        return ChatSession.objects.filter(
            tenant=self.get_tenant(),
            user=self.request.user
        ).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"sessions": serializer.data})

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            session = ChatSession.objects.create(
                tenant=self.get_tenant(),
                user=request.user,
                title="Untitled"
            )
        serializer = self.get_serializer(session)
        return Response({"session": serializer.data}, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        session = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = self.get_serializer(session)
        return Response(serializer.data)

    def destroy(self, request, pk=None):
        with transaction.atomic():
            session = self.get_queryset().get(pk=pk)
            session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ---------------------------------------------------------------------------
#  ChatMessage List (per session)
# ---------------------------------------------------------------------------

class ChatMessageViewSet(TenantBaseView):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        session_id = self.kwargs.get("session_pk")
        return ChatMessage.objects.filter(
            session__id=session_id,
            session__tenant=self.get_tenant(),
            session__user=self.request.user
        ).order_by("timestamp")

    def list(self, request, session_pk=None):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"messages": serializer.data})

    def create(self, request, session_pk=None):
        with transaction.atomic():
            session = ChatSession.objects.get(
                pk=session_pk,
                tenant=self.get_tenant(),
                user=request.user
            )
            message = ChatMessage.objects.create(
                session=session,
                sender=request.data.get("sender"),
                text=request.data.get("text")
            )
        serializer = self.get_serializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
