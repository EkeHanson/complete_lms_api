from rest_framework import serializers
from .models import Role, Group, GroupMembership
from users.serializers import UserSerializer
from users.models import User

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'


# groups/serializers.py
class GroupSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        source='role',
        write_only=True,
        required=True
    )
    members = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'role', 'role_id', 'is_active', 'members']
        read_only_fields = ['id', 'members']
    
    def get_members(self, obj):
        # Get all memberships with user data
        memberships = obj.memberships.select_related('user').all()
        return [
            {
                'id': m.user.id,
                'first_name': m.user.first_name,
                'last_name': m.user.last_name,
                'email': m.user.email,
                'profile_picture': m.user.profile_picture.url if m.user.profile_picture else None
            }
            for m in memberships
        ]


class GroupMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True
    )
    group = GroupSerializer(read_only=True)
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        source='group',
        write_only=True
    )

    class Meta:
        model = GroupMembership
        fields = '__all__'
        read_only_fields = ('joined_at',)