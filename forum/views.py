from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Forum, ForumPost
from .serializers import ForumSerializer, ForumPostSerializer
from users.models import UserActivity
from django.db.models import Prefetch, Count
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from groups.models import GroupMembership
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import ModerationQueue
from .serializers import ModerationQueueSerializer
from users.models import UserActivity
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class IsForumMemberOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return GroupMembership.objects.filter(
            user=request.user,
            group__in=obj.allowed_groups.all(),
            is_active=True
        ).exists()

class ForumViewSet(viewsets.ModelViewSet):
    queryset = Forum.objects.prefetch_related(
        Prefetch('allowed_groups'),
        Prefetch('posts'),
        Prefetch('created_by')
    )
    serializer_class = ForumSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsForumMemberOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=False, methods=['get'])
    def stats(self, request):
        active_forums = Forum.objects.filter(is_active=True).count()
        total_posts = ForumPost.objects.count()
        return Response({
            'active_forums': active_forums,
            'total_posts': total_posts
        })

class ForumPostViewSet(viewsets.ModelViewSet):
    queryset = ForumPost.objects.select_related('forum', 'author', 'moderated_by')
    serializer_class = ForumPostSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsForumMemberOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        serializer.save(moderated_by=self.request.user)



class ModerationQueueViewSet(viewsets.ModelViewSet):
    queryset = ModerationQueue.objects.select_related('reported_by', 'moderated_by')
    serializer_class = ModerationQueueSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(moderated_by=self.request.user)

    @action(detail=True, methods=['patch'])
    def moderate(self, request, pk=None):
        item = self.get_object()
        action = request.data.get('action')
        moderation_notes = request.data.get('moderation_notes', '')

        if action not in ['approve', 'reject']:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

        item.status = 'approved' if action == 'approve' else 'rejected'
        item.moderation_notes = moderation_notes
        item.moderated_by = request.user
        item.save()

        # Update related content (e.g., ForumPost)
        if item.content_type == 'forum_post':
            from forum.models import ForumPost
            try:
                post = ForumPost.objects.get(id=item.content_id)
                post.is_approved = (action == 'approve')
                post.moderated_by = request.user
                post.save()
            except ForumPost.DoesNotExist:
                pass

        return Response({'status': f'Content {action}d successfully'})

    @action(detail=False, methods=['get'])
    def pending_count(self, request):
        count = ModerationQueue.objects.filter(status='pending').count()
        return Response({'count': count})