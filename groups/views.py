import logging
from django.db import connection, transaction
from django_tenants.utils import tenant_context
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.decorators import action
from django.db.models import Prefetch
from django.contrib.auth import get_user_model
from users.models import UserActivity
from .models import Role, Group, GroupMembership
from .serializers import RoleSerializer, GroupSerializer, GroupMembershipSerializer

logger = logging.getLogger('group_management')
User = get_user_model()

class TenantBaseView(viewsets.GenericViewSet):
    """Base view to handle tenant schema setting and validation."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")

class RoleViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage roles for a tenant with filtering by is_default."""
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_default']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Role.objects.all().order_by('name')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Role creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            role = serializer.save()
            UserActivity.objects.create(
                user=request.user,
                activity_type='role_created',
                details=f'Created role "{role.name}"',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Role created: {role.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                logger.error(f"[{tenant.schema_name}] Role update validation failed: {str(e)}")
                raise
            with transaction.atomic():
                role = serializer.save()
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='role_updated',
                    details=f'Updated role "{role.name}"',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Role updated: {role.name}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            instance.delete()
            UserActivity.objects.create(
                user=request.user,
                activity_type='role_deleted',
                details=f'Deleted role "{instance.name}"',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Role deleted: {instance.name}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        """Restrict create, update, and delete actions to admin users."""
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]

class GroupViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage groups for a tenant with role and membership prefetching."""
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Group.objects.prefetch_related(
                Prefetch('role'),
                Prefetch('memberships', queryset=GroupMembership.objects.select_related('user', 'role'))
            ).order_by('name')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Group creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            group = serializer.save()
            UserActivity.objects.create(
                user=request.user,
                activity_type='group_created',
                details=f'Created group "{group.name}"',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Group created: {group.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                logger.error(f"[{tenant.schema_name}] Group update validation failed: {str(e)}")
                raise
            with transaction.atomic():
                group = serializer.save()
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='group_updated',
                    details=f'Updated group "{group.name}"',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Group updated: {group.name}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            instance.delete()
            UserActivity.objects.create(
                user=request.user,
                activity_type='group_deleted',
                details=f'Deleted group "{instance.name}"',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Group deleted: {instance.name}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def update_members(self, request, pk=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant), transaction.atomic():
                group = self.get_object()
                member_ids = request.data.get('members', [])
                if not isinstance(member_ids, list):
                    logger.warning(f"[{tenant.schema_name}] Invalid input for update_members: members must be a list")
                    return Response({"detail": "members must be a list"}, status=status.HTTP_400_BAD_REQUEST)

                # Validate user IDs
                existing_users = set(User.objects.filter(id__in=member_ids).values_list('id', flat=True))
                invalid_ids = set(member_ids) - existing_users
                if invalid_ids:
                    logger.warning(f"[{tenant.schema_name}] Invalid user IDs for group {group.name}: {invalid_ids}")
                    return Response({"detail": f"Invalid user IDs: {invalid_ids}"}, status=status.HTTP_400_BAD_REQUEST)

                # Determine changes
                current_members = set(group.memberships.values_list('user_id', flat=True))
                new_member_ids = set(member_ids) - current_members
                removed_member_ids = current_members - set(member_ids)

                # Add new members
                for user_id in new_member_ids:
                    GroupMembership.objects.create(user_id=user_id, group=group, role=group.role)
                # Remove old members
                group.memberships.filter(user_id__in=removed_member_ids).delete()

                logger.info(f"[{tenant.schema_name}] Updated members for group {group.name}: {len(new_member_ids)} added, {len(removed_member_ids)} removed")
                return Response({
                    "detail": "Group members updated",
                    "added": list(new_member_ids),
                    "removed": list(removed_member_ids),
                    "total_members": group.memberships.count()
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error updating members for group {pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error updating group members"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                group = self.get_object()
                memberships = group.memberships.select_related('user', 'role')
                serializer = GroupMembershipSerializer(memberships, many=True)
                logger.info(f"[{tenant.schema_name}] Retrieved members for group {group.name}")
                return Response(serializer.data)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error retrieving members for group {pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error retrieving group members"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='by-name/(?P<name>[^/.]+)/members')
    def members_by_name(self, request, name=None):
        tenant = request.tenant
        allowed_names = {'trainers', 'instructors', 'teachers', 'assessor'}
        if name.lower() not in allowed_names:
            logger.warning(f"[{tenant.schema_name}] Invalid group name: {name}")
            return Response({"detail": f"Invalid group name. Must be one of: {', '.join(allowed_names)}"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with tenant_context(tenant):
                group = Group.objects.prefetch_related(
                    Prefetch('memberships', queryset=GroupMembership.objects.select_related('user', 'role'))
                ).get(name__iexact=name)
                memberships = group.memberships.all()
                serializer = GroupMembershipSerializer(memberships, many=True)
                logger.info(f"[{tenant.schema_name}] Retrieved members for group {name}")
                return Response(serializer.data)
        except Group.DoesNotExist:
            logger.warning(f"[{tenant.schema_name}] Group {name} not found")
            raise NotFound(f"Group with name '{name}' not found")
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error retrieving members for group {name}: {str(e)}", exc_info=True)
            return Response({"detail": "Error retrieving group members"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        """Restrict create, update, and delete actions to admin users."""
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'update_members'] else [IsAuthenticated()]

class GroupMembershipViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage group memberships for a tenant with filtering."""
    serializer_class = GroupMembershipSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_active', 'group', 'user', 'role', 'is_primary']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = GroupMembership.objects.select_related('user', 'group', 'role')
            user_email = self.request.query_params.get('user_email')
            if user_email:
                queryset = queryset.filter(user__email__icontains=user_email)
            return queryset.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Group membership creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            membership = serializer.save()
            logger.info(f"[{tenant.schema_name}] Group membership created: user {membership.user_id} in group {membership.group.name}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                logger.error(f"[{tenant.schema_name}] Group membership update validation failed: {str(e)}")
                raise
            serializer.save()
            logger.info(f"[{tenant.schema_name}] Group membership updated: user {instance.user_id} in group {instance.group.name}")
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def set_primary(self, request, pk=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                membership = self.get_object()
                if not membership.role:
                    logger.warning(f"[{tenant.schema_name}] Cannot set primary membership without role for user {membership.user_id}")
                    return Response({"detail": "Cannot set as primary without a role"}, status=status.HTTP_400_BAD_REQUEST)
                membership.is_primary = True
                membership.save()
                logger.info(f"[{tenant.schema_name}] Set primary membership for user {membership.user_id} in group {membership.group.name}")
                return Response({
                    "detail": "Membership set as primary",
                    "user_role": membership.role.code
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error setting primary membership {pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error setting primary membership"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        """Restrict create, update, and delete actions to admin users."""
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'set_primary'] else [IsAuthenticated()]