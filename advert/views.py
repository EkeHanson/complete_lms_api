from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Q
from .models import Advert
from .serializers import AdvertSerializer
from users.models import UserActivity
import logging

logger = logging.getLogger(__name__)

class AdvertViewSet(viewsets.ModelViewSet):
    serializer_class = AdvertSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # Add JSONParser    serializer_class = AdvertSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Advert.objects.all().order_by('-priority', '-created_at')
        
        # Apply filters
        search = self.request.query_params.get('search', None)
        status = self.request.query_params.get('status', None)
        target = self.request.query_params.get('target', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(content__icontains=search)
            )
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        if target and target != 'all':
            queryset = queryset.filter(target=target)
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(end_date__lte=date_to)
            
        return queryset
    
    def create(self, request, *args, **kwargs):
        logger.debug(f"Request data type: {type(request.data)}")
        logger.debug(f"Request data content: {request.data}")
        logger.debug(f"Request headers: {request.headers}")
        logger.debug(f"Request content type: {request.content_type}")
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        
        logger.error(f"Create advert failed. Errors: {serializer.errors}")
        logger.error(f"Data that failed validation: {serializer.initial_data}")
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    def update(self, request, *args, **kwargs):
        logger.debug(f"Request data: {request.data}")
        logger.debug(f"Request headers: {request.headers}")
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            return Response(serializer.data)
        logger.error(f"Update advert failed: {serializer.errors}")
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(creator=self.request.user)
    
    @action(detail=True, methods=['get'])
    def activity(self, request, pk=None):
        advert = self.get_object()
        activities = UserActivity.objects.filter(
            Q(activity_type='advert_created') |
            Q(activity_type='advert_updated') |
            Q(activity_type='advert_deleted'),
            details__contains=advert.title
        ).order_by('-created_at')
        
        page = self.paginate_queryset(activities)
        if page is not None:
            serializer = AdvertActivitySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = AdvertActivitySerializer(activities, many=True)
        return Response(serializer.data)