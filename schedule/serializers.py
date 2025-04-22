from rest_framework import serializers
from .models import Schedule, ScheduleParticipant
from users.serializers import UserSerializer
from groups.serializers import GroupSerializer
from groups.models import Group
from users.models import User

class ScheduleParticipantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    group = GroupSerializer(read_only=True)
    
    class Meta:
        model = ScheduleParticipant
        fields = ['id', 'user', 'group', 'is_optional', 'response_status']

class ScheduleSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    participants = ScheduleParticipantSerializer(many=True, read_only=True)
    participant_users = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        write_only=True,
        required=False
    )
    participant_groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Group.objects.all(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Schedule
        fields = [
            'id', 'title', 'description', 'start_time', 'end_time',
            'location', 'is_all_day', 'creator', 'created_at', 'updated_at',
            'participants', 'participant_users', 'participant_groups'
        ]
        read_only_fields = ['creator', 'created_at', 'updated_at', 'participants']

    def create(self, validated_data):
        participant_users = validated_data.pop('participant_users', [])
        participant_groups = validated_data.pop('participant_groups', [])
        
        schedule = Schedule.objects.create(
            # creator=self.context['request'].user,
            **validated_data
        )
        
        # Create participants
        for user in participant_users:
            ScheduleParticipant.objects.create(
                schedule=schedule,
                user=user
            )
        
        for group in participant_groups:
            ScheduleParticipant.objects.create(
                schedule=schedule,
                group=group
            )
        
        return schedule

    def update(self, instance, validated_data):
        participant_users = validated_data.pop('participant_users', None)
        participant_groups = validated_data.pop('participant_groups', None)
        
        instance = super().update(instance, validated_data)
        
        if participant_users is not None:
            # Update user participants
            current_users = set(instance.participants.filter(user__isnull=False).values_list('user_id', flat=True))
            new_users = set(user.id for user in participant_users)
            
            # Remove participants not in new set
            instance.participants.filter(user_id__in=current_users - new_users).delete()
            
            # Add new participants
            for user_id in new_users - current_users:
                ScheduleParticipant.objects.create(
                    schedule=instance,
                    user_id=user_id
                )
        
        if participant_groups is not None:
            # Update group participants
            current_groups = set(instance.participants.filter(group__isnull=False).values_list('group_id', flat=True))
            new_groups = set(group.id for group in participant_groups)
            
            # Remove participants not in new set
            instance.participants.filter(group_id__in=current_groups - new_groups).delete()
            
            # Add new participants
            for group_id in new_groups - current_groups:
                ScheduleParticipant.objects.create(
                    schedule=instance,
                    group_id=group_id
                )
        
        return instance