from rest_framework import viewsets, permissions, status, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from .models import UserActivity
from .serializers import UserSerializer, UserActivitySerializer, CustomTokenObtainPairSerializer
import pandas as pd
from django.db import transaction
from django.db import models

import re
from io import BytesIO
from datetime import datetime
from datetime import datetime, timedelta
from rest_framework.parsers import MultiPartParser, FormParser
User = get_user_model()
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
import logging
logger = logging.getLogger(__name__)
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from collections import defaultdict


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        # On successful login, add user data to response
        if response.status_code == 200:
            user = User.objects.get(email=request.data['email'])
            response.data['user'] = UserSerializer(user).data
            
        return response

class RegisterView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # You can add email verification here if needed
        
        return Response({
            'user': serializer.data,
            'message': 'User created successfully'
        }, status=status.HTTP_201_CREATED)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'page_size': self.get_page_size(self.request),
            'results': data
        })

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = CustomPagination
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtering
        role = self.request.query_params.get('role', None)
        status = self.request.query_params.get('status', None)
        search = self.request.query_params.get('search', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if role and role != 'all':
            queryset = queryset.filter(role=role)
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(email__icontains=search)
            )
        if date_from:
            queryset = queryset.filter(signup_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(signup_date__lte=date_to)
            
        return queryset.order_by('-signup_date')
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """General user statistics"""
        total_users = User.objects.count()
        active_users = User.objects.filter(status='active').count()
        
        # Last 30 days signups
        thirty_days_ago = datetime.now() - timedelta(days=30)
        new_signups = User.objects.filter(signup_date__gte=thirty_days_ago).count()
        
        suspicious_activity = User.objects.filter(login_attempts__gt=3).count()
        
        return Response({
            'total_users': total_users,
            'active_users': active_users,
            'new_signups': new_signups,
            'suspicious_activity': suspicious_activity,
        })
    
    @action(detail=False, methods=['get'])
    def role_stats(self, request):
        """Detailed statistics by user role"""
        roles = User.objects.values('role').annotate(
            count=models.Count('id'),
            active_count=models.Count('id', filter=models.Q(status='active')),
            pending_count=models.Count('id', filter=models.Q(status='pending')),
            suspended_count=models.Count('id', filter=models.Q(status='suspended'))
        )
        
        # Convert to a more frontend-friendly format
        role_data = {}
        for role in roles:
            role_data[role['role']] = {
                'total': role['count'],
                'active': role['active_count'],
                'pending': role['pending_count'],
                'suspended': role['suspended_count'],
                'last_30_days': User.objects.filter(
                    role=role['role'],
                    signup_date__gte=datetime.now() - timedelta(days=30)
                ).count()
            }
        
        # Include role descriptions and permissions
        role_info = {
            'admin': {
                'description': 'Full system access',
                'permissions': 'Can manage all users, courses, and system settings'
            },
            'instructor': {
                'description': 'Can create and manage courses',
                'permissions': 'Can create course content, manage learners, and view analytics'
            },
            'learner': {
                'description': 'Can enroll in courses',
                'permissions': 'Can browse courses, enroll in programs, and track progress'
            }
        }
        
        # Combine the data
        result = []
        for role, info in role_info.items():
            stats = role_data.get(role, {
                'total': 0,
                'active': 0,
                'pending': 0,
                'suspended': 0,
                'last_30_days': 0
            })
            
            result.append({
                'role': role,
                'total': stats['total'],
                'active': stats['active'],
                'pending': stats['pending'],
                'suspended': stats['suspended'],
                'last_30_days': stats['last_30_days'],
                'description': info['description'],
                'permissions': info['permissions']
            })
        
        return Response(result)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def bulk_upload(self, request):
        """Handle bulk user upload with transaction support"""
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file uploaded', 'detail': 'The request must contain a file'},
                status=status.HTTP_400_BAD_REQUEST
            )

        file = request.FILES['file']
        
        # Validate file type
        valid_extensions = ['.xlsx', '.xls', '.csv']
        if not any(file.name.lower().endswith(ext) for ext in valid_extensions):
            return Response(
                {'error': 'Invalid file type', 'allowed_types': valid_extensions},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                # Read the file
                if file.name.lower().endswith('.csv'):
                    df = pd.read_csv(file)
                else:  # Excel file
                    df = pd.read_excel(file)
                
                # Process the data
                required_columns = ['firstName', 'lastName', 'email', 'password', 'role']
                if not all(col in df.columns for col in required_columns):
                    return Response(
                        {'error': 'Missing required columns', 'required_columns': required_columns},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Process each row
                created_users = []
                errors = []
                
                for index, row in df.iterrows():
                    try:
                        user_data = {
                            'email': row['email'],
                            'password': row['password'],
                            'first_name': row['firstName'],
                            'last_name': row['lastName'],
                            'role': row['role'].lower(),
                            'status': row.get('status', 'active').lower()
                        }
                        
                        # Additional optional fields
                        optional_fields = ['phone', 'birth_date', 'title', 'bio']
                        for field in optional_fields:
                            if field in row and pd.notna(row[field]):
                                user_data[field] = row[field]
                        
                        # Create user
                        user = User.objects.create_user(**user_data)
                        created_users.append({
                            'id': user.id,
                            'email': user.email,
                            'name': user.get_full_name()
                        })
                    except Exception as e:
                        errors.append({
                            'row': index + 2,
                            'error': str(e),
                            'data': dict(row)
                        })

                return Response({
                    'success': True,
                    'created_count': len(created_users),
                    'created_users': created_users,
                    'error_count': len(errors),
                    'errors': errors
                })

        except Exception as e:
            logger.error(f"Error processing bulk upload: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Error processing file', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        

class UserActivityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserActivity.objects.all()
    serializer_class = UserActivitySerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = self.request.query_params.get('user_id', None)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
            
        return queryset