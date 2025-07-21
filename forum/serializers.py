from rest_framework import serializers
from .models import Forum, ForumPost
from groups.serializers import GroupSerializer
from groups.models import Group
from users.serializers import UserSerializer
from rest_framework import serializers
from .models import ModerationQueue
from users.serializers import UserSerializer
from users.models import CustomUser

class ForumPostSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True,
        required=False
    )

    class Meta:
        model = ForumPost
        fields = ['id', 'forum', 'author', 'author_id', 'content', 'created_at', 'updated_at', 'is_approved', 'moderated_at', 'moderated_by']
        read_only_fields = ['id', 'created_at', 'updated_at', 'moderated_at', 'moderated_by']

class ForumSerializer(serializers.ModelSerializer):
    allowed_groups = GroupSerializer(many=True, read_only=True)
    allowed_group_ids = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        many=True,
        write_only=True,
        required=False
    )
    created_by = UserSerializer(read_only=True)
    created_by_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True,
        required=False
    )
    posts = ForumPostSerializer(many=True, read_only=True, default=[])
    post_count = serializers.SerializerMethodField()

    class Meta:
        model = Forum
        fields = ['id', 'title', 'description', 'allowed_groups', 'allowed_group_ids', 'is_active', 'created_at', 'updated_at', 'created_by', 'created_by_id', 'posts', 'post_count']
        read_only_fields = ['id', 'created_at', 'updated_at', 'posts']

    def get_post_count(self, obj):
        return obj.posts.count()




class ModerationQueueSerializer(serializers.ModelSerializer):
    reported_by = UserSerializer(read_only=True)
    reported_by_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True,
        required=False
    )
    moderated_by = UserSerializer(read_only=True)
    moderated_by_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    content_snippet = serializers.SerializerMethodField()

    class Meta:
        model = ModerationQueue
        fields = ['id', 'content_type', 'content_id', 'content', 'reported_by', 'reported_by_id', 'reason', 'status', 'moderation_notes', 'moderated_by', 'moderated_by_id', 'created_at', 'updated_at', 'content_snippet']
        read_only_fields = ['id', 'created_at', 'updated_at', 'content_snippet']

    def get_content_snippet(self, obj):
        return obj.content[:100] + ('...' if len(obj.content) > 100 else '')
    
