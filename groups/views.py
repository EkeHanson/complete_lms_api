from rest_framework import viewsets, permissions
from .models import Role, Group, GroupMembership
from .serializers import RoleSerializer, GroupSerializer, GroupMembershipSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from users.models import UserActivity
from django.db.models import Prefetch


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [AllowAny]
    # permission_classes = [permissions.IsAdminUser]
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
    queryset = Group.objects.select_related('role').prefetch_related(
        Prefetch(
            'memberships',
            queryset=GroupMembership.objects.select_related('user')
        )
    )
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAdminUser]
    

    def perform_create(self, serializer):
        group = serializer.save()
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='group_created',
            details=f'Created group "{group.name}"',
            status='success'
        )

    def perform_update(self, serializer):
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

   # groups/views.py
    @action(detail=True, methods=['post'])
    def update_members(self, request, pk=None):
        group = self.get_object()
        member_ids = request.data.get('members', [])
        
        # Validate member IDs are integers
        try:
            member_ids = [int(id) for id in member_ids]
        except (ValueError, TypeError):
            return Response(
                {'error': 'All member IDs must be integers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        current_members = set(group.memberships.values_list('user_id', flat=True))
        new_members = set(member_ids)
        
        # Members to add
        to_add = new_members - current_members
        for user_id in to_add:
            GroupMembership.objects.create(
                user_id=user_id,
                group=group
            )
        
        # Members to remove
        to_remove = current_members - new_members
        if to_remove:
            group.memberships.filter(user_id__in=to_remove).delete()
        
        # Return the complete updated group
        serializer = self.get_serializer(group)
        return Response(serializer.data)

        
class GroupMembershipViewSet(viewsets.ModelViewSet):
    queryset = GroupMembership.objects.select_related('user', 'group')
    serializer_class = GroupMembershipSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ['is_active', 'group']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by user email if specified
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)
            
        return queryset