from rest_framework import serializers
from .models import Role, Group, GroupMembership
from users.serializers import UserSerializer
from users.models import CustomUser

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

class GroupMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True
    )
    group = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        write_only=True
    )
    role = RoleSerializer(read_only=True)

    class Meta:
        model = GroupMembership
        fields = '__all__'
        read_only_fields = ('joined_at',)



class GroupSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), source='role', write_only=True, required=False
    )
    memberships = GroupMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'role', 'role_id', 'is_active', 'is_system', 'memberships']
        read_only_fields = ['is_system', 'memberships']

    def validate(self, attrs):
        if self.instance and self.instance.is_system:
            if 'name' in attrs or 'role' in attrs or 'is_system' in attrs:
                raise serializers.ValidationError(
                    "Cannot modify name, role, or system status of system groups"
                )
        return attrs
    


# class GroupSerializer(serializers.ModelSerializer):
#     role = RoleSerializer(read_only=True)
#     role_id = serializers.IntegerField(write_only=True)  # Add this line
#     memberships = GroupMembershipSerializer(
#         many=True,
#         read_only=True,
#         default=[]
#     )

#     class Meta:
#         model = Group
#         fields = ['id', 'name', 'description', 'role', 'role_id', 'is_active', 'memberships']
#         read_only_fields = ['id', 'memberships']

#     def to_internal_value(self, data):
#         # Ensure role_id is treated as an integer
#         if 'role_id' in data:
#             try:
#                 role_id = int(data['role_id'])
#                 data['role_id'] = role_id
#             except (ValueError, TypeError):
#                 raise serializers.ValidationError({'role_id': 'Must be a valid integer ID'})
#         return super().to_internal_value(data)