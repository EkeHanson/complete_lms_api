import logging
from django.db import connection, transaction
from django_tenants.utils import tenant_context
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Count
from groups.models import Group
from users.models import UserActivity
from .models import Schedule, ScheduleParticipant
from .serializers import ScheduleSerializer, ScheduleParticipantSerializer

logger = logging.getLogger('schedule')


class TenantBaseView(viewsets.GenericViewSet):
    """Base view to handle tenant schema setting and logging."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")


class ScheduleViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage schedules for a tenant with filtering and participant response handling."""
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]


    def get_queryset(self):
        """Return schedules scoped to the tenant, filtered by user access and query parameters."""
        tenant = self.request.tenant
        user = self.request.user
        search = self.request.query_params.get('search')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        show_past = self.request.query_params.get('show_past', 'false').lower() == 'true'

        with tenant_context(tenant):
            queryset = Schedule.objects.select_related('creator').prefetch_related('participants__user', 'participants__group__memberships__user').filter(
                Q(creator=user) |
                Q(participants__user=user) |
                Q(participants__group__memberships__user=user)
            ).distinct().order_by('-start_time')

            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(location__icontains=search) |
                    Q(creator__email__icontains=search) |
                    Q(creator__first_name__icontains=search) |
                    Q(creator__last_name__icontains=search)
                )
            if date_from:
                try:
                    queryset = queryset.filter(start_time__gte=date_from)
                except ValueError:
                    logger.warning(f"[{tenant.schema_name}] Invalid date_from format: {date_from}")
                    raise ValidationError("Invalid date_from format")
            if date_to:
                try:
                    queryset = queryset.filter(end_time__lte=date_to)
                except ValueError:
                    logger.warning(f"[{tenant.schema_name}] Invalid date_to format: {date_to}")
                    raise ValidationError("Invalid date_to format")
            if not show_past:
                queryset = queryset.filter(end_time__gte=timezone.now())

            logger.debug(f"[{tenant.schema_name}] Schedule query: {queryset.query}")
            return queryset

    def get_serializer_context(self):
        """Include request in serializer context for tenant-aware serialization."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        """Create a new schedule with tenant isolation and activity logging."""
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Schedule creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            schedule = serializer.save(creator=request.user)
            UserActivity.objects.create(
                user=request.user,
                activity_type='schedule_created',
                details=f'Schedule "{schedule.title}" created by user {request.user.id}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Schedule created: {schedule.title} by user {request.user.id}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Update a schedule with tenant isolation and activity logging."""
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            old_data = ScheduleSerializer(instance).data
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                logger.error(f"[{tenant.schema_name}] Schedule update validation failed: {str(e)}")
                raise
            with transaction.atomic():
                serializer.save()
                changes = [
                    f"{field}: {old_data[field]} → {serializer.data[field]}"
                    for field in serializer.data
                    if field in old_data and old_data[field] != serializer.data[field]
                    and field not in ['updated_at', 'created_at']
                ]
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='schedule_updated',
                    details=f'Schedule "{instance.title}" updated. Changes: {"; ".join(changes)}',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Schedule updated: {instance.title} by user {request.user.id}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Delete a schedule with tenant isolation and activity logging."""
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            instance.delete()
            UserActivity.objects.create(
                user=request.user,
                activity_type='schedule_deleted',
                details=f'Schedule "{instance.title}" deleted by user {request.user.id}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Schedule deleted: {instance.title} by user {request.user.id}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """Handle participant response to a schedule."""
        tenant = request.tenant
        response_status = request.data.get('response_status')
        if not response_status:
            logger.warning(f"[{tenant.schema_name}] Missing response_status for schedule response")
            return Response({"detail": "response_status is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with tenant_context(tenant), transaction.atomic():
                schedule = self.get_object()
                participant, created = ScheduleParticipant.objects.update_or_create(
                    schedule=schedule,
                    user=request.user,
                    defaults={'response_status': response_status}
                )
                action = "created" if created else "updated"
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='schedule_response',
                    details=f'Responded "{response_status}" to schedule "{schedule.title}"',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Schedule participant {action}: {schedule.title} by user {request.user.id}")
                return Response(ScheduleParticipantSerializer(participant).data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error processing schedule response: {str(e)}", exc_info=True)
            return Response({"detail": "Error processing response"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Retrieve upcoming schedules for the tenant."""
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                queryset = self.get_queryset().filter(end_time__gte=timezone.now()).order_by('start_time')[:10]
                serializer = self.get_serializer(queryset, many=True)
                logger.info(f"[{tenant.schema_name}] Retrieved {len(serializer.data)} upcoming schedules")
                return Response(serializer.data)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching upcoming schedules: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching upcoming schedules"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Retrieve total number of schedules for the tenant."""
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                total_schedule = Schedule.objects.count()
                logger.info(f"[{tenant.schema_name}] Retrieved schedule stats: {total_schedule} schedules")
                return Response({"total_schedule": total_schedule})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching schedule stats: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching schedule stats"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        """Restrict actions to authenticated users."""
        return [IsAuthenticated()]