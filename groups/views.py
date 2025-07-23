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

    def ensure_default_roles_and_groups(self):
        """Ensure 'instructors' and 'learners' roles and groups exist."""
        tenant = self.request.tenant
        with tenant_context(tenant):
            # Define default roles
            default_roles = [
                {
                    'name': 'Instructors',
                    'code': 'instructors',
                    'permissions': ['create_content', 'edit_content', 'grade_assignments', 'view_content'],
                    'is_system': True
                },
                {
                    'name': 'Learners',
                    'code': 'learners',
                    'permissions': ['view_content'],
                    'is_system': True,
                    'is_default': True
                }
            ]

            # Create or update roles
            for role_data in default_roles:
                role, created = Role.objects.get_or_create(
                    code=role_data['code'],
                    defaults={
                        'name': role_data['name'],
                        'permissions': role_data['permissions'],
                        'is_system': True,
                        'is_default': role_data.get('is_default', False)
                    }
                )
                if not created and role.is_system:
                    role.name = role_data['name']
                    role.permissions = role_data['permissions']
                    role.is_default = role_data.get('is_default', False)
                    role.save()

            # Create default groups
            default_groups = [
                {'name': 'All Instructors', 'role_code': 'instructors', 'is_system': True},
                {'name': 'All Learners', 'role_code': 'learners', 'is_system': True}
            ]

            for group_data in default_groups:
                role = Role.objects.get(code=group_data['role_code'])
                Group.objects.get_or_create(
                    name=group_data['name'],
                    defaults={
                        'role': role,
                        'description': f'Default group for {group_data["role_code"]}',
                        'is_active': True,
                        'is_system': True
                    }
                )

class RoleViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage roles for a tenant with filtering by is_default."""
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_default']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            self.ensure_default_roles_and_groups()
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
            if instance.is_system and ('code' in request.data or 'is_system' in request.data):
                logger.error(f"[{tenant.schema_name}] Attempt to modify system role {instance.name}")
                raise ValidationError("Cannot modify code or system status of system roles")
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
        with tenant_context(tenant):
            instance = self.get_object()
            if instance.is_system:
                logger.error(f"[{tenant.schema_name}] Attempt to delete system role {instance.name}")
                raise ValidationError("System roles cannot be deleted")
            with transaction.atomic():
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
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]

class GroupViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage groups for a tenant with role and membership prefetching."""
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            self.ensure_default_roles_and_groups()
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
            if instance.is_system and ('name' in request.data or 'role_id' in request.data or 'is_system' in request.data):
                logger.error(f"[{tenant.schema_name}] Attempt to modify restricted fields of system group {instance.name}")
                raise ValidationError("Cannot modify name, role, or system status of system groups")
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
        

    # def update(self, request, *args, **kwargs):
    #     tenant = request.tenant
    #     with tenant_context(tenant):
    #         instance = self.get_object()
    #         if instance.is_system and ('role_id' in request.data or 'is_system' in request.data):
    #             logger.error(f"[{tenant.schema_name}] Attempt to modify system group {instance.name}")
    #             raise ValidationError("Cannot modify role or system status of system groups")
    #         serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
    #         try:
    #             serializer.is_valid(raise_exception=True)
    #         except ValidationError as e:
    #             logger.error(f"[{tenant.schema_name}] Group update validation failed: {str(e)}")
    #             raise
    #         with transaction.atomic():
    #             group = serializer.save()
    #             UserActivity.objects.create(
    #                 user=request.user,
    #                 activity_type='group_updated',
    #                 details=f'Updated group "{group.name}"',
    #                 status='success'
    #             )
    #             logger.info(f"[{tenant.schema_name}] Group updated: {group.name}")
    #     return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if instance.is_system:
                logger.error(f"[{tenant.schema_name}] Attempt to delete system group {instance.name}")
                raise ValidationError("System groups cannot be deleted")
            with transaction.atomic():
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
    def add_member(self, request, pk=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant), transaction.atomic():
                group = self.get_object()
                user_id = request.data.get('user_id')
                if not user_id:
                    logger.warning(f"[{tenant.schema_name}] Missing user_id for add_member to group {group.name}")
                    return Response({"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
                
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    logger.warning(f"[{tenant.schema_name}] User {user_id} not found for group {group.name}")
                    return Response({"detail": f"User with ID {user_id} not found"}, status=status.HTTP_400_BAD_REQUEST)

                if GroupMembership.objects.filter(group=group, user=user).exists():
                    logger.warning(f"[{tenant.schema_name}] User {user_id} already a member of group {group.name}")
                    return Response({"detail": f"User {user_id} is already a member of group {group.name}"}, status=status.HTTP_400_BAD_REQUEST)

                membership = GroupMembership.objects.create(
                    user=user,
                    group=group,
                    role=group.role,
                    is_active=True
                )
                serializer = GroupMembershipSerializer(membership)
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='group_member_added',
                    details=f'Added user {user.email} to group {group.name}',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Added user {user_id} to group {group.name}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error adding member to group {pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error adding group member"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'], url_path='members/(?P<user_id>\d+)')
    def remove_member(self, request, pk=None, user_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant), transaction.atomic():
                group = self.get_object()
                try:
                    membership = GroupMembership.objects.get(group=group, user_id=user_id)
                except GroupMembership.DoesNotExist:
                    logger.warning(f"[{tenant.schema_name}] Membership for user {user_id} in group {group.name} not found")
                    return Response({"detail": f"User {user_id} is not a member of group {group.name}"}, status=status.HTTP_404_NOT_FOUND)

                user_email = membership.user.email
                membership.delete()
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='group_member_removed',
                    details=f'Removed user {user_email} from group {group.name}',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Removed user {user_id} from group {group.name}")
                return Response({"detail": f"User {user_id} removed from group {group.name}"}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error removing member {user_id} from group {pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error removing group member"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

                existing_users = set(User.objects.filter(id__in=member_ids).values_list('id', flat=True))
                invalid_ids = set(member_ids) - existing_users
                if invalid_ids:
                    logger.warning(f"[{tenant.schema_name}] Invalid user IDs for group {group.name}: {invalid_ids}")
                    return Response({"detail": f"Invalid user IDs: {invalid_ids}"}, status=status.HTTP_400_BAD_REQUEST)

                current_members = set(group.memberships.values_list('user_id', flat=True))
                new_member_ids = set(member_ids) - current_members
                removed_member_ids = current_members - set(member_ids)

                for user_id in new_member_ids:
                    GroupMembership.objects.create(user_id=user_id, group=group, role=group.role)
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
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'update_members', 'add_member', 'remove_member'] else [IsAuthenticated()]


