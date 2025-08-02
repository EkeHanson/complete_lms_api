import logging
from django.db import connection, transaction, models
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.db.models import Count
from django_tenants.utils import tenant_context

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination

from users.models import UserActivity, CustomUser
from users.views import TenantBaseView

from utils.storage import get_storage_service

from .models import (
    Assignment, Feedback, Cart, Wishlist, Grade,
    Category, Course, Module, Lesson, Badge, UserPoints, UserBadge, Instructor,
    Resource, CourseInstructor, CertificateTemplate, FAQ, Analytics,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating,
    CourseProgress, LessonCompletion, Quiz
)

from .serializers import (
    AnalyticsSerializer, CategorySerializer, CourseSerializer,
    BulkEnrollmentSerializer, WishlistSerializer, CartSerializer,
    ModuleSerializer, LessonSerializer, 
    AssignmentSerializer,
    CertificateTemplateSerializer, SCORMxAPISettingsSerializer, GradeSerializer,
    UserBadgeSerializer, UserPointsSerializer, BadgeSerializer, FAQSerializer,
    FeedbackSerializer, LearningPathSerializer, EnrollmentSerializer,
    CertificateSerializer, CourseRatingSerializer,
    CourseProgressSerializer, LessonCompletionSerializer, InstructorFullProfileSerializer,
    QuizSerializer
)

logger = logging.getLogger('course')


class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100



# Utility to calculate course progress
def calculate_course_progress(user, course):
    total_lessons = Lesson.objects.filter(module__course=course).count()
    completed_lessons = LessonCompletion.objects.filter(user=user, lesson__module__course=course).count()
    if total_lessons == 0:
        return 0
    return round((completed_lessons / total_lessons) * 100, 2)

# ViewSet for CourseProgress
class CourseProgressViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CourseProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            qs = CourseProgress.objects.filter(tenant_id=tenant.schema_name)
            user = self.request.query_params.get('user')
            course = self.request.query_params.get('course')
            if user:
                qs = qs.filter(user_id=user)
            if course:
                qs = qs.filter(course_id=course)
            return qs

    @action(detail=False, methods=['patch'], url_path='update')
    def update_progress(self, request):
        tenant = request.tenant
        user_id = request.data.get('user')
        course_id = request.data.get('course')
        with tenant_context(tenant):
            obj = get_object_or_404(CourseProgress, user_id=user_id, course_id=course_id)
            obj.progress_percent = calculate_course_progress(obj.user, obj.course)
            obj.save()
            serializer = self.get_serializer(obj)
            return Response(serializer.data)

class TenantAPIView(APIView):
    """Base APIView to handle tenant schema setting and logging."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")

class TenantBaseView(viewsets.GenericViewSet):
    """Base view to handle tenant schema setting and logging."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")

# CertificateTemplateView (already updated in previous response, included for completeness)
class CertificateTemplateView(TenantAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                try:
                    template = CertificateTemplate.objects.get(course_id=course_id)
                    serializer = CertificateTemplateSerializer(template, context={'tenant': {'tenant': tenant}})
                    logger.info(f"[{tenant.schema_name}] Retrieved certificate template for for course {course_id}")
                    return Response(serializer.data)
                except CertificateTemplate.DoesNotExist:
                    default_data = {
                        'is_active': True,
                        'template': 'default',
                        'custom_text': 'Congratulations on completing the course!',
                        'signature_name': 'Course Instructor',
                        'show_date': True,
                        'show_course_name': True,
                        'show_completion_hours': True,
                        'min_score': 80,
                        'require_all_modules': True,
                        'logo': None,
                        'signature': None,
                    }
                    logger.info(f"[{tenant.schema_name}] No template found for course {course_id}, returning default")
                    return Response(default_data)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching certificate template: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching certificate template"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, course_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                course = get_object_or_404(Course, id=course_id)
                data = request.data.copy()
                is_import = data.get('is_import') == 'true'
                logo_url = data.pop('logo_url', None)
                signature_url = data.pop('signature_url', None)

                logo_file = request.FILES.get('logo')
                signature_file = request.FILES.get('signature')

                try:
                    template = CertificateTemplate.objects.get(course=course)
                    serializer = CertificateTemplateSerializer(
                        template,
                        data=data,
                        instance=template,
                        partial=True,
                        context={'tenant': tenant, 'course_id': course_id}
                    )
                except CertificateTemplate.DoesNotExist:
                    data['course'] = course_id
                    serializer = CertificateTemplateSerializer(
                        data=data,
                        context={'tenant': tenant, 'course_id': course_id}
                    )

                if serializer.is_valid():
                    instance = serializer.save()

                    # Handle logo file
                    storage_service = get_storage_service()
                    if logo_file:
                        # Handled in serializer, just ensure old file is managed there
                        pass
                    elif is_import and logo_url:
                        if isinstance(logo_url, list):
                            logo_url = logo_url[0] if logo_url else None
                        if isinstance(logo_url, str) and logo_url:
                            instance.logo = logo_url.lstrip('/media/')
                            instance.save()
                        else:
                            logger.warning(f"[{tenant.schema_name}] Invalid logo_url: {logo_url}")
                            instance.logo = None

                    # Handle signature file
                    if signature_file:
                        # Handled in serializer
                        pass
                    elif is_import and signature_url:
                        if isinstance(signature_url, list):
                            signature_url = signature_url[0] if signature_url else None
                        if isinstance(signature_url, str) and signature_url:
                            instance.signature = signature_url.lstrip('/media/')
                            instance.save()
                        else:
                            logger.warning(f"[{tenant.schema_name}] Invalid signature_url: {signature_url}")
                            instance.signature = None

                    serializer = CertificateTemplateSerializer(instance, context={'tenant': {'tenant': tenant}})
                    logger.info(f"[{tenant.schema_name}] Updated/Created certificate template for course {course_id}")
                    return Response(serializer.data, status=status.HTTP_200_OK if template else status.HTTP_201_CREATED)
                logger.warning(f"[{tenant.schema_name}] Invalid data for certificate template: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"{tenant.schema_name}] Error updating certificate template: {str(e)}", exc_info=True)
            return Response({"detail": "Error updating certificate template"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CategoryViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage categories for a tenant with course count annotation."""
    serializer_class = CategorySerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Category.objects.annotate(course_count=Count('course')).order_by('name')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Category creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            serializer.save(created_by=request.user)
            UserActivity.objects.create(
                user=request.user,
                activity_type='category_created',
                details=f'Category "{serializer.validated_data["name"]}" created',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Category created: {serializer.validated_data['name']}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            old_data = CategorySerializer(instance).data
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                logger.error(f"[{tenant.schema_name}] Category update validation failed: {str(e)}")
                raise
            with transaction.atomic():
                serializer.save()
                changes = [f"{field}: {old_data[field]} → {serializer.data[field]}" 
                         for field in serializer.data 
                         if field in old_data and old_data[field] != serializer.data[field] 
                         and field not in ['updated_at', 'created_at']]
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='category_updated',
                    details=f'Category "{instance.name}" updated. Changes: {"; ".join(changes)}',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Category updated: {instance.name}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            instance.delete()
            UserActivity.objects.create(
                user=request.user,
                activity_type='category_deleted',
                details=f'Category "{instance.name}" deleted',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Category deleted: {instance.name}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]




class CourseViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage courses for a tenant with enrollment and FAQ counts."""
    serializer_class = CourseSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Course.objects.select_related('category').annotate(
                total_enrollments=Count('enrollments', distinct=True),
                faq_count=Count('faqs', distinct=True)
            ).order_by('title')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Course creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            instance = serializer.save(created_by=request.user)
            UserActivity.objects.create(
                user=request.user,
                activity_type='course_created',
                details=f'Course "{instance.title}" created',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Course created: {instance.title}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            serializer = self.get_serializer(
                instance,
                data=request.data,
                partial=kwargs.get('partial', False),
                context={'tenant': tenant}
            )
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                logger.error(f"[{tenant.schema_name}] Course update validation failed: {str(e)}")
                raise
            with transaction.atomic():
                serializer.save()
                logger.info(f"[{tenant.schema_name}] Course updated: {instance.title}")
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='course_updated',
                    details=f'Course "{instance.title}" updated',
                    status='success'
                )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            # Delete associated files
            storage_service = get_storage_service()
            if instance.thumbnail:
                storage_service.delete_file(instance.thumbnail)
            instance.delete()
            UserActivity.objects.create(
                user=request.user,
                activity_type='course_deleted',
                details=f'Course "{instance.title}" deleted',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Course deleted: {instance.title}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def most_popular(self, request):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                course = Course.objects.annotate(
                    enrollment_count=Count('enrollments', distinct=True)
                ).filter(enrollment_count__gt=0).order_by('-enrollment_count').first()
                if not course:
                    logger.info(f"[{tenant.schema_name}] No courses with enrollments found for most_popular")
                    return Response(
                        {"message": "No courses with enrollments yet"},
                        status=status.HTTP_200_OK
                    )
                serializer = CourseSerializer(course, context={'tenant': tenant})
                response_data = {
                    'course': serializer.data,
                    'enrollment_count': Course.objects.filter(id=course.id).annotate(
                        enrollment_count=Count('enrollments', distinct=True)
                    ).values('enrollment_count')[0]['enrollment_count']
                }
                logger.info(f"[{tenant.schema_name}] Most popular course: {course.title}")
                return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching most popular course: {str(e)}", exc_info=True)
            return Response(
                {"detail": "Error fetching most popular course"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def least_popular(self, request):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                course = Course.objects.annotate(
                    enrollment_count=Count('enrollments', distinct=True)
                ).filter(enrollment_count__gt=0).order_by('enrollment_count').first()
                if not course:
                    logger.info(f"[{tenant.schema_name}] No courses with enrollments found for least_popular")
                    return Response(
                        {"message": "No courses with enrollments yet"},
                        status=status.HTTP_200_OK
                    )
                serializer = CourseSerializer(course, context={'tenant': tenant})
                response_data = {
                    'course': serializer.data,
                    'enrollment_count': Course.objects.filter(id=course.id).annotate(
                        enrollment_count=Count('enrollments', distinct=True)
                    ).values('enrollment_count')[0]['enrollment_count']
                }
                logger.info(f"[{tenant.schema_name}] Least popular course: {course.title}")
                return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching least popular course: {str(e)}", exc_info=True)
            return Response(
                {"detail": "Error fetching least popular course"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def list(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            response = super().list(request, *args, **kwargs)
            response.data['total_all_enrollments'] = Enrollment.objects.count()
            logger.info(f"[{tenant.schema_name}] Listed courses with {response.data['total_all_enrollments']} total enrollments")
            return response

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'assign_instructor', 'update_instructor_assignment', 'remove_instructor'] else [IsAuthenticated()]

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def assign_instructor(self, request, pk=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                course = self.get_object()
                serializer = CourseInstructorSerializer(
                    data=request.data,
                    context={'course': course}
                )
                serializer.is_valid(raise_exception=True)
                course_instructor = serializer.save()
                logger.info(f"[{tenant.schema_name}] Instructor assigned to course {course.title}")
                return Response(CourseInstructorSerializer(course_instructor).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Instructor assignment validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error assigning instructor: {str(e)}", exc_info=True)
            return Response({"detail": "Error assigning instructor"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['put'], url_path='instructors/(?P<instructor_id>[^/.]+)')
    def update_instructor_assignment(self, request, pk=None, instructor_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                course = self.get_object()
                course_instructor = get_object_or_404(
                    CourseInstructor, 
                    course=course, 
                    instructor_id=instructor_id
                )
                serializer = CourseInstructorSerializer(
                    course_instructor, 
                    data=request.data, 
                    partial=True, 
                    context={'course': course}
                )
                serializer.is_valid(raise_exception=True)
                course_instructor = serializer.save()
                logger.info(f"[{tenant.schema_name}] Instructor assignment updated for course {course.title}")
                return Response(CourseInstructorSerializer(course_instructor).data)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Instructor assignment update validation failed: {str(e)}")
            raise
        except Http404:
            logger.warning(f"[{tenant.schema_name}] Instructor assignment not found for course {pk} and instructor {instructor_id}")
            return Response({"detail": "Instructor assignment not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error updating instructor assignment: {str(e)}", exc_info=True)
            return Response({"detail": "Error updating instructor assignment"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'], url_path='instructors/(?P<instructor_id>[^/.]+)')
    def remove_instructor(self, request, pk=None, instructor_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                course = self.get_object()
                course_instructor = get_object_or_404(
                    CourseInstructor, 
                    course=course, 
                    instructor_id=instructor_id
                )
                course_instructor.delete()
                logger.info(f"[{tenant.schema_name}] Instructor {instructor_id} removed from course {course.title}")
                return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            logger.warning(f"[{tenant.schema_name}] Instructor {instructor_id} not found for course {pk}")
            return Response({"detail": "Instructor assignment not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error removing instructor: {str(e)}", exc_info=True)
            return Response({"detail": "Error removing instructor"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class ModuleViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage modules for a tenant, scoped to courses."""
    serializer_class = ModuleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        course_id = self.kwargs.get('course_id')
        with tenant_context(tenant):
            queryset = Module.objects.select_related('course')
            if course_id:
                queryset = queryset.filter(course_id=course_id)
            return queryset.order_by('order')

    def get_object(self):
        tenant = self.request.tenant
        course_id = self.kwargs.get('course_id')
        module_id = self.kwargs.get('pk')
        with tenant_context(tenant):
            queryset = self.get_queryset()
            return get_object_or_404(queryset, id=module_id)

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        course_id = self.kwargs.get('course_id')
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Module creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            course = get_object_or_404(Course, id=course_id) if course_id else None
            serializer.save(course=course)
            logger.info(f"[{tenant.schema_name}] Module created: {serializer.validated_data['title']}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                logger.error(f"[{tenant.schema_name}] Module update validation failed: {str(e)}")
                raise
            serializer.save()
            logger.info(f"[{tenant.schema_name}] Module updated: {instance.title}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            # Delete associated lesson files
            storage_service = get_storage_service()
            for lesson in instance.lessons.all():
                if lesson.content_file:
                    storage_service.delete_file(lesson.content_file)
            instance.delete()
            logger.info(f"[{tenant.schema_name}] Module deleted: {instance.title}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request, *args, **kwargs):
        tenant = request.tenant
        module_ids = request.data.get('ids', [])
        is_published = request.data.get('is_published')
        if not isinstance(module_ids, list) or not isinstance(is_published, bool):
            logger.warning(f"[{tenant.schema_name}] Invalid input for bulk_update")
            return Response({"detail": "Invalid input: ids must be a list and is_published must be a boolean"}, status=status.HTTP_400_BAD_REQUEST)
        with tenant_context(tenant), transaction.atomic():
            updated = Module.objects.filter(id__in=module_ids).update(is_published=is_published)
            logger.info(f"[{tenant.schema_name}] Bulk updated {updated} modules")
            return Response({"detail": f"Updated {updated} module(s)"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request, *args, **kwargs):
        tenant = request.tenant
        module_ids = request.data.get('ids', [])
        if not isinstance(module_ids, list):
            logger.warning(f"[{tenant.schema_name}] Invalid input for bulk_delete")
            return Response({"detail": "Invalid input: ids must be a list"}, status=status.HTTP_400_BAD_REQUEST)
        with tenant_context(tenant), transaction.atomic():
            # Delete associated lesson files
            storage_service = get_storage_service()
            for module in Module.objects.filter(id__in=module_ids):
                for lesson in module.lessons.all():
                    if lesson.content_file:
                        storage_service.delete_file(lesson.content_file)
            deleted, _ = Module.objects.filter(id__in=module_ids).delete()
            logger.info(f"[{tenant.schema_name}] Bulk deleted {deleted} modules")
            return Response({"detail": f"Deleted {deleted} module(s)"}, status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_update', 'bulk_delete'] else [IsAuthenticated()]

class LessonViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage lessons for a tenant, scoped to courses and modules."""
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        course_id = self.kwargs.get('course_id')
        module_id = self.kwargs.get('module_id')
        with tenant_context(tenant):
            queryset = Lesson.objects.select_related('module__course')
            if course_id and module_id:
                queryset = queryset.filter(module__course_id=course_id, module_id=module_id)
            return queryset.order_by('order')

    def get_object(self):
        tenant = self.request.tenant
        course_id = self.kwargs.get('course_id')
        module_id = self.kwargs.get('module_id')
        lesson_id = self.kwargs.get('pk')
        with tenant_context(tenant):
            queryset = self.get_queryset()
            return get_object_or_404(queryset, id=lesson_id)

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        course_id = self.kwargs.get('course_id')
        module_id = self.kwargs.get('module_id')
        if not course_id or not module_id:
            logger.warning(f"[{tenant.schema_name}] Missing course_id or module_id for lesson creation")
            raise ValidationError("Course ID and Module ID are required.")
        serializer = self.get_serializer(
            data=request.data,
            context={'tenant': tenant, 'course_id': course_id, 'module_id': module_id}
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Lesson creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            module = get_object_or_404(Module, id=module_id, course_id=course_id)
            serializer.save(module=module)
            logger.info(f"[{tenant.schema_name}] Lesson created: {serializer.validated_data['title']}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            serializer = self.get_serializer(
                instance,
                data=request.data,
                partial=kwargs.get('partial', False),
                context={'tenant': tenant}
            )
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                logger.error(f"[{tenant.schema_name}] Lesson update validation failed: {str(e)}")
                raise
            serializer.save()
            logger.info(f"[{tenant.schema_name}] Lesson updated: {instance.title}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            # Delete associated file
            storage_service = get_storage_service()
            if instance.content_file:
                storage_service.delete_file(instance.content_file)
            instance.delete()
            logger.info(f"[{tenant.schema_name}] Lesson deleted: {instance.title}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]


class EnrollmentViewSet(TenantBaseView, viewsets.ViewSet):
    """Manage course enrollments for a tenant."""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def list(self, request, course_id=None, user_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                queryset = Enrollment.objects.select_related('user', 'course').filter(is_active=True)
                if request.user.role != "admin" and user_id and user_id != str(request.user.id):
                    logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.id} attempted to access user {user_id} enrollments")
                    return Response({"detail": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)
                if request.user.role != "admin":
                    queryset = queryset.filter(user=request.user)
                elif user_id:
                    queryset = queryset.filter(user_id=user_id)
                if course_id:
                    queryset = queryset.filter(course_id=course_id)
                    if not queryset.exists() and not request.user.is_staff:
                        logger.warning(f"[{tenant.schema_name}] User {request.user.id} not enrolled in course {course_id}")
                        return Response({"detail": "Not enrolled in this course"}, status=status.HTTP_403_FORBIDDEN)
                queryset = queryset.order_by('-enrolled_at')
                paginator = self.pagination_class()
                page = paginator.paginate_queryset(queryset, request)
                serializer = EnrollmentSerializer(page, many=True)
                logger.info(f"[{tenant.schema_name}] Listed enrollments for user {request.user.id}")
                return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error listing enrollments: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching enrollments"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='course/(?P<course_id>[^/.]+)')
    def enroll_to_course(self, request, course_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                course = get_object_or_404(Course, id=course_id, status='Published')
                user_id = request.data.get('user_id')
                if not user_id:
                    logger.warning(f"[{tenant.schema_name}] Missing user_id for enrollment")
                    return Response({"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
                if Enrollment.objects.filter(user_id=user_id, course=course).exists():
                    logger.warning(f"[{tenant.schema_name}] User {user_id} already enrolled in course {course_id}")
                    return Response({"detail": "User already enrolled in this course"}, status=status.HTTP_400_BAD_REQUEST)
                enrollment = Enrollment.objects.create(user_id=user_id, course=course)
                serializer = EnrollmentSerializer(enrollment)
                #logger.info(f"[{tenant.schema_name}] User {user_id} enrolled in course {course_id}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Http404:
            logger.warning(f"[{tenant.schema_name}] Course {course_id} not found or not published")
            return Response({"detail": "Course not found or not published"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error enrolling user: {str(e)}", exc_info=True)
            return Response({"detail": "Error processing enrollment"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='course/(?P<course_id>[^/.]+)/bulk')
    def bulk_enroll(self, request, course_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                course = get_object_or_404(Course, id=course_id)  # Remove status='Published' for admin flexibility
                user_ids = request.data.get('user_ids', [])
                if not isinstance(user_ids, list):
                    logger.warning(f"[{tenant.schema_name}] Invalid user_ids for bulk enrollment")
                    return Response({"detail": "user_ids must be a list"}, status=status.HTTP_400_BAD_REQUEST)
                if not user_ids:
                    logger.warning(f"[{tenant.schema_name}] No user_ids provided for bulk enrollment")
                    return Response({"detail": "user_ids is required"}, status=status.HTTP_400_BAD_REQUEST)
                existing = set(Enrollment.objects.filter(user_id__in=user_ids, course=course).values_list('user_id', flat=True))
                new_enrollments = [Enrollment(user_id=user_id, course=course) for user_id in user_ids if user_id not in existing]
                with transaction.atomic():
                    if new_enrollments:
                        Enrollment.objects.bulk_create(new_enrollments)
                    logger.info(f"[{tenant.schema_name}] Bulk enrolled {len(new_enrollments)} users to course {course_id}")
                    return Response({
                        "detail": f"Enrolled {len(new_enrollments)} users",
                        "created": len(new_enrollments),
                        "already_enrolled": len(existing)
                    }, status=status.HTTP_201_CREATED)
                return Response({"detail": "No new enrollments created (all users already enrolled)"}, status=status.HTTP_200_OK)
        except Http404:
            logger.warning(f"[{tenant.schema_name}] Course {course_id} not found")
            return Response({"detail": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error in bulk enrollment: {str(e)}", exc_info=True)
            return Response({"detail": "Error processing bulk enrollment"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def all_enrollments(self, request):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                enrollments = Enrollment.objects.select_related('user', 'course').filter(is_active=True).order_by('-enrolled_at')
                paginator = self.pagination_class()
                page = paginator.paginate_queryset(enrollments, request)
                serializer = EnrollmentSerializer(page, many=True)
                logger.info(f"[{tenant.schema_name}] Listed all enrollments")
                return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching all enrollments: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching all enrollments"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def user_enrollments(self, request, user_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                user_id = user_id or request.user.id
                if request.user.role != "admin" and user_id != str(request.user.id):
                    logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.id} attempted to access user {user_id} enrollments")
                    return Response({"detail": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)
                enrollments = Enrollment.objects.filter(user_id=user_id, is_active=True).select_related('course').prefetch_related(
                    'course__resources', 'course__modules', 'course__modules__lessons', 'course__course_instructors__instructor__user'
                ).order_by('-enrolled_at')
                result = []
                base_url = request.build_absolute_uri('/')[:-1]
                for enrollment in enrollments:
                    course = enrollment.course
                    resources = [
                        {
                            'id': r.id, 'title': r.title, 'type': r.resource_type, 'url': r.url, 'order': r.order,
                            'file': get_storage_service().get_public_url(str(r.file)) if r.file else None
                        } for r in course.resources.all()
                    ]
                    modules = [
                        {
                            'id': m.id, 'title': m.title, 'order': m.order,
                            'lessons': [
                                {
                                    'id': l.id, 'title': l.title, 'type': l.lesson_type, 'duration': l.duration,
                                    'order': l.order, 'is_published': l.is_published, 'content_url': l.content_url,
                                    'content_file': get_storage_service().get_public_url(str(l.content_file)) if l.content_file else None
                                } for l in m.lessons.all()
                            ]
                        } for m in course.modules.all()
                    ]
                    instructors = [
                        {'id': ci.instructor.id, 'name': ci.instructor.user.get_username(), 'bio': ci.instructor.bio}
                        for ci in course.course_instructors.all()
                    ]
                    result.append({
                        'id': enrollment.id,
                        'course': {
                            'id': course.id,
                            'title': course.title,
                            'description': course.description,
                            'thumbnail': f"{base_url}{course.thumbnail.url}" if course.thumbnail else None,
                            'resources': resources,
                            'modules': modules,
                            'instructors': instructors
                        },
                        'enrolled_at': enrollment.enrolled_at,
                        'completed_at': enrollment.completed_at
                    })
                logger.info(f"[{tenant.schema_name}] Retrieved enrollments for user {user_id}")
                return Response(result)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching user enrollments: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching user enrollments"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='my-courses')
    def my_courses(self, request):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                enrollments = Enrollment.objects.filter(user=request.user, is_active=True).select_related('course').prefetch_related(
                    'course__resources', 'course__modules', 'course__modules__lessons', 'course__course_instructors__instructor__user'
                ).order_by('-enrolled_at')
                result = []
                base_url = request.build_absolute_uri('/')[:-1]
                for enrollment in enrollments:
                    course = enrollment.course
                    resources = [
                        {
                            'id': r.id, 'title': r.title, 'type': r.resource_type, 'url': r.url, 'order': r.order,
                            'file': get_storage_service().get_public_url(str(r.file)) if r.file else None
                        } for r in course.resources.all()
                    ]
                    modules = [
                        {
                            'id': m.id, 'title': m.title, 'order': m.order,
                            'lessons': [
                                {
                                    'id': l.id, 'title': l.title, 'type': l.lesson_type, 'duration': l.duration,
                                    'order': l.order, 'is_published': l.is_published, 'content_url': l.content_url,
                                    'content_file': get_storage_service().get_public_url(str(l.content_file)) if l.content_file else None
                                } for l in m.lessons.all()
                            ]
                        } for m in course.modules.all()
                    ]
                    instructors = [
                        {'id': ci.instructor.id, 'name': ci.instructor.user.get_username(), 'bio': ci.instructor.bio}
                        for ci in course.course_instructors.all()
                    ]
                    result.append({
                        'id': enrollment.id,
                        'course': {
                            'id': course.id,
                            'title': course.title,
                            'description': course.description,
                            'thumbnail': f"{base_url}{course.thumbnail.url}" if course.thumbnail else None,
                            'resources': resources,
                            'modules': modules,
                            'instructors': instructors
                        },
                        'enrolled_at': enrollment.enrolled_at,
                        'completed_at': enrollment.completed_at
                    })
                logger.info(f"[{tenant.schema_name}] Retrieved my courses for user {request.user.id}")
                return Response(result)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching my courses: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching my courses"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CourseProgressViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CourseProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            qs = CourseProgress.objects.filter(tenant_id=tenant.schema_name)
            user = self.request.query_params.get('user')
            course = self.request.query_params.get('course')
            if user:
                qs = qs.filter(user_id=user)
            if course:
                qs = qs.filter(course_id=course)
            return qs

    @action(detail=False, methods=['patch'], url_path='update')
    def update_progress(self, request):
        tenant = request.tenant
        user_id = request.data.get('user')
        course_id = request.data.get('course')
        with tenant_context(tenant):
            obj = get_object_or_404(CourseProgress, user_id=user_id, course_id=course_id)
            obj.progress_percent = calculate_course_progress(obj.user, obj.course)
            obj.save()
            serializer = self.get_serializer(obj)
            return Response(serializer.data)

class CourseProgressViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CourseProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return CourseProgress.objects.filter(tenant_id=tenant.schema_name)

    def perform_create(self, serializer):
        tenant = self.request.tenant
        serializer.save(user=self.request.user, tenant_id=tenant.schema_name)


class CourseProgressViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CourseProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return CourseProgress.objects.filter(tenant_id=tenant.schema_name)

    def perform_create(self, serializer):
        tenant = request.tenant
        serializer.save(user=self.request.user, tenant_id=tenant.schema_name)



class AssignmentViewSet(TenantBaseView,viewsets.ModelViewSet):
    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = Assignment.objects.select_related('course', 'user')
            if self.request.user.role != 'admin':
                queryset = queryset.filter(user=self.request.user)
            return queryset.order_by('-due_date')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
        serializer.is_valid(raise_exception=True)
        with tenant_context(tenant):
            serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class FeedbackViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = Feedback.objects.select_related('user', 'course')
            if self.request.user.role != 'admin':
                queryset = queryset.filter(user=self.request.user)
            return queryset.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
        serializer.is_valid(raise_exception=True)
        with tenant_context(tenant):
            serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



class CartViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Cart.objects.filter(user=self.request.user).select_related('course')

class WishlistViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = WishlistSerializer, 
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Wishlist.objects.filter(user=self.request.user).select_related('course')

class GradeViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = GradeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = Grade.objects.select_related('user', 'course', 'assignment')
            if self.request.user.role != 'admin':
                queryset = queryset.filter(user=self.request.user)
            return queryset.order_by('-created_at')



class AnalyticsViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = AnalyticsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Analytics.objects.filter(user=self.request.user).select_related('course')


class LessonCompletionViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = LessonCompletionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            qs = LessonCompletion.objects.all()
            user = self.request.query_params.get('user')
            lesson = self.request.query_params.get('lesson')
            if user:
                qs = qs.filter(user_id=user)
            if lesson:
                qs = qs.filter(lesson_id=lesson)
            return qs

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        user_id = request.data.get('user')
        lesson_id = request.data.get('lesson')
        with tenant_context(tenant):
            obj, created = LessonCompletion.objects.get_or_create(user_id=user_id, lesson_id=lesson_id)
            serializer = self.get_serializer(obj)
            return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)



class InstructorViewSet(TenantBaseView, viewsets.ModelViewSet):
    queryset = Instructor.objects.select_related('user').all()
    serializer_class = InstructorFullProfileSerializer
    permission_classes = [IsAuthenticated]  # Allow instructor access

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        tenant = request.tenant
        user = request.user
        with tenant_context(tenant):
            try:
                instructor = Instructor.objects.select_related('user').get(user=user)
            except Instructor.DoesNotExist:
                return Response({"detail": "You are not an instructor."}, status=status.HTTP_404_NOT_FOUND)
            serializer = self.get_serializer(instructor)
            return Response(serializer.data)

class QuizViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = Quiz.objects.filter(tenant_id=tenant.schema_name)
            course_id = self.request.query_params.get('course')
            module_id = self.request.query_params.get('module')
            if course_id:
                queryset = queryset.filter(course_id=course_id)
            if module_id:
                queryset = queryset.filter(module_id=module_id)
            return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        tenant = self.request.tenant
        serializer.save(tenant_id=tenant.schema_name)

