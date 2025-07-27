from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from django_tenants.utils import tenant_context
from django.db import transaction, connection
from django.shortcuts import get_object_or_404
from .models import ActivityLog
from .serializers import ActivityLogSerializer
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from django.http import Http404
from rest_framework.response import Response
from users.models import CustomUser
import logging

logger = logging.getLogger('course')

class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ActivityLogViewSet(viewsets.ModelViewSet):
    """Manage activity logs for a tenant with filtering and pagination."""
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = ActivityLog.objects.select_related('user').order_by('-timestamp')
            # Apply filters if provided in query params
            user_id = self.request.query_params.get('user_id')
            activity_type = self.request.query_params.get('activity_type')
            status = self.request.query_params.get('status')
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            if activity_type:
                queryset = queryset.filter(activity_type__icontains=activity_type)
            if status:
                queryset = queryset.filter(status=status)
            return queryset

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for ActivityLog request")

    def list(self, request, *args, **kwargs):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                queryset = self.filter_queryset(self.get_queryset())
                page = self.paginate_queryset(queryset)
                if page is not None:
                    serializer = self.get_serializer(page, many=True)
                    logger.info(f"[{tenant.schema_name}] Listed activity logs, count: {len(serializer.data)}")
                    return self.get_paginated_response(serializer.data)
                serializer = self.get_serializer(queryset, many=True)
                logger.info(f"[{tenant.schema_name}] Listed activity logs, count: {len(serializer.data)}")
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error listing activity logs: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching activity logs"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                instance = self.get_object()
                serializer = self.get_serializer(instance)
                logger.info(f"[{tenant.schema_name}] Retrieved activity log: {instance.activity_type} for user {instance.user}")
                return Response(serializer.data)
        except Http404:
            logger.warning(f"[{tenant.schema_name}] Activity log not found for id: {kwargs.get('pk')}")
            return Response({"detail": "Activity log not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error retrieving activity log: {str(e)}", exc_info=True)
            return Response({"detail": "Error retrieving activity log"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] ActivityLog creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            instance = serializer.save()
            logger.info(f"[{tenant.schema_name}] ActivityLog created: {instance.activity_type} for user {instance.user}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            serializer = self.get_serializer(
                instance,
                data=request.data,
                partial=kwargs.get('partial', False),
                context={'tenant': tenant}
            )
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                logger.error(f"[{tenant.schema_name}] ActivityLog update validation failed: {str(e)}")
                raise
            with transaction.atomic():
                serializer.save()
                logger.info(f"[{tenant.schema_name}] ActivityLog updated: {instance.activity_type} for user {instance.user}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            instance.delete()
            logger.info(f"[{tenant.schema_name}] ActivityLog deleted: {instance.activity_type} for user {instance.user}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='user-activities/(?P<user_id>[^/.]+)')
    def user_activities(self, request, user_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                # Verify user exists
                get_object_or_404(CustomUser, id=user_id)
                queryset = self.get_queryset().filter(user_id=user_id)
                page = self.paginate_queryset(queryset)
                if page is not None:
                    serializer = self.get_serializer(page, many=True)
                    logger.info(f"[{tenant.schema_name}] Listed user activities for user_id {user_id}, count: {len(serializer.data)}")
                    return self.get_paginated_response(serializer.data)
                serializer = self.get_serializer(queryset, many=True)
                logger.info(f"[{tenant.schema_name}] Listed user activities for user_id {user_id}, count: {len(serializer.data)}")
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Http404:
            logger.warning(f"[{tenant.schema_name}] User not found for user_id: {user_id}")
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching user activities for user_id {user_id}: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching user activities"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]