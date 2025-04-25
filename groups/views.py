from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Role, Group, GroupMembership
from .serializers import RoleSerializer, GroupSerializer, GroupMembershipSerializer
from users.models import UserActivity
from django.db.models import Prefetch
from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import NotFound

User = get_user_model()

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [AllowAny]
    #permission_classes = [permissions.IsAdminUser]
    filterset_fields = ['is_default']

    def perform_create(self, serializer):
        role = serializer.save()
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='role_created',
            details=f'Created role "{role.name}"',
            status='success'
        )

    def perform_update(self, serializer):
        role = serializer.save()
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='role_updated',
            details=f'Updated role "{role.name}"',
            status='success'
        )

    def perform_destroy(self, instance):
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='role_deleted',
            details=f'Deleted role "{instance.name}"',
            status='system'
        )
        instance.delete()

class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.prefetch_related(
        Prefetch('role'),  # Updated to single role
        Prefetch('memberships', queryset=GroupMembership.objects.select_related('user', 'role'))
    )
    serializer_class = GroupSerializer
    permission_classes = [AllowAny]
    # permission_classes = [permissions.IsAdminUser]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            print(f"Error creating group: {str(e)}")  # Log the actual error
            raise
        
    def perform_create(self, serializer):
        group = serializer.save()
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='group_created',
            details=f'Created group "{group.name}"',
            status='success'
        )

    def perform_update(self, serializer):
        print(serializer.validated_data)
        group = serializer.save()
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='group_updated',
            details=f'Updated group "{group.name}"',
            status='success'
        )

    def perform_destroy(self, instance):
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='group_deleted',
            details=f'Deleted group "{instance.name}"',
            status='system'
        )
        instance.delete()

    @action(detail=True, methods=['post'])
    def update_members(self, request, pk=None):
        print("Request data:", request.data)
        
        group = self.get_object()
        member_ids = request.data.get('members', [])
        
        # Validate all user IDs exist
        existing_users = User.objects.filter(id__in=member_ids).values_list('id', flat=True)
        invalid_ids = set(member_ids) - set(existing_users)
        
        if invalid_ids:
            return Response(
                {'error': f'Invalid user IDs: {invalid_ids}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get current memberships
        current_memberships = group.memberships.all()
        current_member_ids = set(current_memberships.values_list('user_id', flat=True))
        
        # Determine changes
        new_member_ids = set(member_ids) - current_member_ids
        removed_member_ids = current_member_ids - set(member_ids)
        
        # Add new members
        for user_id in new_member_ids:
            print(f"Adding user {user_id} with role {group.role}")
            GroupMembership.objects.create(
                user_id=user_id,
                group=group,
                role=group.role  # Assign the group's single role
            )
        
        # Remove old members
        group.memberships.filter(user_id__in=removed_member_ids).delete()
        
        return Response({
            'added': list(new_member_ids),
            'removed': list(removed_member_ids),
            'total_members': group.memberships.count()
        })
        @action(detail=True, methods=['get'])
        def members(self, request, pk=None):
            group = self.get_object()
            memberships = group.memberships.select_related('user', 'role')
            serializer = GroupMembershipSerializer(memberships, many=True)
            return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        group = self.get_object()
        memberships = group.memberships.select_related('user', 'role')
        serializer = GroupMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by-name/(?P<name>[^/.]+)/members')
    def members_by_name(self, request, name=None):
        """
        Fetch members of a group by its name (e.g., trainers, instructors, teachers).
        """
        allowed_names = ['trainers', 'instructors', 'teachers', 'assessor']
        if name.lower() not in allowed_names:
            return Response(
                {'error': f'Invalid group name. Must be one of: {", ".join(allowed_names)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            group = Group.objects.prefetch_related(
                Prefetch('memberships', queryset=GroupMembership.objects.select_related('user', 'role'))
            ).get(name__iexact=name)
        except Group.DoesNotExist:
            raise NotFound(f'Group with name "{name}" not found')

        memberships = group.memberships.all()
        serializer = GroupMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

class GroupMembershipViewSet(viewsets.ModelViewSet):
    queryset = GroupMembership.objects.select_related('user', 'group', 'role')
    serializer_class = GroupMembershipSerializer
    permission_classes = [AllowAny]
    # permission_classes = [permissions.IsAdminUser]
    filterset_fields = ['is_active', 'group', 'user', 'role', 'is_primary']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
            
        return queryset

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        membership = self.get_object()
        
        if not membership.role:
            return Response(
                {'error': 'Cannot set as primary without a role'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        membership.is_primary = True
        membership.save()
        
        return Response(
            {'status': 'Membership set as primary', 'user_role': membership.role.code},
            status=status.HTTP_200_OK
        )