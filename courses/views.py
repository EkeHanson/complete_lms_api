import logging
from django.db import connection, transaction
from django_tenants.utils import tenant_context
from django.http import Http404
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Count
from rest_framework.pagination import PageNumberPagination
from users.models import UserActivity, CustomUser
from .models import (
    Category, Course, Module, Lesson, Badge, UserPoints, UserBadge, Instructor,
    Resource, CourseInstructor, CertificateTemplate, FAQ,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating
)
from .serializers import (
    CategorySerializer, CourseSerializer, BulkEnrollmentSerializer,
    ModuleSerializer, LessonSerializer, ResourceSerializer,
    CertificateTemplateSerializer, SCORMxAPISettingsSerializer,
    UserBadgeSerializer, UserPointsSerializer, BadgeSerializer, FAQSerializer,
    LearningPathSerializer, EnrollmentSerializer, CertificateSerializer, CourseRatingSerializer
)
from utils.storage import get_storage_service

logger = logging.getLogger('course')

class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

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
                    serializer = CertificateTemplateSerializer(template, context={'tenant': tenant})
                    logger.info(f"[{tenant.schema_name}] Retrieved certificate template for course {course_id}")
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
                        # Handled in serializer
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

                    serializer = CertificateTemplateSerializer(instance, context={'tenant': tenant})
                    logger.info(f"[{tenant.schema_name}] Updated/Created certificate template for course {course_id}")
                    return Response(serializer.data, status=status.HTTP_200_OK if template else status.HTTP_201_CREATED)
                logger.warning(f"[{tenant.schema_name}] Invalid data for certificate template: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error updating certificate template: {str(e)}", exc_info=True)
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
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
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
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False), context={'tenant': tenant})
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
                total_enrollments=Count('enrollment', distinct=True),
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
                    context={'course': course, 'tenant': tenant}
                )
                serializer.is_valid(raise_exception=True)
                course_instructor = serializer.save()
                logger.info(f"[{tenant.schema_name}] Instructor assigned to course {course.title}")
                return Response(CourseInstructorSerializer(course_instructor, context={'tenant': tenant}).data, status=status.HTTP_201_CREATED)
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
                    context={'course': course, 'tenant': tenant}
                )
                serializer.is_valid(raise_exception=True)
                course_instructor = serializer.save()
                logger.info(f"[{tenant.schema_name}] Instructor assignment updated for course {course.title}")
                return Response(CourseInstructorSerializer(course_instructor, context={'tenant': tenant}).data)
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
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
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
            serializer = self.get_serializer(
                instance,
                data=request.data,
                partial=kwargs.get('partial', False),
                context={'tenant': tenant}
            )
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
                serializer = EnrollmentSerializer(page, many=True, context={'tenant': tenant})
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
                serializer = EnrollmentSerializer(enrollment, context={'tenant': tenant})
                logger.info(f"[{tenant.schema_name}] User {user_id} enrolled in course {course_id}")
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
                course = get_object_or_404(Course, id=course_id)
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
                serializer = EnrollmentSerializer(page, many=True, context={'tenant': tenant})
                logger.info(f"[{tenant.schema_name}] Listed all enrollments")
                return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching all enrollments: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching all enrollments"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def user_enrollments(self, request, user_id=None):
        tenant = request.tenant
        storage_service = get_storage_service()
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
                for enrollment in enrollments:
                    course = enrollment.course
                    resources = [
                        {
                            'id': r.id,
                            'title': r.title,
                            'type': r.resource_type,
                            'url': r.url,
                            'order': r.order,
                            'file': storage_service.get_public_url(r.file) if r.file else None
                        }
                        for r in course.resources.all()
                    ]
                    modules = [
                        {
                            'id': m.id,
                            'title': m.title,
                            'order': m.order,
                            'lessons': [
                                {
                                    'id': l.id,
                                    'title': l.title,
                                    'type': l.lesson_type,
                                    'duration': l.duration,
                                    'order': l.order,
                                    'is_published': l.is_published,
                                    'content_url': l.content_url,
                                    'content_file': storage_service.get_public_url(l.content_file) if l.content_file else None
                                }
                                for l in m.lessons.all()
                            ]
                        }
                        for m in course.modules.all()
                    ]
                    instructors = [
                        {'id': ci.instructor.id, 'name': ci.instructor.user.get_full_name(), 'bio': ci.instructor.bio}
                        for ci in course.course_instructors.all()
                    ]
                    result.append({
                        'id': enrollment.id,
                        'course': {
                            'id': course.id,
                            'title': course.title,
                            'description': course.description,
                            'thumbnail': storage_service.get_public_url(course.thumbnail) if course.thumbnail else None,
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



    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_courses(self, request):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                enrollments = Enrollment.objects.filter(user=request.user, is_active=True).select_related('course').order_by('-enrolled_at')
                courses = [enrollment.course for enrollment in enrollments]
                serializer = CourseSerializer(courses, many=True, context={'tenant': tenant})
                return Response(serializer.data)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching my courses: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching my courses"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminEnrollmentView(TenantBaseView, APIView):
    """Admin endpoint to manage single or bulk enrollments."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        tenant = request.tenant
        serializer = BulkEnrollmentSerializer(data=request.data, many=isinstance(request.data, list))
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Admin enrollment validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            enrollments = []
            for data in serializer.validated_data:
                course = get_object_or_404(Course, id=data['course_id'], status='Published')
                if not Enrollment.objects.filter(user_id=data['user_id'], course=course).exists():
                    enrollments.append(Enrollment(user_id=data['user_id'], course=course))
            Enrollment.objects.bulk_create(enrollments)
            logger.info(f"[{tenant.schema_name}] Created {len(enrollments)} enrollments")
            return Response({"detail": f"{len(enrollments)} enrollments created successfully"}, status=status.HTTP_201_CREATED)

class LearningPathViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage learning paths for a tenant."""
    serializer_class = LearningPathSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return LearningPath.objects.filter(is_active=True).order_by('title')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Learning path creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            serializer.save(created_by=request.user)
            logger.info(f"[{tenant.schema_name}] Learning path created: {serializer.validated_data['title']}")
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
                logger.error(f"[{tenant.schema_name}] Learning path update validation failed: {str(e)}")
                raise
            serializer.save()
            logger.info(f"[{tenant.schema_name}] Learning path updated: {instance.title}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            instance.delete()
            logger.info(f"[{tenant.schema_name}] Learning path deleted: {instance.title}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]

class ResourceViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage resources for a tenant, scoped to courses."""
    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        course_id = self.kwargs.get('course_id')
        with tenant_context(tenant):
            queryset = Resource.objects.select_related('course')
            if course_id:
                queryset = queryset.filter(course_id=course_id)
            return queryset.order_by('order')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        course_id = self.kwargs.get('course_id')
        serializer = self.get_serializer(
            data=request.data,
            context={'tenant': tenant, 'course_id': course_id}
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Resource creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            course = get_object_or_404(Course, id=course_id) if course_id else None
            serializer.save(course=course)
            logger.info(f"[{tenant.schema_name}] Resource created: {serializer.validated_data['title']}")
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
                logger.error(f"[{tenant.schema_name}] Resource update validation failed: {str(e)}")
                raise
            serializer.save()
            logger.info(f"[{tenant.schema_name}] Resource updated: {instance.title}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            # Delete associated file
            storage_service = get_storage_service()
            if instance.file:
                storage_service.delete_file(instance.file)
            instance.delete()
            logger.info(f"[{tenant.schema_name}] Resource deleted: {instance.title}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def reorder(self, request, course_id):
        tenant = request.tenant
        resources = request.data.get('resources', [])
        if not isinstance(resources, list):
            logger.warning(f"[{tenant.schema_name}] Invalid input for resource reorder")
            return Response({"detail": "resources must be a list"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with tenant_context(tenant), transaction.atomic():
                for item in resources:
                    Resource.objects.filter(id=item['id'], course_id=course_id).update(order=item['order'])
                logger.info(f"[{tenant.schema_name}] Reordered resources for course {course_id}")
                return Response({"detail": "Resources reordered successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error reordering resources: {str(e)}", exc_info=True)
            return Response({"detail": "Error reordering resources"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'reorder'] else [IsAuthenticated()]

class CertificateView(TenantAPIView, APIView):
    """Manage certificates for a tenant."""
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                enrollments = Enrollment.objects.filter(user=request.user, is_active=True, completed_at__isnull=False)
                if course_id:
                    enrollments = enrollments.filter(course_id=course_id)
                certificates = Certificate.objects.filter(enrollment__in=enrollments).select_related('enrollment__course')
                serializer = CertificateSerializer(certificates, many=True, context={'tenant': tenant})
                logger.info(f"[{tenant.schema_name}] Retrieved certificates for user {request.user.id}")
                return Response(serializer.data)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching certificates: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching certificates"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FAQStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        course_id = request.query_params.get('course_id')
        try:
            with tenant_context(tenant):
                if course_id:
                    faq_count = FAQ.objects.filter(course_id=course_id, is_active=True).count()
                else:
                    faq_count = FAQ.objects.filter(is_active=True).count()
                logger.info(f"[{tenant.schema_name}] Retrieved FAQ count: {faq_count}")
                return Response({'faq_count': faq_count})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching FAQ stats: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching FAQ stats"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BadgeViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage badges for a tenant."""
    serializer_class = BadgeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return Badge.objects.filter(is_active=True).order_by('title')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Badge creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            serializer.save()
            logger.info(f"[{tenant.schema_name}] Badge created: {serializer.validated_data['title']}")
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
                logger.error(f"[{tenant.schema_name}] Badge update validation failed: {str(e)}")
                raise
            serializer.save()
            logger.info(f"[{tenant.schema_name}] Badge updated: {instance.title}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        with tenant_context(tenant), transaction.atomic():
            instance = self.get_object()
            # Delete associated image
            storage_service = get_storage_service()
            if instance.image:
                storage_service.delete_file(instance.image)
            instance.delete()
            logger.info(f"[{tenant.schema_name}] Badge deleted: {instance.title}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]

class UserPointsViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage user points for a tenant."""
    serializer_class = UserPointsSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = UserPoints.objects.select_related('user', 'course')
            if not self.request.user.is_staff:
                queryset = queryset.filter(user=self.request.user)
            return queryset.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] User points creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            serializer.save()
            logger.info(f"[{tenant.schema_name}] User points created for user {serializer.validated_data['user'].id}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = self.request.tenant
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
                logger.error(f"[{tenant.schema_name}] User points update validation failed: {str(e)}")
                raise
            serializer.save()
            logger.info(f"[{tenant.schema_name}] User points updated for user {instance.user.id}")
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        tenant = request.tenant
        course_id = request.query_params.get('course_id')
        try:
            with tenant_context(tenant):
                queryset = UserPoints.objects.values('user__username').annotate(
                    total_points=Count('points')
                ).order_by('-total_points')
                if course_id:
                    queryset = queryset.filter(course_id=course_id)
                paginator = self.pagination_class()
                page = paginator.paginate_queryset(queryset, request)
                logger.info(f"[{tenant.schema_name}] Retrieved leaderboard for course {course_id or 'all'}")
                return paginator.get_paginated_response(page)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error fetching leaderboard: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching leaderboard"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]

class UserBadgeViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage user badges for a tenant."""
    serializer_class = UserBadgeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = UserBadge.objects.select_related('user', 'badge')
            if not self.request.user.is_staff:
                queryset = queryset.filter(user=self.request.user)
            return queryset.order_by('-awarded_at')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] User badge creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            serializer.save()
            logger.info(f"[{tenant.schema_name}] User badge created for user {serializer.validated_data['user'].id}")
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
                logger.error(f"[{tenant.schema_name}] User badge update validation failed: {str(e)}")
                raise
            serializer.save()
            logger.info(f"[{tenant.schema_name}] User badge updated for user {instance.user.id}")
        return Response(serializer.data)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]

class FAQViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage FAQs for a tenant, scoped to courses."""
    serializer_class = FAQSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        tenant = self.request.tenant
        course_id = self.kwargs.get('course_id')
        with tenant_context(tenant):
            queryset = FAQ.objects.select_related('course')
            if course_id:
                queryset = queryset.filter(course_id=course_id)
            return queryset.order_by('order')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        course_id = self.kwargs.get('course_id')
        serializer = self.get_serializer(data=request.data, context={'tenant': tenant, 'course_id': course_id})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[{tenant.schema_name}] FAQ creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            course = get_object_or_404(Course, id=course_id) if course_id else None
            serializer.save(course=course)
            logger.info(f"[{tenant.schema_name}] FAQ created for course {course_id}")
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
                logger.error(f"[{tenant.schema_name}] FAQ update validation failed: {str(e)}")
                raise
            serializer.save()
            logger.info(f"[{tenant.schema_name}] FAQ updated for course {instance.course.id}")
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def reorder(self, request, course_id):
        tenant = request.tenant
        faqs = request.data.get('faqs', [])
        if not isinstance(faqs, list):
            logger.warning(f"[{tenant.schema_name}] Invalid input for FAQ reorder")
            return Response({"detail": "faqs must be a list"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with tenant_context(tenant), transaction.atomic():
                for item in faqs:
                    FAQ.objects.filter(id=item['id'], course_id=course_id).update(order=item['order'])
                logger.info(f"[{tenant.schema_name}] Reordered FAQs for course {course_id}")
                return Response({"detail": "FAQs reordered successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error reordering FAQs: {str(e)}", exc_info=True)
            return Response({"detail": "Error reordering FAQs"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'reorder'] else [IsAuthenticated()]




# import logging
# from django.db import connection, transaction
# from django_tenants.utils import tenant_context
# from django.http import Http404
# from rest_framework import viewsets, status
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated, IsAdminUser
# from rest_framework.exceptions import ValidationError
# from rest_framework.decorators import action
# from django.shortcuts import get_object_or_404
# from django.db.models import Count
# from rest_framework.pagination import PageNumberPagination
# from users.models import UserActivity, CustomUser
# from .models import (
#     Category, Course, Module, Lesson, Badge, UserPoints, UserBadge,Instructor,
#     Resource, CourseInstructor, CertificateTemplate, FAQ,
#     SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating
# )
# from .serializers import (
#     CategorySerializer, CourseSerializer, BulkEnrollmentSerializer,
#     ModuleSerializer, LessonSerializer, ResourceSerializer, InstructorSerializer,
#     CourseInstructorSerializer, CertificateTemplateSerializer, SCORMxAPISettingsSerializer,
#     UserBadgeSerializer, UserPointsSerializer, BadgeSerializer, FAQSerializer,
#     LearningPathSerializer, EnrollmentSerializer, CertificateSerializer, CourseRatingSerializer
# )
# from .models import CertificateTemplate
# from .serializers import CertificateTemplateSerializer
# # views.py, update CertificateTemplateView.patch
# from django.core.files.storage import default_storage
# from django.core.files.base import ContentFile
# import os
# import uuid
# from django.core.files.storage import default_storage
# from django.core.files.base import ContentFile
# import os
# import uuid
# from .models import Course, CertificateTemplate, certificate_logo_path, certificate_signature_path  # Add imports
# from django.core.files.storage import default_storage
# from django.core.files.base import ContentFile
# import os
# import uuid
# from django.conf import settings




# logger = logging.getLogger('lesson')

# class StandardResultsPagination(PageNumberPagination):
#     page_size = 10
#     page_size_query_param = 'page_size'
#     max_page_size = 100


# class TenantAPIView(APIView):
#     """Base APIView to handle tenant schema setting and logging."""
#     def initial(self, request, *args, **kwargs):
#         super().initial(request, *args, **kwargs)
#         tenant = request.tenant
#         if not tenant:
#             logger.error("No tenant associated with the request")
#             raise ValidationError("Tenant not found.")
#         connection.set_schema(tenant.schema_name)
#         logger.debug(f"[{tenant.schema_name}] Schema set for request")

# class TenantBaseView(viewsets.GenericViewSet):
#     """Base view to handle tenant schema setting and logging."""
#     def initial(self, request, *args, **kwargs):
#         super().initial(request, *args, **kwargs)
#         tenant = request.tenant
#         if not tenant:
#             logger.error("No tenant associated with the request")
#             raise ValidationError("Tenant not found.")
#         connection.set_schema(tenant.schema_name)
#         logger.debug(f"[{tenant.schema_name}] Schema set for request")


# # class CertificateTemplateView(TenantAPIView, APIView):
# #     permission_classes = [IsAuthenticated]

# #     def get(self, request, course_id=None):
# #         tenant = request.tenant
# #         try:
# #             with tenant_context(tenant):
# #                 try:
# #                     template = CertificateTemplate.objects.get(course_id=course_id)
# #                     serializer = CertificateTemplateSerializer(template)
# #                     logger.info(f"[{tenant.schema_name}] Retrieved certificate template for course {course_id}")
# #                     return Response(serializer.data)
# #                 except CertificateTemplate.DoesNotExist:
# #                     default_data = {
# #                         'is_active': True,
# #                         'template': 'default',
# #                         'custom_text': 'Congratulations on completing the course!',
# #                         'signature_name': 'Course Instructor',
# #                         'show_date': True,
# #                         'show_course_name': True,
# #                         'show_completion_hours': True,
# #                         'min_score': 80,
# #                         'require_all_modules': True,
# #                         'logo': None,
# #                         'signature': None,
# #                     }
# #                     logger.info(f"[{tenant.schema_name}] No template found for course {course_id}, returning default")
# #                     return Response(default_data)
# #         except Exception as e:
# #             logger.error(f"[{tenant.schema_name}] Error fetching certificate template: {str(e)}", exc_info=True)
# #             return Response({"detail": "Error fetching certificate template"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# #     def patch(self, request, course_id=None):
# #         tenant = request.tenant
# #         try:
# #             with tenant_context(tenant):
# #                 course = get_object_or_404(Course, id=course_id)
# #                 data = request.data.copy()
# #                 is_import = data.get('is_import') == 'true'
# #                 logo_url = data.pop('logo_url', None)
# #                 signature_url = data.pop('signature_url', None)

# #                 # Handle file uploads
# #                 logo_file = request.FILES.get('logo')
# #                 signature_file = request.FILES.get('signature')

# #                 try:
# #                     template = CertificateTemplate.objects.get(course=course)
# #                     serializer = CertificateTemplateSerializer(template, data=data, partial=True)
# #                 except CertificateTemplate.DoesNotExist:
# #                     data['course'] = course_id
# #                     serializer = CertificateTemplateSerializer(data=data)

# #                 if serializer.is_valid():
# #                     instance = serializer.save()

# #                     # Handle logo file
# #                     if logo_file:
# #                         instance.logo = logo_file
# #                     elif is_import and logo_url:
# #                         try:
# #                             # Ensure logo_url is a string
# #                             if isinstance(logo_url, list):
# #                                 logo_url = logo_url[0] if logo_url else None
# #                             if isinstance(logo_url, str) and logo_url:
# #                                 logo_path = logo_url.lstrip('/media/')
# #                                 if default_storage.exists(logo_path):
# #                                     file_name = os.path.basename(logo_path)
# #                                     new_name = f"{uuid.uuid4().hex}_{file_name}"
# #                                     file_path = certificate_logo_path(instance, new_name)
# #                                     with default_storage.open(logo_path, 'rb') as f:
# #                                         instance.logo.save(new_name, ContentFile(f.read()), save=False)
# #                                     logger.info(f"[{tenant.schema_name}] Copied logo to {file_path}")
# #                                 else:
# #                                     logger.warning(f"[{tenant.schema_name}] Logo file {logo_path} does not exist")
# #                                     instance.logo = None
# #                             else:
# #                                 logger.warning(f"[{tenant.schema_name}] Invalid logo_url: {logo_url}")
# #                                 instance.logo = None
# #                         except Exception as e:
# #                             logger.error(f"[{tenant.schema_name}] Error copying logo: {str(e)}")
# #                             instance.logo = None

# #                     # Handle signature file
# #                     if signature_file:
# #                         instance.signature = signature_file
# #                     elif is_import and signature_url:
# #                         try:
# #                             # Ensure signature_url is a string
# #                             if isinstance(signature_url, list):
# #                                 signature_url = signature_url[0] if signature_url else None
# #                             if isinstance(signature_url, str) and signature_url:
# #                                 signature_path = signature_url.lstrip('/media/')
# #                                 if default_storage.exists(signature_path):
# #                                     file_name = os.path.basename(signature_path)
# #                                     new_name = f"{uuid.uuid4().hex}_{file_name}"
# #                                     file_path = certificate_signature_path(instance, new_name)
# #                                     with default_storage.open(signature_path, 'rb') as f:
# #                                         instance.signature.save(new_name, ContentFile(f.read()), save=False)
# #                                     logger.info(f"[{tenant.schema_name}] Copied signature to {file_path}")
# #                                 else:
# #                                     logger.warning(f"[{tenant.schema_name}] Signature file {signature_path} does not exist")
# #                                     instance.signature = None
# #                             else:
# #                                 logger.warning(f"[{tenant.schema_name}] Invalid signature_url: {signature_url}")
# #                                 instance.signature = None
# #                         except Exception as e:
# #                             logger.error(f"[{tenant.schema_name}] Error copying signature: {str(e)}")
# #                             instance.signature = None

# #                     # Save the instance with updated file fields
# #                     instance.save()

# #                     # Update serializer data with full URLs
# #                     serializer = CertificateTemplateSerializer(instance)
# #                     response_data = serializer.data
# #                     if instance.logo:
# #                         response_data['logo'] = f"{settings.MEDIA_URL}{instance.logo.name}"
# #                     if instance.signature:
# #                         response_data['signature'] = f"{settings.MEDIA_URL}{instance.signature.name}"

# #                     logger.info(f"[{tenant.schema_name}] Updated/Created certificate template for course {course_id}")
# #                     return Response(response_data, status=status.HTTP_200_OK if template else status.HTTP_201_CREATED)
# #                 else:
# #                     logger.warning(f"[{tenant.schema_name}] Invalid data for certificate template: {serializer.errors}")
# #                     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
# #         except Exception as e:
# #             logger.error(f"[{tenant.schema_name}] Error updating certificate template: {str(e)}", exc_info=True)
# #             return Response({"detail": "Error updating certificate template"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class CertificateTemplateView(TenantAPIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, course_id=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 try:
#                     template = CertificateTemplate.objects.get(course_id=course_id)
#                     serializer = CertificateTemplateSerializer(template, context={'tenant': {'tenant': tenant}})
#                     logger.info(f"[{tenant.schema_name}] Retrieved certificate template for for course {course_id}")
#                     return Response(serializer.data)
#                 except CertificateTemplate.DoesNotExist:
#                     default_data = {
#                         'is_active': True,
#                         'template': 'default',
#                         'custom_text': 'Congratulations on completing the course!',
#                         'signature_name': 'Course Instructor',
#                         'show_date': True,
#                         'show_course_name': True,
#                         'show_completion_hours': True,
#                         'min_score': 80,
#                         'require_all_modules': True,
#                         'logo': None,
#                         'signature': None,
#                     }
#                     logger.info(f"[{tenant.schema_name}] No template found for course {course_id}, returning default")
#                     return Response(default_data)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error fetching certificate template: {str(e)}", exc_info=True)
#             return Response({"detail": "Error fetching certificate template"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def patch(self, request, course_id=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 course = get_object_or_404(Course, id=course_id)
#                 data = request.data.copy()
#                 is_import = data.get('is_import') == 'true'
#                 logo_url = data.pop('logo_url', None)
#                 signature_url = data.pop('signature_url', None)

#                 logo_file = request.FILES.get('logo')
#                 signature_file = request.FILES.get('signature')

#                 try:
#                     template = CertificateTemplate.objects.get(course=course)
#                     serializer = CertificateTemplateSerializer(
#                         template,
#                         data=data,
#                         instance=template,
#                         partial=True,
#                         context={'tenant': tenant, 'course_id': course_id}
#                     )
#                 except CertificateTemplate.DoesNotExist:
#                     data['course'] = course_id
#                     serializer = CertificateTemplateSerializer(
#                         data=data,
#                         context={'tenant': tenant, 'course_id': course_id}
#                     )

#                 if serializer.is_valid():
#                     instance = serializer.save()

#                     # Handle logo file
#                     storage_service = get_storage_service()
#                     if logo_file:
#                         # Handled in serializer, just ensure old file is managed there
#                         pass
#                     elif is_import and logo_url:
#                         if isinstance(logo_url, list):
#                             logo_url = logo_url[0] if logo_url else None
#                         if isinstance(logo_url, str) and logo_url:
#                             instance.logo = logo_url.lstrip('/media/')
#                             instance.save()
#                         else:
#                             logger.warning(f"[{tenant.schema_name}] Invalid logo_url: {logo_url}")
#                             instance.logo = None

#                     # Handle signature file
#                     if signature_file:
#                         # Handled in serializer
#                         pass
#                     elif is_import and signature_url:
#                         if isinstance(signature_url, list):
#                             signature_url = signature_url[0] if signature_url else None
#                         if isinstance(signature_url, str) and signature_url:
#                             instance.signature = signature_url.lstrip('/media/')
#                             instance.save()
#                         else:
#                             logger.warning(f"[{tenant.schema_name}] Invalid signature_url: {signature_url}")
#                             instance.signature = None

#                     serializer = CertificateTemplateSerializer(instance, context={'tenant': {'tenant': tenant}})
#                     logger.info(f"[{tenant.schema_name}] Updated/Created certificate template for course {course_id}")
#                     return Response(serializer.data, status=status.HTTP_200_OK if template else status.HTTP_201_CREATED)
#                 logger.warning(f"[{tenant.schema_name}] Invalid data for certificate template: {serializer.errors}")
#                 return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             logger.error(f"{tenant.schema_name}] Error updating certificate template: {str(e)}", exc_info=True)
#             return Response({"detail": "Error updating certificate template"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class CategoryViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage categories for a tenant with course count annotation."""
#     serializer_class = CategorySerializer
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         with tenant_context(tenant):
#             return Category.objects.annotate(course_count=Count('course')).order_by('name')

#     def create(self, request, *args, **kwargs):
#         tenant = request.tenant
#         serializer = self.get_serializer(data=request.data)
#         try:
#             serializer.is_valid(raise_exception=True)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Category creation validation failed: {str(e)}")
#             raise
#         with tenant_context(tenant), transaction.atomic():
#             serializer.save(created_by=request.user)
#             UserActivity.objects.create(
#                 user=request.user,
#                 activity_type='category_created',
#                 details=f'Category "{serializer.validated_data["name"]}" created',
#                 status='success'
#             )
#             logger.info(f"[{tenant.schema_name}] Category created: {serializer.validated_data['name']}")
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     def update(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant):
#             instance = self.get_object()
#             old_data = CategorySerializer(instance).data
#             serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
#             try:
#                 serializer.is_valid(raise_exception=True)
#             except ValidationError as e:
#                 logger.error(f"[{tenant.schema_name}] Category update validation failed: {str(e)}")
#                 raise
#             with transaction.atomic():
#                 serializer.save()
#                 changes = [f"{field}: {old_data[field]} → {serializer.data[field]}" 
#                          for field in serializer.data 
#                          if field in old_data and old_data[field] != serializer.data[field] 
#                          and field not in ['updated_at', 'created_at']]
#                 UserActivity.objects.create(
#                     user=request.user,
#                     activity_type='category_updated',
#                     details=f'Category "{instance.name}" updated. Changes: {"; ".join(changes)}',
#                     status='success'
#                 )
#                 logger.info(f"[{tenant.schema_name}] Category updated: {instance.name}")
#         return Response(serializer.data)

#     def destroy(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant), transaction.atomic():
#             instance = self.get_object()
#             instance.delete()
#             UserActivity.objects.create(
#                 user=request.user,
#                 activity_type='category_deleted',
#                 details=f'Category "{instance.name}" deleted',
#                 status='success'
#             )
#             logger.info(f"[{tenant.schema_name}] Category deleted: {instance.name}")
#         return Response(status=status.HTTP_204_NO_CONTENT)

#     def get_permissions(self):
#         return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]




# class CourseViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage courses for a tenant with enrollment and FAQ counts."""
#     serializer_class = CourseSerializer
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         with tenant_context(tenant):
#             return Course.objects.select_related('category').annotate(
#                 total_enrollments=Count('enrollments', distinct=True),
#                 faq_count=Count('faqs', distinct=True)
#             ).order_by('title')




#     # def create(self, request, *args, **kwargs):
#     #     tenant = request.tenant
#     #     serializer = self.get_serializer(data=request.data)
#     #     try:
#     #         serializer.is_valid(raise_exception=True)
#     #     except ValidationError as e:
#     #         logger.error(f"[{tenant.schema_name}] Course creation validation failed: {str(e)}")
#     #         raise
#     #     with tenant_context(tenant), transaction.atomic():
#     #         thumbnail_file = serializer.validated_data.pop('thumbnail', None)
#     #         instance = serializer.save(created_by=request.user)
#     #         if thumbnail_file:
#     #             file_name = f"courses/{instance.slug}/thumbnails/{uuid.uuid4().hex}_{thumbnail_file.name}"
#     #             res = upload_to_supabase(thumbnail_file, file_name, content_type=thumbnail_file.content_type)
#     #             if res.status_code == 200:
#     #                 instance.thumbnail = file_name
#     #                 instance.save()
#     #             else:
#     #                 logger.error(f"[{tenant.schema_name}] Failed to upload thumbnail to Supabase: {res.content}")
#     #                 raise serializers.ValidationError("Failed to upload thumbnail to Supabase")
#     #         UserActivity.objects.create(
#     #             user=request.user,
#     #             activity_type='course_created',
#     #             details=f'Course "{serializer.validated_data["title"]}" created',
#     #             status='success'
#     #         )
#     #         logger.info(f"[{tenant.schema_name}] Course created: {serializer.validated_data['title']}")
#     #     return Response(serializer.data, status=status.HTTP_201_CREATED)


#     # def update(self, request, *args, **kwargs):
#     #     tenant = request.tenant
#     #     with tenant_context(tenant):
#     #         instance = self.get_object()
#     #         # print("request.data")
#     #         # print(request.data)
#     #         # print("request.data")
#     #         serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
#     #         try:
#     #             serializer.is_valid(raise_exception=True)
#     #         except ValidationError as e:
#     #             logger.error(f"[{tenant.schema_name}] Course update validation failed: {str(e)}")
#     #             raise
#     #         with transaction.atomic():
#     #             serializer.save()
#     #             logger.info(f"[{tenant.schema_name}] Course updated: {instance.title}")
#     #             UserActivity.objects.create(
#     #                 user=request.user,
#     #                 activity_type='course_updated',
#     #                 details=f'Course "{instance.title}" updated',
#     #                 status='success'
#     #             )
#     #     return Response(serializer.data)

#     def create(self, request, *args, **kwargs):
#         tenant = request.tenant
#         serializer = self.get_serializer(data=request.data, context={'tenant': tenant})
#         try:
#             serializer.is_valid(raise_exception=True)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Course creation validation failed: {str(e)}")
#             raise
#         with tenant_context(tenant), transaction.atomic():
#             instance = serializer.save(created_by=request.user)
#             UserActivity.objects.create(
#                 user=request.user,
#                 activity_type='course_created',
#                 details=f'course_created',
#                 status='success'
#             )
#             logger.info(f"[{tenant.schema_name}] Course created: {instance.title}")
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     def update(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant):
#             instance = self.get_object()
#             serializer = self.get_serializer(
#                 instance,
#                 data=request.data,
#                 partial=kwargs.get('partial', False),
#                 context={'tenant': {'tenant': tenant}}
#             )
#             try:
#                 serializer.is_valid(raise_exception=True)
#             except ValidationError as e:
#                 logger.error(f"[{tenant.schema_name}] Course update validation failed: {str(e)}")
#                 raise
#             with transaction.atomic():
#                 serializer.save()
#                 logger.info(f"[{tenant.schema_name}] Course updated: {instance.title}")
#                 UserActivity.objects.create(
#                     user=request.user,
#                     activity_type='course_updated',
#                     details=f'{course_updated.title}" updated',
#                     status='success'
#                 )
#         return Response(serializer.data)


#     def destroy(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant), transaction.atomic():
#             instance = self.get_object()
#             instance.delete()
#             UserActivity.objects.create(
#                 user=request.user,
#                 activity_type='course_deleted',
#                 details=f'Course "{instance.title}" deleted',
#                 status='success'
#             )
#             logger.info(f"[{tenant.schema_name}] Course deleted: {instance.title}")
#         return Response(status=status.HTTP_204_NO_CONTENT)


#     @action(detail=False, methods=['get'])
#     def most_popular(self, request):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 course = Course.objects.annotate(
#                     enrollment_count=Count('enrollments', distinct=True)
#                 ).filter(enrollment_count__gt=0).order_by('-enrollment_count').first()
#                 if not course:
#                     logger.info(f"[{tenant.schema_name}] No courses with enrollments found for most_popular")
#                     return Response(
#                         {"message": "No courses with enrollments yet"},
#                         status=status.HTTP_200_OK
#                     )
#                 serializer = CourseSerializer(course)
#                 response_data = {
#                     'course': serializer.data,
#                     'enrollment_count': Course.objects.filter(id=course.id).annotate(
#                         enrollment_count=Count('enrollments', distinct=True)
#                     ).values('enrollment_count')[0]['enrollment_count']
#                 }
#                 logger.info(f"[{tenant.schema_name}] Most popular course: {course.title}")
#                 return Response(response_data, status=status.HTTP_200_OK)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error fetching most popular course: {str(e)}", exc_info=True)
#             return Response(
#                 {"detail": "Error fetching most popular course"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#     @action(detail=False, methods=['get'])
#     def least_popular(self, request):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 course = Course.objects.annotate(
#                     enrollment_count=Count('enrollments', distinct=True)
#                 ).filter(enrollment_count__gt=0).order_by('enrollment_count').first()
#                 if not course:
#                     logger.info(f"[{tenant.schema_name}] No courses with enrollments found for least_popular")
#                     return Response(
#                         {"message": "No courses with enrollments yet"},
#                         status=status.HTTP_200_OK
#                     )
#                 serializer = CourseSerializer(course)
#                 response_data = {
#                     'course': serializer.data,
#                     'enrollment_count': Course.objects.filter(id=course.id).annotate(
#                         enrollment_count=Count('enrollments', distinct=True)
#                     ).values('enrollment_count')[0]['enrollment_count']
#                 }
#                 logger.info(f"[{tenant.schema_name}] Least popular course: {course.title}")
#                 return Response(response_data, status=status.HTTP_200_OK)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error fetching least popular course: {str(e)}", exc_info=True)
#             return Response(
#                 {"detail": "Error fetching least popular course"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#     def list(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant):
#             response = super().list(request, *args, **kwargs)
#             response.data['total_all_enrollments'] = Enrollment.objects.count()
#             logger.info(f"[{tenant.schema_name}] Listed courses with {response.data['total_all_enrollments']} total enrollments")
#             return response

#     def get_permissions(self):
#         return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'assign_instructor', 'update_instructor_assignment', 'remove_instructor'] else [IsAuthenticated()]
        
#     def list(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant):
#             response = super().list(request, *args, **kwargs)
#             response.data['total_all_enrollments'] = Enrollment.objects.count()
#             logger.info(f"[{tenant.schema_name}] Listed courses with {response.data['total_all_enrollments']} total enrollments")
#             return response

#     def get_permissions(self):
#         return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]


#     # @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
#     # def assign_instructor(self, request, pk=None):
#     #     tenant = request.tenant
#     #     try:
#     #         with tenant_context(tenant):
#     #             course = self.get_object()
#     #             serializer = CourseInstructorSerializer(
#     #                 data=request.data,
#     #                 context={'course': course}
#     #             )
#     #             serializer.is_valid(raise_exception=True)
#     #             course_instructor = serializer.save()
#     #             logger.info(f"[{tenant.schema_name}] Instructor assigned to course {course.title}")
#     #             return Response(CourseInstructorSerializer(course_instructor).data, status=status.HTTP_201_CREATED)
#     #     except ValidationError as e:
#     #         logger.error(f"[{tenant.schema_name}] Instructor assignment validation failed: {str(e)}")
#     #         raise
#     #     except Exception as e:
#     #         logger.error(f"[{tenant.schema_name}] Error assigning instructor: {str(e)}", exc_info=True)
#     #         return Response({"detail": "Error assigning instructor"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



#     @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
#     def assign_instructor(self, request, pk=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 course = self.get_object()
#                 serializer = CourseInstructorSerializer(
#                     data=request.data,
#                     context={'course': course}
#                 )
#                 serializer.is_valid(raise_exception=True)
#                 course_instructor = serializer.save()
#                 logger.info(f"[{tenant.schema_name}] Instructor assigned to course {course.title}")
#                 return Response(CourseInstructorSerializer(course_instructor).data, status=status.HTTP_201_CREATED)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Instructor assignment validation failed: {str(e)}")
#             raise
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error assigning instructor: {str(e)}", exc_info=True)
#             return Response({"detail": "Error assigning instructor"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     @action(detail=True, methods=['put'], url_path='instructors/(?P<instructor_id>[^/.]+)')
#     def update_instructor_assignment(self, request, pk=None, instructor_id=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 course = self.get_object()
#                 course_instructor = get_object_or_404(
#                     CourseInstructor, 
#                     course=course, 
#                     instructor_id=instructor_id
#                 )
#                 serializer = CourseInstructorSerializer(
#                     course_instructor, 
#                     data=request.data, 
#                     partial=True, 
#                     context={'course': course}
#                 )
#                 serializer.is_valid(raise_exception=True)
#                 course_instructor = serializer.save()
#                 logger.info(f"[{tenant.schema_name}] Instructor assignment updated for course {course.title}")
#                 return Response(CourseInstructorSerializer(course_instructor).data)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Instructor assignment update validation failed: {str(e)}")
#             raise
#         except Http404:
#             logger.warning(f"[{tenant.schema_name}] Instructor assignment not found for course {pk} and instructor {instructor_id}")
#             return Response({"detail": "Instructor assignment not found"}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error updating instructor assignment: {str(e)}", exc_info=True)
#             return Response({"detail": "Error updating instructor assignment"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



#     @action(detail=True, methods=['delete'], url_path='instructors/(?P<instructor_id>[^/.]+)')
#     def remove_instructor(self, request, pk=None, instructor_id=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 course = self.get_object()
#                 course_instructor = get_object_or_404(
#                     CourseInstructor, 
#                     course=course, 
#                     instructor_id=instructor_id
#                 )
#                 course_instructor.delete()
#                 logger.info(f"[{tenant.schema_name}] Instructor {instructor_id} removed from course {course.title}")
#                 return Response(status=status.HTTP_204_NO_CONTENT)
#         except Http404:
#             logger.warning(f"[{tenant.schema_name}] Instructor {instructor_id} not found for course {pk}")
#             return Response({"detail": "Instructor assignment not found"}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error removing instructor: {str(e)}", exc_info=True)
#             return Response({"detail": "Error removing instructor"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        



# class ModuleViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage modules for a tenant, scoped to courses."""
#     serializer_class = ModuleSerializer
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         course_id = self.kwargs.get('course_id')
#         with tenant_context(tenant):
#             queryset = Module.objects.select_related('course')
#             if course_id:
#                 queryset = queryset.filter(course_id=course_id)
#             return queryset.order_by('order')

#     def get_object(self):
#         tenant = self.request.tenant
#         course_id = self.kwargs.get('course_id')
#         module_id = self.kwargs.get('pk')
#         with tenant_context(tenant):
#             queryset = self.get_queryset()
#             return get_object_or_404(queryset, id=module_id)

#     def create(self, request, *args, **kwargs):
#         tenant = request.tenant
#         course_id = self.kwargs.get('course_id')
#         serializer = self.get_serializer(data=request.data)
#         try:
#             serializer.is_valid(raise_exception=True)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Module creation validation failed: {str(e)}")
#             raise
#         with tenant_context(tenant), transaction.atomic():
#             course = get_object_or_404(Course, id=course_id) if course_id else None
#             serializer.save(course=course)
#             logger.info(f"[{tenant.schema_name}] Module created: {serializer.validated_data['title']}")
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     def update(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant):
#             instance = self.get_object()
#             serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
#             try:
#                 serializer.is_valid(raise_exception=True)
#             except ValidationError as e:
#                 logger.error(f"[{tenant.schema_name}] Module update validation failed: {str(e)}")
#                 raise
#             serializer.save()
#             logger.info(f"[{tenant.schema_name}] Module updated: {instance.title}")
#         return Response(serializer.data)

#     @action(detail=False, methods=['post'])
#     def bulk_update(self, request, *args, **kwargs):
#         tenant = request.tenant
#         module_ids = request.data.get('ids', [])
#         is_published = request.data.get('is_published')
#         if not isinstance(module_ids, list) or not isinstance(is_published, bool):
#             logger.warning(f"[{tenant.schema_name}] Invalid input for bulk_update")
#             return Response({"detail": "Invalid input: ids must be a list and is_published must be a boolean"}, status=status.HTTP_400_BAD_REQUEST)
#         with tenant_context(tenant), transaction.atomic():
#             updated = Module.objects.filter(id__in=module_ids).update(is_published=is_published)
#             logger.info(f"[{tenant.schema_name}] Bulk updated {updated} modules")
#             return Response({"detail": f"Updated {updated} module(s)"}, status=status.HTTP_200_OK)

#     @action(detail=False, methods=['post'])
#     def bulk_delete(self, request, *args, **kwargs):
#         tenant = request.tenant
#         module_ids = request.data.get('ids', [])
#         if not isinstance(module_ids, list):
#             logger.warning(f"[{tenant.schema_name}] Invalid input for bulk_delete")
#             return Response({"detail": "Invalid input: ids must be a list"}, status=status.HTTP_400_BAD_REQUEST)
#         with tenant_context(tenant), transaction.atomic():
#             deleted, _ = Module.objects.filter(id__in=module_ids).delete()
#             logger.info(f"[{tenant.schema_name}] Bulk deleted {deleted} modules")
#             return Response({"detail": f"Deleted {deleted} module(s)"}, status=status.HTTP_200_OK)

#     def get_permissions(self):
#         return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_update', 'bulk_delete'] else [IsAuthenticated()]



# class LessonViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage lessons for a tenant, scoped to courses and modules."""
#     serializer_class = LessonSerializer
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         course_id = self.kwargs.get('course_id')
#         module_id = self.kwargs.get('module_id')
#         with tenant_context(tenant):
#             queryset = Lesson.objects.select_related('module__course')
#             if course_id and module_id:
#                 queryset = queryset.filter(module__course_id=course_id, module_id=module_id)
#             return queryset.order_by('order')

#     def get_object(self):
#         tenant = self.request.tenant
#         course_id = self.kwargs.get('course_id')
#         module_id = self.kwargs.get('module_id')
#         lesson_id = self.kwargs.get('pk')
#         with tenant_context(tenant):
#             queryset = self.get_queryset()
#             return get_object_or_404(queryset, id=lesson_id)

#     # def create(self, request, *args, **kwargs):
#     #     tenant = request.tenant
#     #     course_id = self.kwargs.get('course_id')
#     #     module_id = self.kwargs.get('module_id')
#     #     if not course_id or not module_id:
#     #         logger.warning(f"[{tenant.schema_name}] Missing course_id or module_id for lesson creation")
#     #         raise ValidationError("Course ID and Module ID are required.")
#     #     serializer = self.get_serializer(data=request.data)
#     #     try:
#     #         serializer.is_valid(raise_exception=True)
#     #     except ValidationError as e:
#     #         logger.error(f"[{tenant.schema_name}] Lesson creation validation failed: {str(e)}")
#     #         raise
#     #     with tenant_context(tenant), transaction.atomic():
#     #         module = get_object_or_404(Module, id=module_id, course_id=course_id)
#     #         serializer.save(module=module)
#     #         logger.info(f"[{tenant.schema_name}] Lesson created: {serializer.validated_data['title']}")
#     #     return Response(serializer.data, status=status.HTTP_201_CREATED)

#     # def update(self, request, *args, **kwargs):
#     #     tenant = request.tenant
#     #     with tenant_context(tenant):
#     #         instance = self.get_object()
#     #         serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
#     #         try:
#     #             serializer.is_valid(raise_exception=True)
#     #         except ValidationError as e:
#     #             logger.error(f"[{tenant.schema_name}] Lesson update validation failed: {str(e)}")
#     #             raise
#     #         serializer.save()
#     #         logger.info(f"[{tenant.schema_name}] Lesson updated: {instance.title}")
#     #     return Response(serializer.data)


#     def create(self, request, *args, **kwargs):
#         tenant = request.tenant
#         course_id = self.kwargs.get('course_id')
#         module_id = self.kwargs.get('module_id')
#         if not course_id or not module_id:
#             logger.warning(f"[{tenant.schema_name}] Missing course_id or module_id for lesson creation")
#             raise ValidationError("Course ID and Module ID are required.")
#         serializer = self.get_serializer(
#             data=request.data,
#             context={'tenant': tenant, 'course_id': course_id, 'module_id': module_id}
#         )
#         try:
#             serializer.is_valid(raise_exception=True)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Lesson creation validation failed: {str(e)}")
#             raise
#         with tenant_context(tenant), transaction.atomic():
#             module = get_object_or_404(Module, id=module_id, course_id=course_id)
#             serializer.save(module=module)
#             logger.info(f"[{tenant.schema_name}] Lesson created: {serializer.validated_data['title']}")
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     def update(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant):
#             instance = self.get_object()
#             serializer = self.get_serializer(
#                 instance,
#                 data=request.data,
#                 partial=kwargs.get('partial', False),
#                 context={'tenant': tenant}
#             )
#             try:
#                 serializer.is_valid(raise_exception=True)
#             except ValidationError as e:
#                 logger.error(f"[{tenant.schema_name}] Lesson update validation failed: {str(e)}")
#                 raise
#             serializer.save()
#             logger.info(f"[{tenant.schema_name}] Lesson updated: {instance.title}")
#         return Response(serializer.data)


#     def get_permissions(self):
#         return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]



# class EnrollmentViewSet(TenantBaseView, viewsets.ViewSet):
#     """Manage course enrollments for a tenant."""
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsPagination

#     def list(self, request, course_id=None, user_id=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 queryset = Enrollment.objects.select_related('user', 'course').filter(is_active=True)
#                 if request.user.role != "admin" and user_id and user_id != str(request.user.id):
#                     logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.id} attempted to access user {user_id} enrollments")
#                     return Response({"detail": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)
#                 if request.user.role != "admin":
#                     queryset = queryset.filter(user=request.user)
#                 elif user_id:
#                     queryset = queryset.filter(user_id=user_id)
#                 if course_id:
#                     queryset = queryset.filter(course_id=course_id)
#                     if not queryset.exists() and not request.user.is_staff:
#                         logger.warning(f"[{tenant.schema_name}] User {request.user.id} not enrolled in course {course_id}")
#                         return Response({"detail": "Not enrolled in this course"}, status=status.HTTP_403_FORBIDDEN)
#                 queryset = queryset.order_by('-enrolled_at')
#                 paginator = self.pagination_class()
#                 page = paginator.paginate_queryset(queryset, request)
#                 serializer = EnrollmentSerializer(page, many=True)
#                 logger.info(f"[{tenant.schema_name}] Listed enrollments for user {request.user.id}")
#                 return paginator.get_paginated_response(serializer.data)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error listing enrollments: {str(e)}", exc_info=True)
#             return Response({"detail": "Error fetching enrollments"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#     @action(detail=False, methods=['post'], url_path='course/(?P<course_id>[^/.]+)')
#     def enroll_to_course(self, request, course_id=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 course = get_object_or_404(Course, id=course_id, status='Published')
#                 user_id = request.data.get('user_id')
#                 if not user_id:
#                     logger.warning(f"[{tenant.schema_name}] Missing user_id for enrollment")
#                     return Response({"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
#                 if Enrollment.objects.filter(user_id=user_id, course=course).exists():
#                     logger.warning(f"[{tenant.schema_name}] User {user_id} already enrolled in course {course_id}")
#                     return Response({"detail": "User already enrolled in this course"}, status=status.HTTP_400_BAD_REQUEST)
#                 enrollment = Enrollment.objects.create(user_id=user_id, course=course)
#                 serializer = EnrollmentSerializer(enrollment)
#                 #logger.info(f"[{tenant.schema_name}] User {user_id} enrolled in course {course_id}")
#                 return Response(serializer.data, status=status.HTTP_201_CREATED)
#         except Http404:
#             logger.warning(f"[{tenant.schema_name}] Course {course_id} not found or not published")
#             return Response({"detail": "Course not found or not published"}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error enrolling user: {str(e)}", exc_info=True)
#             return Response({"detail": "Error processing enrollment"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#     @action(detail=False, methods=['post'], url_path='course/(?P<course_id>[^/.]+)/bulk')
#     def bulk_enroll(self, request, course_id=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 course = get_object_or_404(Course, id=course_id)  # Remove status='Published' for admin flexibility
#                 user_ids = request.data.get('user_ids', [])
#                 if not isinstance(user_ids, list):
#                     logger.warning(f"[{tenant.schema_name}] Invalid user_ids for bulk enrollment")
#                     return Response({"detail": "user_ids must be a list"}, status=status.HTTP_400_BAD_REQUEST)
#                 if not user_ids:
#                     logger.warning(f"[{tenant.schema_name}] No user_ids provided for bulk enrollment")
#                     return Response({"detail": "user_ids is required"}, status=status.HTTP_400_BAD_REQUEST)
#                 existing = set(Enrollment.objects.filter(user_id__in=user_ids, course=course).values_list('user_id', flat=True))
#                 new_enrollments = [Enrollment(user_id=user_id, course=course) for user_id in user_ids if user_id not in existing]
#                 with transaction.atomic():
#                     if new_enrollments:
#                         Enrollment.objects.bulk_create(new_enrollments)
#                     logger.info(f"[{tenant.schema_name}] Bulk enrolled {len(new_enrollments)} users to course {course_id}")
#                     return Response({
#                         "detail": f"Enrolled {len(new_enrollments)} users",
#                         "created": len(new_enrollments),
#                         "already_enrolled": len(existing)
#                     }, status=status.HTTP_201_CREATED)
#                 return Response({"detail": "No new enrollments created (all users already enrolled)"}, status=status.HTTP_200_OK)
#         except Http404:
#             logger.warning(f"[{tenant.schema_name}] Course {course_id} not found")
#             return Response({"detail": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error in bulk enrollment: {str(e)}", exc_info=True)
#             return Response({"detail": "Error processing bulk enrollment"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
#     def all_enrollments(self, request):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 enrollments = Enrollment.objects.select_related('user', 'course').filter(is_active=True).order_by('-enrolled_at')
#                 paginator = self.pagination_class()
#                 page = paginator.paginate_queryset(enrollments, request)
#                 serializer = EnrollmentSerializer(page, many=True)
#                 logger.info(f"[{tenant.schema_name}] Listed all enrollments")
#                 return paginator.get_paginated_response(serializer.data)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error fetching all enrollments: {str(e)}", exc_info=True)
#             return Response({"detail": "Error fetching all enrollments"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     @action(detail=False, methods=['get'])
#     def user_enrollments(self, request, user_id=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 user_id = user_id or request.user.id
#                 if request.user.role != "admin" and user_id != str(request.user.id):
#                     logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.id} attempted to access user {user_id} enrollments")
#                     return Response({"detail": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)
#                 enrollments = Enrollment.objects.filter(user_id=user_id, is_active=True).select_related('course').prefetch_related(
#                     'course__resources', 'course__modules', 'course__modules__lessons', 'course__course_instructors__instructor__user'
#                 ).order_by('-enrolled_at')
#                 result = []
#                 base_url = request.build_absolute_uri('/')[:-1]
#                 for enrollment in enrollments:
#                     course = enrollment.course
#                     resources = [
#                         {
#                             'id': r.id, 'title': r.title, 'type': r.resource_type, 'url': r.url, 'order': r.order,
#                             'file': f"{base_url}{r.file.url}" if r.file else None
#                         } for r in course.resources.all()
#                     ]
#                     modules = [
#                         {
#                             'id': m.id, 'title': m.title, 'order': m.order,
#                             'lessons': [
#                                 {
#                                     'id': l.id, 'title': l.title, 'type': l.lesson_type, 'duration': l.duration,
#                                     'order': l.order, 'is_published': l.is_published, 'content_url': l.content_url,
#                                     'content_file': f"{base_url}{l.content_file.url}" if l.content_file else None
#                                 } for l in m.lessons.all()
#                             ]
#                         } for m in course.modules.all()
#                     ]
#                     instructors = [
#                         {'id': ci.instructor.id, 'name': ci.instructor.user.get_full_name(), 'bio': ci.instructor.bio}
#                         for ci in course.course_instructors.all()
#                     ]
#                     result.append({
#                         'id': enrollment.id,
#                         'course': {
#                             'id': course.id, 'title': course.title, 'description': course.description,
#                             'thumbnail': f"{base_url}{course.thumbnail.url}" if course.thumbnail else None,
#                             'resources': resources, 'modules': modules, 'instructors': instructors
#                         },
#                         'enrolled_at': enrollment.enrolled_at, 'completed_at': enrollment.completed_at
#                     })
#                 logger.info(f"[{tenant.schema_name}] Retrieved enrollments for user {user_id}")
#                 return Response(result)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error fetching user enrollments: {str(e)}", exc_info=True)
#             return Response({"detail": "Error fetching user enrollments"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class AdminEnrollmentView(TenantBaseView, APIView):
#     """Admin endpoint to manage single or bulk enrollments."""
#     permission_classes = [IsAdminUser]

#     def post(self, request):
#         tenant = request.tenant
#         serializer = BulkEnrollmentSerializer(data=request.data, many=isinstance(request.data, list))
#         try:
#             serializer.is_valid(raise_exception=True)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Admin enrollment validation failed: {str(e)}")
#             raise
#         with tenant_context(tenant), transaction.atomic():
#             enrollments = []
#             for data in serializer.validated_data:
#                 course = get_object_or_404(Course, id=data['course_id'], status='Published')
#                 if not Enrollment.objects.filter(user_id=data['user_id'], course=course).exists():
#                     enrollments.append(Enrollment(user_id=data['user_id'], course=course))
#             Enrollment.objects.bulk_create(enrollments)
#             logger.info(f"[{tenant.schema_name}] Created {len(enrollments)} enrollments")
#             return Response({"detail": f"{len(enrollments)} enrollments created successfully"}, status=status.HTTP_201_CREATED)


# class LearningPathViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage learning paths for a tenant."""
#     serializer_class = LearningPathSerializer
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         with tenant_context(tenant):
#             return LearningPath.objects.filter(is_active=True).order_by('title')

#     def create(self, request, *args, **kwargs):
#         tenant = request.tenant
#         serializer = self.get_serializer(data=request.data)
#         try:
#             serializer.is_valid(raise_exception=True)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Learning path creation validation failed: {str(e)}")
#             raise
#         with tenant_context(tenant), transaction.atomic():
#             serializer.save(created_by=request.user)
#             logger.info(f"[{tenant.schema_name}] Learning path created: {serializer.validated_data['title']}")
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     def get_permissions(self):
#         return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]

# class ResourceViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage resources for a tenant, scoped to courses."""
#     serializer_class = ResourceSerializer
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         course_id = self.kwargs.get('course_id')
#         with tenant_context(tenant):
#             queryset = Resource.objects.select_related('course')
#             if course_id:
#                 queryset = queryset.filter(course_id=course_id)
#             return queryset.order_by('order')

#     # def create(self, request, *args, **kwargs):
#     #     tenant = request.tenant
#     #     course_id = self.kwargs.get('course_id')
#     #     serializer = self.get_serializer(data=request.data)
#     #     try:
#     #         serializer.is_valid(raise_exception=True)
#     #     except ValidationError as e:
#     #         logger.error(f"[{tenant.schema_name}] Resource creation validation failed: {str(e)}")
#     #         raise
#     #     with tenant_context(tenant), transaction.atomic():
#     #         course = get_object_or_404(Course, id=course_id) if course_id else None
#     #         serializer.save(course=course)
#     #         logger.info(f"[{tenant.schema_name}] Resource created: {serializer.validated_data['title']}")
#     #     return Response(serializer.data, status=status.HTTP_201_CREATED)

#     # def update(self, request, *args, **kwargs):
#     #     tenant = request.tenant
#     #     with tenant_context(tenant):
#     #         instance = self.get_object()
#     #         serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
#     #         try:
#     #             serializer.is_valid(raise_exception=True)
#     #         except ValidationError as e:
#     #             logger.error(f"[{tenant.schema_name}] Resource update validation failed: {str(e)}")
#     #             raise
#     #         serializer.save()
#     #         logger.info(f"[{tenant.schema_name}] Resource updated: {instance.title}")
#     #     return Response(serializer.data)


#     def create(self, request, *args, **kwargs):
#         tenant = request.tenant
#         course_id = kwargs.get('course_id')
#         serializer = self.get_serializer(
#             data=request.data,
#             context={'tenant': tenant, 'course_id': course_id}
#         )
#         try:
#             serializer.is_valid(raise_exception=True)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Resource creation validation failed: {str(e)}")
#             raise
#         with tenant_context(tenant), transaction.atomic():
#             course = get_object_or_404(Course, id=course_id) if course_id else None
#             serializer.save(course=course)
#             logger.info(f"[{tenant.schema_name}] Resource created: {serializer.validated_data['title']}")
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     def update(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant):
#             instance = self.get_object()
#             serializer = self.get_serializer(
#                 instance,
#                 data=request.data,
#                 partial=kwargs.get('partial', False),
#                 context={'tenant': tenant}
#             )
#             try:
#                 serializer.is_valid(raise_exception=True)
#             except ValidationError as e:
#                 logger.error(f"[{tenant.schema_name}] Resource update failed: {str(e)}")
#                 raise
#             serializer.save()
#             logger.info(f"[{tenant.schema_name}] Resource updated: {instance.title}")
#         return Response(serializer.data)

#     def destroy(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant):
#             instance = self.get_object()
#             instance.delete()
#             logger.info(f"[{tenant.schema_name}] Resource deleted: {instance.title}")
#         return Response(status=status.HTTP_204_NO_CONTENT)

#     @action(detail=False, methods=['post'])
#     def reorder(self, request, course_id):
#         tenant = request.tenant
#         resources = request.data.get('resources', [])
#         if not isinstance(resources, list):
#             logger.warning(f"[{tenant.schema_name}] Invalid input for resource reorder")
#             return Response({"detail": "resources must be a list"}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             with tenant_context(tenant), transaction.atomic():
#                 for item in resources:
#                     Resource.objects.filter(id=item['id'], course_id=course_id).update(order=item['order'])
#                 logger.info(f"[{tenant.schema_name}] Reordered resources for course {course_id}")
#                 return Response({"detail": "Resources reordered successfully"}, status=status.HTTP_200_OK)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error reordering resources: {str(e)}", exc_info=True)
#             return Response({"detail": "Error reordering resources"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def get_permissions(self):
#         return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'reorder'] else [IsAuthenticated()]

# class CertificateView(TenantAPIView, APIView):
#     """Manage certificates for a tenant."""
#     permission_classes = [IsAuthenticated]

#     def get(self, request, course_id=None):
#         tenant = request.tenant
#         try:
#             with tenant_context(tenant):
#                 enrollments = Enrollment.objects.filter(user=request.user, is_active=True, completed_at__isnull=False)
#                 if course_id:
#                     enrollments = enrollments.filter(course_id=course_id)
#                 certificates = Certificate.objects.filter(enrollment__in=enrollments).select_related('enrollment__course')
#                 serializer = CertificateSerializer(certificates, many=True)
#                 logger.info(f"[{tenant.schema_name}] Retrieved certificates for user {request.user.id}")
#                 return Response(serializer.data)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error fetching certificates: {str(e)}", exc_info=True)
#             return Response({"detail": "Error fetching certificates"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# class FAQStatsView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, *args, **kwargs):
#         course_id = request.query_params.get('course_id')
#         if course_id:
#             faq_count = FAQ.objects.filter(course_id=course_id, is_active=True).count()
#         else:
#             faq_count = FAQ.objects.filter(is_active=True).count()
#         return Response({'faq_count': faq_count})


# class BadgeViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage badges for a tenant."""
#     serializer_class = BadgeSerializer
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         with tenant_context(tenant):
#             return Badge.objects.filter(is_active=True).order_by('name')

#     # def create(self, request, *args, **kwargs):
#     #     tenant = request.tenant
#     #     serializer = self.get_serializer(data=request.data)
#     #     try:
#     #         serializer.is_valid(raise_exception=True)
#     #     except ValidationError as e:
#     #         logger.error(f"[{tenant.schema_name}] Badge creation validation failed: {str(e)}")
#     #         raise
#     #     with tenant_context(tenant), transaction.atomic():
#     #         serializer.save()
#     #         logger.info(f"[{tenant.schema_name}] Badge created: {serializer.validated_data['name']}")
#     #     return Response(serializer.data, status=status.HTTP_201_CREATED)



#     def create(self, request, *args, **kwargs):
#         tenant = request.tenant
#         serializer = self.get_serializer(
#             data=request.data,
#             context={'tenant': tenant}
#         )
#         try:
#             serializer.is_valid(raise_exception=True)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] Badge creation failed: {str(e)}")
#             raise
#         with tenant_context(tenant), transaction.atomic():
#             serializer.save()
#             logger.info(f"[{tenant.schema_name}] Badge created: {serializer.validated_data['title']}")
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     def update(self, request, *args, **kwargs):
#         tenant = request.tenant
#         with tenant_context(tenant):
#             instance = self.get_object()
#             serializer = self.get_serializer(
#                 instance,
#                 data=request.data,
#                 partial=kwargs.get('partial', False),
#                 context={'tenant': tenant}
#             )
#             try:
#                 serializer.is_valid(raise_exception=True)
#             except ValidationError as e:
#                 logger.error(f"[{tenant.schema_name}] Badge update failed: {str(e)}")
#                 raise
#             serializer.save()
#             logger.info(f"[{tenant.schema_name}] Badge updated: {instance.title}")
#         return Response(serializer.data)


#     def get_permissions(self):
#         return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]

# class UserPointsViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage user points for a tenant."""
#     serializer_class = UserPointsSerializer
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         with tenant_context(tenant):
#             queryset = UserPoints.objects.select_related('user', 'course')
#             if not self.request.user.is_staff:
#                 queryset = queryset.filter(user=self.request.user)
#             return queryset.order_by('-created_at')

#     @action(detail=False, methods=['get'])
#     def leaderboard(self, request):
#         tenant = request.tenant
#         course_id = request.query_params.get('course_id')
#         try:
#             with tenant_context(tenant):
#                 queryset = UserPoints.objects.values('user__username').annotate(
#                     total_points=Count('points')
#                 ).order_by('-total_points')
#                 if course_id:
#                     queryset = queryset.filter(course_id=course_id)
#                 paginator = self.pagination_class()
#                 page = paginator.paginate_queryset(queryset, request)
#                 logger.info(f"[{tenant.schema_name}] Retrieved leaderboard for course {course_id or 'all'}")
#                 return paginator.get_paginated_response(page)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error fetching leaderboard: {str(e)}", exc_info=True)
#             return Response({"detail": "Error fetching leaderboard"}, status=500)

# class UserBadgeViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage user badges for a tenant."""
#     serializer_class = UserBadgeSerializer
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         with tenant_context(tenant):
#             queryset = UserBadge.objects.select_related('user', 'badge')
#             if not self.request.user.is_staff:
#                 queryset = queryset.filter(user=self.request.user)
#             return queryset.order_by('-created_at')

# class FAQViewSet(TenantBaseView, viewsets.ModelViewSet):
#     """Manage FAQs for a tenant, scoped to courses."""
#     serializer_class = FAQSerializer
#     permission_classes = [IsAuthenticated]
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         tenant = self.request.tenant
#         course_id = self.kwargs.get('course_id')
#         with tenant_context(tenant):
#             queryset = FAQ.objects.select_related('course')
#             if course_id:
#                 queryset = queryset.filter(course_id=course_id)
#             return queryset.order_by('order')

#     def create(self, request, *args, **kwargs):
#         tenant = request.tenant
#         course_id = self.kwargs.get('course_id')
#         serializer = self.get_serializer(data=request.data)
#         try:
#             serializer.is_valid(raise_exception=True)
#         except ValidationError as e:
#             logger.error(f"[{tenant.schema_name}] FAQ creation validation failed: {str(e)}")
#             raise
#         with tenant_context(tenant), transaction.atomic():
#             course = get_object_or_404(Course, id=course_id) if course_id else None
#             serializer.save(course=course)
#             logger.info(f"[{tenant.schema_name}] FAQ created for course {course_id}")
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     @action(detail=False, methods=['post'])
#     def reorder(self, request, course_id):
#         tenant = request.tenant
#         faqs = request.data.get('faqs', [])
#         if not isinstance(faqs, list):
#             logger.warning(f"[{tenant.schema_name}] Invalid input for FAQ reorder")
#             return Response({"detail": "faqs must be a list"}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             with tenant_context(tenant), transaction.atomic():
#                 for item in faqs:
#                     FAQ.objects.filter(id=item['id'], course_id=course_id).update(order=item['order'])
#                 logger.info(f"[{tenant.schema_name}] Reordered FAQs for course {course_id}")
#                 return Response({"detail": "FAQs reordered successfully"}, status=status.HTTP_200_OK)
#         except Exception as e:
#             logger.error(f"[{tenant.schema_name}] Error reordering FAQs: {str(e)}", exc_info=True)
#             return Response({"detail": "Error reordering FAQs"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def get_permissions(self):
#         return [IsAdminUser()] if self.action in ['compile', 'update', 'partial_update', 'destroy', 'reorder'] else [IsAuthenticated()]

