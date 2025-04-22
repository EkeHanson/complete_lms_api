from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets
from django.db import transaction
from rest_framework.exceptions import ValidationError
from users.models import UserActivity
from rest_framework import serializers

import json

from .models import (
    Category, Course,  Module, Lesson,
    Resource, Instructor, CourseInstructor, CertificateTemplate,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating
)
from .serializers import (
    CategorySerializer, CourseSerializer,
    ModuleSerializer, LessonSerializer, ResourceSerializer, InstructorSerializer,
    CourseInstructorSerializer, CertificateTemplateSerializer, SCORMxAPISettingsSerializer,
    LearningPathSerializer, EnrollmentSerializer, CertificateSerializer, CourseRatingSerializer
)
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q
import logging
# Configure logging
logger = logging.getLogger(__name__)

class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer  # You'll need to create this serializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"Validation failed: {serializer.errors}")
            print("Detailed errors:", serializer.errors)
            raise
        
        with transaction.atomic():
            self.perform_create(serializer)
            # Create activity log
            UserActivity.objects.create(
                user=request.user,
                activity_type='category_created',
                details=f'Category "{serializer.data["name"]}" created',
                status='success'
            )
            
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    # For CourseViewSet's update method
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_data = CourseSerializer(instance).data
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
        
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"Validation failed: {serializer.errors}")
            print("Detailed errors:", serializer.errors)
            raise
        
        with transaction.atomic():
            self.perform_update(serializer)
            new_data = serializer.data
            
            # Compare old and new data to find changes
            changes = []
            for field in new_data:
                if field in old_data and old_data[field] != new_data[field] and field not in ['updated_at', 'created_at']:
                    changes.append(f"{field}: {old_data[field]} → {new_data[field]}")
            
            # Create activity log with changes
            UserActivity.objects.create(
                user=request.user,
                activity_type='course_updated',
                details=f'Course "{instance.title}" updated. Changes: {"; ".join(changes)}',
                status='success'
            )
            
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        with transaction.atomic():
            self.perform_destroy(instance)
            # Create activity log
            UserActivity.objects.create(
                user=request.user,
                activity_type='category_deleted',
                details=f'Category "{instance.name}" deleted',
                status='success'
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"Validation failed: {serializer.errors}")
            print("Detailed errors:", serializer.errors)
            raise
        
        with transaction.atomic():
            self.perform_create(serializer)
            # Create activity log
            UserActivity.objects.create(
                user=request.user,
                activity_type='course_created',
                details=f'Course "{serializer.data["title"]}" created',
                status='success'
            )
            
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"Validation failed: {serializer.errors}")
            print("Detailed errors:", serializer.errors)
            raise
        
        with transaction.atomic():
            self.perform_update(serializer)
            # Create activity log
            UserActivity.objects.create(
                user=request.user,
                activity_type='course_updated',
                details=f'Course "{instance.title}" updated',
                status='success'
            )
            
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        with transaction.atomic():
            self.perform_destroy(instance)
            # Create activity log
            UserActivity.objects.create(
                user=request.user,
                activity_type='course_deleted',
                details=f'Course "{instance.title}" deleted',
                status='success'
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        # if not self.request.user.is_staff:
        #     queryset = queryset.filter(status='Published')
        return queryset

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ModuleViewSet(ModelViewSet):
    serializer_class = ModuleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        """
        Filter modules by course_id from the URL parameter.
        """
        course_id = self.kwargs.get('course_id')
        if course_id:
            return Module.objects.filter(course_id=course_id)
        return Module.objects.all()

    def get_object(self):
        """
        Retrieve a specific module, ensuring it belongs to the specified course.
        """
        course_id = self.kwargs.get('course_id')
        module_id = self.kwargs.get('module_id')
        queryset = self.get_queryset()
        module = get_object_or_404(queryset, id=module_id)
        return module

    def perform_create(self, serializer):
        """
        Ensure the module is associated with the specified course during creation.
        """
        course_id = self.kwargs.get('course_id')
        if course_id:
            course = get_object_or_404(Course, id=course_id)
            serializer.save(course=course)
        else:
            serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            logger.info(f"Module created successfully: {serializer.data}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Module creation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        """
        Handle PATCH requests to update a module.
        """
        module = self.get_object()
        serializer = self.get_serializer(module, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Module updated successfully: {serializer.data}")
            return Response(serializer.data)
        else:
            logger.error(f"Module update failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        module_ids = request.data.get('ids', [])
        is_published = request.data.get('is_published')

        # Validate input
        if not isinstance(module_ids, list) or not isinstance(is_published, bool):
            return Response({'error': 'Invalid input'}, status=status.HTTP_400_BAD_REQUEST)

        # Update modules
        updated = Module.objects.filter(id__in=module_ids).update(is_published=is_published)
        return Response({'updated': updated})

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        module_ids = request.data.get('ids', [])

        if not isinstance(module_ids, list):
            return Response({'error': 'Invalid input'}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = Module.objects.filter(id__in=module_ids).delete()
        return Response({'deleted': deleted})

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]


class LessonViewSet(ModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        """
        Filter lessons by course_id and module_id from the URL parameters.
        """
        course_id = self.kwargs.get('course_id')
        module_id = self.kwargs.get('module_id')
        if course_id and module_id:
            return Lesson.objects.filter(module__course_id=course_id, module_id=module_id)
        return Lesson.objects.all()

    def get_object(self):
        """
        Retrieve a specific lesson, ensuring it belongs to the specified course and module.
        """
        course_id = self.kwargs.get('course_id')
        module_id = self.kwargs.get('module_id')
        lesson_id = self.kwargs.get('pk')
        queryset = self.get_queryset()
        lesson = get_object_or_404(queryset, id=lesson_id)
        return lesson

    def perform_create(self, serializer):
        """
        Ensure the lesson is associated with the specified module during creation.
        """
        course_id = self.kwargs.get('course_id')
        module_id = self.kwargs.get('module_id')
        if course_id and module_id:
            module = get_object_or_404(Module, id=module_id, course_id=course_id)
            serializer.save(module=module)
        else:
            raise serializers.ValidationError("Course ID and Module ID are required.")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            logger.info(f"Lesson created successfully: {serializer.data}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Lesson creation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class EnrollmentView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get(self, request, course_id=None):
        if course_id:
            enrollments = Enrollment.objects.filter(user=request.user, course_id=course_id, is_active=True)
            if not enrollments.exists():
                return Response({"error": "Not enrolled in this course"}, status=status.HTTP_403_FORBIDDEN)
        else:
            enrollments = Enrollment.objects.filter(user=request.user, is_active=True)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(enrollments, request)
        serializer = EnrollmentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, status='Published')
        if Enrollment.objects.filter(user=request.user, course=course, is_active=True).exists():
            return Response({"error": "Already enrolled in this course"}, status=status.HTTP_400_BAD_REQUEST)
        
        enrollment = Enrollment.objects.create(user=request.user, course=course)
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class CourseRatingView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get(self, request, course_id=None):
        if course_id:
            ratings = CourseRating.objects.filter(course_id=course_id)
        else:
            ratings = CourseRating.objects.filter(user=request.user)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(ratings, request)
        serializer = CourseRatingSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        if not Enrollment.objects.filter(user=request.user, course=course, is_active=True).exists():
            return Response({"error": "Must be enrolled to rate this course"}, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data.copy()
        data['user'] = request.user.id
        data['course'] = course.id
        serializer = CourseRatingSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.error(f"Course rating creation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LearningPathViewSet(ModelViewSet):
    queryset = LearningPath.objects.filter(is_active=True)
    serializer_class = LearningPathSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination


    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]


class ResourceViewSet(viewsets.ModelViewSet):
    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        """
        Filter resources by course_id from the URL parameter.
        """
        course_id = self.kwargs.get('course_id')
        if course_id:
            return Resource.objects.filter(course_id=course_id).order_by('order')
        return Resource.objects.all()

    def get_object(self):
        """
        Retrieve a specific resource, ensuring it belongs to the specified course.
        """
        course_id = self.kwargs.get('course_id')
        resource_id = self.kwargs.get('pk')
        queryset = self.get_queryset()
        resource = get_object_or_404(queryset, id=resource_id)
        return resource

    def perform_create(self, serializer):
        """
        Ensure the resource is associated with the specified course during creation.
        """
        course_id = self.kwargs.get('course_id')
        course = get_object_or_404(Course, id=course_id)
        serializer.save(course=course)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            logger.info(f"Resource created successfully: {serializer.data}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Resource creation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        resource = self.get_object()
        serializer = self.get_serializer(resource, data=request.data, partial=kwargs.pop('partial', False))
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Resource updated successfully: {serializer.data}")
            return Response(serializer.data)
        else:
            logger.error(f"Resource update failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        resource = self.get_object()
        resource.delete()
        logger.info(f"Resource deleted successfully: {resource.id}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        """
        Restrict create, update, and delete actions to admin users.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['post'])
    def reorder(self, request, course_id):
        resources = request.data.get('resources', [])  # List of {id, order}
        with transaction.atomic():
            for item in resources:
                Resource.objects.filter(id=item['id'], course_id=course_id).update(order=item['order'])
        return Response({'status': 'Resources reordered'})
    

class CertificateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id=None):
        enrollments = Enrollment.objects.filter(user=request.user, is_active=True, completed_at__isnull=False)
        if course_id:
            enrollments = enrollments.filter(course_id=course_id)
        
        certificates = Certificate.objects.filter(enrollment__in=enrollments)
        serializer = CertificateSerializer(certificates, many=True)
        return Response(serializer.data)