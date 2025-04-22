from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from groups.models import Group
from .models import Schedule, ScheduleParticipant
from .serializers import ScheduleSerializer, ScheduleParticipantSerializer
from users.models import UserActivity

class ScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]
        
    def get_queryset(self):
        user = self.request.user
        queryset = Schedule.objects.filter(
            Q(creator=user) | 
            Q(participants__user=user) |
            Q(participants__group__memberships__user=user)
        ).distinct().order_by('-start_time')

        # Apply filters
        search = self.request.query_params.get('search', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        show_past = self.request.query_params.get('show_past', 'false') == 'true'
        
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
            queryset = queryset.filter(start_time__gte=date_from)
        if date_to:
            queryset = queryset.filter(end_time__lte=date_to)
        if not show_past:
            queryset = queryset.filter(end_time__gte=timezone.now())
            
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        schedule = serializer.save(creator=self.request.user)
        
        UserActivity.objects.create(
            user=self.request.user,
            activity_type='schedule_created',
            details=f'{self.request.user} created schedule "{schedule.title}"',
            status='success'
        )
    
    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        schedule = self.get_object()
        response_status = request.data.get('response_status')
        
        if not response_status:
            return Response(
                {'error': 'response_status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update or create participant record for the user
        participant, created = ScheduleParticipant.objects.update_or_create(
            schedule=schedule,
            user=request.user,
            defaults={'response_status': response_status}
        )
        
        UserActivity.objects.create(
            user=request.user,
            activity_type='schedule_response',
            details=f'Responded "{response_status}" to schedule "{schedule.title}"',
            status='success'
        )
        
        return Response(
            ScheduleParticipantSerializer(participant).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        queryset = self.get_queryset().filter(
            end_time__gte=timezone.now()
        ).order_by('start_time')[:10]
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)