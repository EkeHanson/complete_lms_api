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
from django.db import models

import json

from .models import (
    Category, Course,  Module, Lesson,Badge,UserPoints,UserBadge,
    Resource, Instructor, CourseInstructor, CertificateTemplate,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating
)
from .serializers import ( 
    CategorySerializer, CourseSerializer,BulkEnrollmentSerializer,
    ModuleSerializer, LessonSerializer, ResourceSerializer, InstructorSerializer,
    CourseInstructorSerializer, CertificateTemplateSerializer, SCORMxAPISettingsSerializer,
UserBadgeSerializer, UserPointsSerializer, BadgeSerializer,
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

    @action(detail=False, methods=['get'])
    def most_popular(self, request):
        """
        Get the course with the highest number of enrollments
        Includes enrollment count and instructor information
        """
        try:
            course = Course.objects.annotate(
                enrollment_count=models.Count('enrollments')
            ).order_by('-enrollment_count').first()
            
            if not course:
                return Response(
                    {"error": "No courses found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get instructor name (first instructor if available            
            response_data = {
                "id": course.id,
                "title": course.title,
                "enrollment_count": course.enrollment_count,
                "instructor": "Hanson Abraham",
                # Include other fields you might need
                "thumbnail": course.thumbnail.url if course.thumbnail else None,
                "description": course.description,
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error fetching most popular course: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while fetching the most popular course"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def least_popular(self, request):
        """
        Get the course with the lowest number of enrollments
        Includes enrollment count and instructor information
        """
        try:
            # Filter out courses with 0 enrollments if you want
            course = Course.objects.annotate(
                enrollment_count=models.Count('enrollments')
            ).exclude(enrollment_count=0).order_by('enrollment_count').first()
            
            # If all courses have 0 enrollments, get the first one
            if not course:
                course = Course.objects.annotate(
                    enrollment_count=models.Count('enrollments')
                ).order_by('enrollment_count').first()
                
                if not course:
                    return Response(
                        {"error": "No courses found"},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # Get instructor name (first instructor if available)
            # instructor_name = "No instructor assigned"
            # if course.instructors.exists():
            #     instructor_name = course.instructors.first().name
            # elif Instructor.objects.exists():
            #     # Fallback to any instructor if course has none
            #     instructor_name = Instructor.objects.first().name
            
            response_data = {
                "id": course.id,
                "title": course.title,
                "enrollment_count": course.enrollment_count,
                "instructor": "Ekene-onwon Solomon",
                # Include other fields you might need
                "thumbnail": course.thumbnail.url if course.thumbnail else None,
                "description": course.description,
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error fetching least popular course: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while fetching the least popular course"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
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



class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class EnrollmentViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def list(self, request, course_id=None, user_id=None):
        try:
            # Admin can see all enrollments, regular users only their own
            if request.user.role == "admin":
                enrollments = Enrollment.objects.select_related('user', 'course')
                # Filter by user_id if provided
                if user_id is not None:
                    enrollments = enrollments.filter(user_id=user_id, is_active=True)
            else:
                # Regular users can only see their own enrollments
                enrollments = Enrollment.objects.select_related('user', 'course').filter(
                    user=request.user, 
                    is_active=True
                )
            
            if course_id:
                enrollments = enrollments.filter(course_id=course_id)
                if not enrollments.exists() and not request.user.is_staff:
                    return Response(
                        {"error": "Not enrolled in this course"}, 
                        status=status.HTTP_403_FORBIDDEN
                    )

            # Add ordering to ensure consistent results
            enrollments = enrollments.order_by('-enrolled_at')
            
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(enrollments, request)
            serializer = EnrollmentSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            logger.error(f"Error in EnrollmentView GET: {str(e)}", exc_info=True)
            return Response(
                {
                    "error": "An error occurred while fetching enrollments",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='course/(?P<course_id>[^/.]+)')
    def enroll_to_course(self, request, course_id=None):
        """
        Handle single enrollment to a course
        """
        try:
            course = get_object_or_404(Course, id=course_id, status='Published')
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response(
                    {"error": "user_id is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if already enrolled
            if Enrollment.objects.filter(user_id=user_id, course=course).exists():
                return Response(
                    {"error": "User already enrolled in this course"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            enrollment = Enrollment.objects.create(user_id=user_id, course=course)
            serializer = EnrollmentSerializer(enrollment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error in enrollment: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while processing enrollment"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    @action(detail=False, methods=['post'], url_path='course/(?P<course_id>[^/.]+)/bulk')
    def bulk_enroll(self, request, course_id=None):
        """
        Handle bulk enrollment to a course
        """
        try:
            course = get_object_or_404(Course, id=course_id, status='Published')
            
            # Get user_ids from request data
            user_ids = request.data.get('user_ids', [])
            if not user_ids:
                return Response(
                    {"error": "user_ids array is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check for existing enrollments
            existing = Enrollment.objects.filter(
                user_id__in=user_ids,
                course=course
            ).values_list('user_id', flat=True)
            
            new_enrollments = []
            for user_id in user_ids:
                if user_id not in existing:
                    new_enrollments.append(Enrollment(user_id=user_id, course=course))

            with transaction.atomic():
                Enrollment.objects.bulk_create(new_enrollments)
            
            response_data = {
                "message": f"Successfully enrolled {len(new_enrollments)} users",
                "created": len(new_enrollments),
                "already_enrolled": len(existing),
                "course_id": course_id
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error in bulk enrollment: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while processing bulk enrollment"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    # @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    @action(detail=False, methods=['get'])
    def all_enrollments(self, request):
        """
        Admin-only endpoint to get all enrollments in the system
        """
        try:
            enrollments = Enrollment.objects.filter(
                is_active=True
            ).select_related('user', 'course').order_by('-enrolled_at')
            
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(enrollments, request)
            serializer = EnrollmentSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error fetching all enrollments: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while fetching all enrollments"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    @action(detail=False, methods=['get'])
    def user_enrollments(self, request, user_id=None):
        """
        Get all enrollments with complete course details including:
        - Course info
        - Resources (PDFs, docs, etc.)
        - Modules with lessons (videos, files)
        - Instructor info
        """
        try:
            if user_id is None:
                user_id = request.user.id

            enrollments = (
                Enrollment.objects.filter(user_id=user_id, is_active=True)
                .select_related('course')
                .prefetch_related(
                    'course__resources',
                    'course__modules',
                    'course__modules__lessons',
                    'course__course_instructors',
                    'course__course_instructors__instructor__user',
                )
                .order_by('-enrolled_at')
            )

            result = []
            for enrollment in enrollments:
                course = enrollment.course
                base_url = request.build_absolute_uri('/')[:-1]  # Get base URL

                # Process resources
                resources = []
                for resource in course.resources.all():
                    resource_data = {
                        'id': resource.id,
                        'title': resource.title,
                        'type': resource.resource_type,
                        'url': resource.url,
                        'order': resource.order,
                    }
                    if resource.file:
                        resource_data['file'] = f"{base_url}{resource.file.url}"
                    resources.append(resource_data)

                # Process modules and lessons
                modules = []
                for module in course.modules.all():
                    lessons = []
                    for lesson in module.lessons.all():
                        lesson_data = {
                            'id': lesson.id,
                            'title': lesson.title,
                            'type': lesson.lesson_type,
                            'duration': lesson.duration,
                            'order': lesson.order,
                            'is_published': lesson.is_published,
                        }
                        if lesson.content_url:
                            lesson_data['content_url'] = lesson.content_url
                        if lesson.content_file:
                            lesson_data['content_file'] = f"{base_url}{lesson.content_file.url}"
                        lessons.append(lesson_data)

                    modules.append({
                        'id': module.id,
                        'title': module.title,
                        'order': module.order,
                        'lessons': lessons,
                    })

                # Process instructors
                instructors = []
                for ci in course.course_instructors.all():
                    instructor = ci.instructor
                    instructors.append({
                        'id': instructor.id,
                        'name': instructor.user.get_full_name(),
                        'bio': instructor.bio,
                    })

                result.append({
                    'id': enrollment.id,
                    'course': {
                        'id': course.id,
                        'title': course.title,
                        'description': course.description,
                        'thumbnail': f"{base_url}{course.thumbnail.url}" if course.thumbnail else None,
                        'resources': resources,
                        'modules': modules,
                        'instructors': instructors,
                        # Include other course fields as needed
                    },
                    'enrolled_at': enrollment.enrolled_at,
                    'completed_at': enrollment.completed_at,
                })

            return Response(result)

        except Exception as e:
            logger.error(f"Error fetching user enrollments: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while fetching user enrollments"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminEnrollmentView(APIView):
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        """Admin endpoint to enroll users in courses (single or bulk)"""
        serializer = BulkEnrollmentSerializer(data=request.data, many=isinstance(request.data, list))
        serializer.is_valid(raise_exception=True)
        
        enrollments = []
        for data in serializer.validated_data:
            course_id = data['course_id']
            user_id = data['user_id']
            
            course = get_object_or_404(Course, id=course_id, status='Published')
            if not Enrollment.objects.filter(user_id=user_id, course=course).exists():
                enrollments.append(Enrollment(user_id=user_id, course=course))
        
        Enrollment.objects.bulk_create(enrollments)
        return Response({"message": f"{len(enrollments)} enrollments created successfully"},
                       status=status.HTTP_201_CREATED)



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
    

class BadgeViewSet(ModelViewSet):
    queryset = Badge.objects.filter(is_active=True)
    serializer_class = BadgeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class UserPointsViewSet(ModelViewSet):
    queryset = UserPoints.objects.all()
    serializer_class = UserPointsSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        if self.request.user.is_staff:
            return UserPoints.objects.all()
        return UserPoints.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        course_id = request.query_params.get('course_id')
        queryset = UserPoints.objects.values('user__username').annotate(
            total_points=models.Sum('points')
        ).order_by('-total_points')

        if course_id:
            queryset = queryset.filter(course_id=course_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(page)

class UserBadgeViewSet(ModelViewSet):
    queryset = UserBadge.objects.all()
    serializer_class = UserBadgeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        if self.request.user.is_staff:
            return UserBadge.objects.all()
        return UserBadge.objects.filter(user=self.request.user)