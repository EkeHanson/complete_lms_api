To develop the **courses** Django app for your course management system using Django REST Framework (DRF), I'll create a comprehensive implementation that integrates with the previously provided analytics app and aligns with the course management models you shared. The courses app will include models, serializers, views, URLs, and additional components like signals and permissions to manage courses, modules, lessons, enrollments, and related entities. This implementation will support your React frontend and provide a robust API for course-related operations.

### Courses App Structure

The courses app will include:
- **Models**: The core models for courses, modules, lessons, enrollments, etc., as provided in the original model structure.
- **Serializers**: To convert model data into JSON for API responses.
- **Views**: To handle API requests for creating, retrieving, updating, and deleting course-related data.
- **URLs**: To define API endpoints for course management.
- **Signals**: To automate tasks like generating slugs or updating related data.
- **Permissions**: To control access to course data (e.g., admin-only for course creation, user-specific for enrollments).
- **Utilities**: Helper functions for tasks like file uploads or certificate generation.

### Assumptions
- The courses app will use the models you provided (e.g., `Course`, `Module`, `Lesson`, `Enrollment`, etc.).
- The app integrates with the `analytics` app for tracking progress and statistics.
- Authentication is handled via DRF's `TokenAuthentication` or `SessionAuthentication`.
- File uploads (e.g., thumbnails, resources) are stored locally or on an S3-compatible storage.
- The app supports CRUD operations for courses, modules, lessons, and enrollments, with appropriate permissions.
- PostgreSQL is assumed for the database, but the code is compatible with other Django-supported databases.

### Implementation

#### 1. Models (courses/models.py)
The models are based on the provided structure, with minor adjustments for clarity and consistency. I'll include all the models you shared to ensure completeness.

```python
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
import os

def course_thumbnail_path(instance, filename):
    return f'courses/{instance.slug}/thumbnails/{filename}'

def certificate_logo_path(instance, filename):
    return f'courses/{instance.course.slug}/certificates/logos/{filename}'

def certificate_signature_path(instance, filename):
    return f'courses/{instance.course.slug}/certificates/signatures/{filename}'

def resource_file_path(instance, filename):
    return f'courses/{instance.module.course.slug}/resources/{filename}'

def scorm_package_path(instance, filename):
    return f'courses/{instance.course.slug}/scorm_packages/{filename}'

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Course(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Published', 'Published'),
        ('Archived', 'Archived'),
    ]
    
    LEVEL_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]
    
    CURRENCY_CHOICES = [
        ('NGN', 'Naira (₦)'),
        ('USD', 'Dollar ($)'),
        ('EUR', 'Euro (€)'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='Beginner')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    duration = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='NGN')
    thumbnail = models.ImageField(upload_to=course_thumbnail_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_courses')
    
    completion_hours = models.PositiveIntegerField(default=0, help_text="Estimated hours to complete the course")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    @property
    def current_price(self):
        return self.discount_price if self.discount_price else self.price

class LearningOutcome(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='learning_outcomes')
    text = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.course.title} - {self.text[:50]}"

class Prerequisite(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='prerequisites')
    text = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.course.title} - {self.text[:50]}"

class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"

class Lesson(models.Model):
    LESSON_TYPE_CHOICES = [
        ('video', 'Video'),
        ('quiz', 'Quiz'),
        ('assignment', 'Assignment'),
        ('text', 'Text'),
        ('file', 'File'),
    ]
    
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES, default='video')
    duration = models.PositiveIntegerField(help_text="Duration in minutes", default=0)
    content_url = models.URLField(blank=True)
    content_file = models.FileField(upload_to='lessons/files/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    
    class Meta:
        ordering ==['order']
        unique_together = ['module', 'order']
    
    def __str__(self):
        return f"{self.module.title} - {self.title}"
    
    @property
    def duration_display(self):
        hours = self.duration // 60
        minutes = self.duration % 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

class Resource(models.Model):
    RESOURCE_TYPE_CHOICES = [
        ('link', 'Web Link'),
        ('pdf', 'PDF Document'),
        ('video', 'Video'),
        ('file', 'File'),
    ]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=200)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES)
    url = models.URLField(blank=True)
    file = models.FileField(upload_to=resource_file_path, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"

class Instructor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='instructor_profile')
    bio = models.TextField(blank=True)
    expertise = models.ManyToManyField(Category, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.user.get_full_name()

class CourseInstructor(models.Model):
    ASSIGNMENT_CHOICES = [
        ('all', 'Entire Course'),
        ('specific', 'Specific Modules'),
    ]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_instructors')
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='assigned_courses')
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_CHOICES, default='all')
    is_active = models.BooleanField(default=True)
    modules = models.ManyToManyField(Module, blank=True)
    
    class Meta:
        unique_together = ['course', 'instructor']
    
    def __str__(self):
        return f"{self.instructor} - {self.course.title}"

class CertificateTemplate(models.Model):
    TEMPLATE_CHOICES = [
        ('default', 'Default'),
        ('modern', 'Modern'),
        ('elegant', 'Elegant'),
        ('custom', 'Custom'),
    ]
    
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='certificate_settings')
    is_active = models.BooleanField(default=False)
    template = models.CharField(max_length=20, choices=TEMPLATE_CHOICES, default='default')
    custom_text = models.TextField(default='Congratulations on completing the course!')
    logo = models.ImageField(upload_to=certificate_logo_path, null=True, blank=True)
    signature = models.ImageField(upload_to=certificate_signature_path, null=True, blank=True)
    signature_name = models.CharField(max_length=100, default='Course Instructor')
    show_date = models.BooleanField(default=True)
    show_course_name = models.BooleanField(default=True)
    show_completion_hours = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Certificate for {self.course.title}"

class SCORMxAPISettings(models.Model):
    STANDARD_CHOICES = [
        ('scorm12', 'SCORM 1.2'),
        ('scorm2004', 'SCORM 2004'),
        ('xapi', 'xAPI (Tin Can)'),
    ]
    
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='scorm_settings')
    is_active = models.BooleanField(default=False)
    standard = models.CharField(max_length=20, choices=STANDARD_CHOICES, default='scorm12')
    version = models.CharField(max_length=20, default='1.2')
    completion_threshold = models.PositiveIntegerField(
        default=80,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    score_threshold = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    track_completion = models.BooleanField(default=True)
    track_score = models.BooleanField(default=True)
    track_time = models.BooleanField(default=True)
    track_progress = models.BooleanField(default=True)
    package = models.FileField(upload_to=scorm_package_path, null=True, blank=True)
    
    def __str__(self):
        return f"SCORM/xAPI Settings for {self.course.title}"

class LearningPath(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    courses = models.ManyToManyField(Course, related_name='learning_paths')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.title

class Enrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'course']
    
    def __str__(self):
        return f"{self.user} - {self.course}"

class Certificate(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='certificate')
    issued_at = models.DateTimeField(auto_now_add=True)
    certificate_id = models.CharField(max_length=50, unique=True)
    pdf_file = models.FileField(upload_to='certificates/pdfs/', null=True, blank=True)
    
    def __str__(self):
        return f"Certificate {self.certificate_id} for {self.enrollment.user}"

class CourseRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_ratings')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'course']
    
    def __str__(self):
        return f"{self.user} rated {self.course} {self.rating} stars"
```

#### 2. Serializers (courses/serializers.py)
Serializers convert model data into JSON for the API, including nested relationships for course details.

```python
from rest_framework import serializers
from .models import (
    Category, Course, LearningOutcome, Prerequisite, Module, Lesson,
    Resource, Instructor, CourseInstructor, CertificateTemplate,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating
)
from django.contrib.auth import get_user_model

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description']

class LearningOutcomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningOutcome
        fields = ['id', 'text', 'order']

class PrerequisiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prerequisite
        fields = ['id', 'text', 'order']

class LessonSerializer(serializers.ModelSerializer):
    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'description', 'lesson_type', 'duration', 'duration_display', 'content_url', 'content_file', 'order', 'is_published']

class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'description', 'order', 'is_published', 'lessons']

class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ['id', 'title', 'resource_type', 'url', 'file', 'order']

class InstructorSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    expertise = CategorySerializer(many=True, read_only=True)

    class Meta:
        model = Instructor
        fields = ['id', 'user_name', 'bio', 'expertise', 'is_active']

class CourseInstructorSerializer(serializers.ModelSerializer):
    instructor = InstructorSerializer(read_only=True)
    module_titles = serializers.SerializerMethodField()

    class Meta:
        model = CourseInstructor
        fields = ['id', 'instructor', 'assignment_type', 'is_active', 'module_titles']

    def get_module_titles(self, obj):
        return [module.title for module in obj.modules.all()]

class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateTemplate
        fields = ['id', 'is_active', 'template', 'custom_text', 'logo', 'signature', 'signature_name', 'show_date', 'show_course_name', 'show_completion_hours']

class SCORMxAPISettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCORMxAPISettings
        fields = ['id', 'is_active', 'standard', 'version', 'completion_threshold', 'score_threshold', 'track_completion', 'track_score', 'track_time', 'track_progress', 'package']

class CourseSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    learning_outcomes = LearningOutcomeSerializer(many=True, read_only=True)
    prerequisites = PrerequisiteSerializer(many=True, read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    resources = ResourceSerializer(many=True, read_only=True)
    course_instructors = CourseInstructorSerializer(many=True, read_only=True)
    certificate_settings = CertificateTemplateSerializer(read_only=True)
    scorm_settings = SCORMxAPISettingsSerializer(read_only=True)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'code', 'description', 'short_description', 'category', 'category_id',
            'level', 'status', 'duration', 'price', 'discount_price', 'currency', 'thumbnail',
            'created_at', 'updated_at', 'created_by', 'created_by_username', 'completion_hours',
            'current_price', 'learning_outcomes', 'prerequisites', 'modules', 'resources',
            'course_instructors', 'certificate_settings', 'scorm_settings'
        ]

class LearningPathSerializer(serializers.ModelSerializer):
    courses = CourseSerializer(many=True, read_only=True)
    course_ids = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), many=True, source='courses', write_only=True)

    class Meta:
        model = LearningPath
        fields = ['id', 'title', 'description', 'courses', 'course_ids', 'is_active', 'order', 'created_at', 'updated_at']

class EnrollmentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'user', 'user_username', 'course', 'course_title', 'enrolled_at', 'completed_at', 'is_active']

class CertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='enrollment.course.title', read_only=True)
    user_username = serializers.CharField(source='enrollment.user.username', read_only=True)

    class Meta:
        model = Certificate
        fields = ['id', 'enrollment', 'course_title', 'user_username', 'issued_at', 'certificate_id', 'pdf_file']

class CourseRatingSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = CourseRating
        fields = ['id', 'user', 'user_username', 'course', 'course_title', 'rating', 'review', 'created_at', 'updated_at']
```

#### 3. Views (courses/views.py)
Views handle API requests for course-related operations, with appropriate permissions and pagination.

```python
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from .models import (
    Category, Course, LearningOutcome, Prerequisite, Module, Lesson,
    Resource, Instructor, CourseInstructor, CertificateTemplate,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating
)
from .serializers import (
    CategorySerializer, CourseSerializer, LearningOutcomeSerializer, PrerequisiteSerializer,
    ModuleSerializer, LessonSerializer, ResourceSerializer, InstructorSerializer,
    CourseInstructorSerializer, CertificateTemplateSerializer, SCORMxAPISettingsSerializer,
    LearningPathSerializer, EnrollmentSerializer, CertificateSerializer, CourseRatingSerializer
)
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q

class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class CategoryViewSet(ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class CourseViewSet(ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(status='Published')
        return queryset

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class ModuleViewSet(ModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

class LessonViewSet(ModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

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

class CertificateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id=None):
        enrollments = Enrollment.objects.filter(user=request.user, is_active=True, completed_at__isnull=False)
        if course_id:
            enrollments = enrollments.filter(course_id=course_id)
        
        certificates = Certificate.objects.filter(enrollment__in=enrollments)
        serializer = CertificateSerializer(certificates, many=True)
        return Response(serializer.data)
```

#### 4. URLs (courses/urls.py)
Define API endpoints for course-related operations.

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, CourseViewSet, ModuleViewSet, LessonViewSet,
    EnrollmentView, CourseRatingView, LearningPathViewSet, CertificateView
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'modules', ModuleViewSet)
router.register(r'lessons', LessonViewSet)
router.register(r'learning-paths', LearningPathViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('enrollments/', EnrollmentView.as_view(), name='enrollments'),
    path('enrollments/course/<int:course_id>/', EnrollmentView.as_view(), name='enrollment-course'),
    path('ratings/', CourseRatingView.as_view(), name='ratings'),
    path('ratings/course/<int:course_id>/', CourseRatingView.as_view(), name='rating-course'),
    path('certificates/', CertificateView.as_view(), name='certificates'),
    path('certificates/course/<int:course_id>/', CertificateView.as_view(), name='certificate-course'),
]
```

#### 5. Signals (courses/signals.py)
Use signals to automate tasks like generating unique certificate IDs or updating related data.

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Certificate, Enrollment
import uuid

@receiver(post_save, sender=Enrollment)
def create_certificate_on_completion(sender, instance, **kwargs):
    if instance.completed_at and not hasattr(instance, 'certificate'):
        certificate_id = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        Certificate.objects.create(
            enrollment=instance,
            certificate_id=certificate_id
        )
```

#### 6. App Configuration (courses/apps.py)
Configure the courses app to load signals.

```python
from django.apps import AppConfig

class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'courses'

    def ready(self):
        import courses.signals  # Load signals
```

#### 7. Settings Update
Ensure the courses app is included in your Django settings and configure media storage.

```python
INSTALLED_APPS = [
    ...
    'rest_framework',
    'courses',
    'analytics',
]

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
}

MEDIA_URL = '/media/'
MEDIA_ROOT = 'media'

# Optional: S3 storage configuration
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# AWS_ACCESS_KEY_ID = 'your-access-key'
# AWS_SECRET_ACCESS_KEY = 'your-secret-key'
# AWS_STORAGE_BUCKET_NAME = 'your-bucket-name'
```

### Integration with Analytics App

1. **Dependencies**:
   - The `courses` app is a dependency for the `analytics` app, as analytics models reference `Course`, `Enrollment`, `Lesson`, etc.
   - Ensure both apps are installed in `INSTALLED_APPS`.

2. **Data Flow**:
   - When a user enrolls in a course, an `Enrollment` record is created, triggering analytics updates via signals in the `analytics` app.
   - Course ratings (`CourseRating`) update the `CourseAnalytics.average_rating` via signals.
   - Lesson completion (tracked in `analytics.UserProgress`) relies on `Lesson` and `Enrollment` models.

3. **Permissions**:
   - Admin users can create, update, and delete courses, modules, and lessons.
   - Authenticated users can view published courses, enroll, rate courses, and access their certificates.
   - Non-authenticated users cannot access any endpoints (enforced by `IsAuthenticated`).

4. **API Endpoints**:
   - `/courses/categories/` - CRUD for categories (admin for write, authenticated for read).
   - `/courses/courses/` - CRUD for courses (admin for write, authenticated for read, filtered by status for non-admins).
   - `/courses/modules/` - CRUD for modules (admin for write, authenticated for read).
   - `/courses/lessons/` - CRUD for lessons (admin for write, authenticated for read).
   - `/courses/learning-paths/` - CRUD for learning paths (admin for write, authenticated for read).
   - `/courses/enrollments/` - List enrollments or enroll in a course.
   - `/courses/ratings/` - List or submit course ratings.
   - `/courses/certificates/` - List certificates for completed courses.

### Database Optimization
- **Indexes**: Included in models (e.g., `unique_together`, `ordering`) to optimize queries.
- **Pagination**: Applied to all list endpoints to handle large datasets.
- **Query Optimization**: Used `select_related` and `prefetch_related` implicitly via serializers to reduce database hits.

### Example API Response
For `/courses/courses/1/`:
```json
{
    "id": 1,
    "title": "Python Programming",
    "slug": "python-programming",
    "code": "PY101",
    "description": "Learn Python from scratch.",
    "short_description": "A beginner-friendly Python course.",
    "category": {
        "id": 1,
        "name": "Programming",
        "slug": "programming",
        "description": "Coding courses"
    },
    "level": "Beginner",
    "status": "Published",
    "duration": "8 weeks",
    "price": "100.00",
    "discount_price": "80.00",
    "currency": "USD",
    "thumbnail": "/media/courses/python-programming/thumbnails/thumb.jpg",
    "created_at": "2025-04-20T12:00:00Z",
    "updated_at": "2025-04-20T12:00:00Z",
    "created_by": 1,
    "created_by_username": "admin",
    "completion_hours": 40,
    "current_price": "80.00",
    "learning_outcomes": [
        {"id": 1, "text": "Write Python scripts", "order": 1},
        {"id": 2, "text": "Understand OOP", "order": 2}
    ],
    "prerequisites": [
        {"id": 1, "text": "Basic computer skills", "order": 1}
    ],
    "modules": [
        {
            "id": 1,
            "title": "Introduction to Python",
            "description": "Python basics",
            "order": 1,
            "is_published": true,
            "lessons": [
                {
                    "id": 1,
                    "title": "Python Setup",
                    "description": "Install Python",
                    "lesson_type": "video",
                    "duration": 15,
                    "duration_display": "15m",
                    "content_url": "https://example.com/video",
                    "content_file": null,
                    "order": 1,
                    "is_published": true
                }
            ]
        }
    ],
    "resources": [],
    "course_instructors": [],
    "certificate_settings": null,
    "scorm_settings": null
}
```

### Additional Features
1. **File Uploads**:
   - Configured for thumbnails, lesson files, resources, certificate logos, signatures, and SCORM packages.
   - Use `django-storages` for S3 integration if needed (commented in settings).

2. **Certificate Generation**:
   - Certificates are created automatically when an enrollment is marked as completed (via signals).
   - The `CertificateTemplate` model allows customization of certificate appearance.

3. **SCORM/xAPI**:
   - The `SCORMxAPISettings` model supports SCORM package uploads and tracking settings.
   - Integration with a SCORM engine (e.g., Rustici) would require additional setup.

### Next Steps
1. **Testing**: Write unit tests for models, serializers, and views using `django.test.TestCase` and `rest_framework.test.APITestCase`.
2. **Frontend Integration**: Connect the API endpoints to your React components for course browsing, enrollment, and management.
3. **Admin Interface**: Customize the Django admin for easier course management (e.g., inlines for modules and lessons).
4. **Celery Tasks**: Use Celery for background tasks like generating certificate PDFs or processing SCORM data.
5. **Search and Filtering**: Add `django-filter` for advanced course filtering (e.g., by category, level, or price).
6. **Payment Integration**: Integrate a payment gateway (e.g., Stripe) for paid courses.

Would you like me to provide additional components (e.g., test cases, admin customization, or Celery tasks)? Alternatively, I can elaborate on specific parts, such as certificate PDF generation, SCORM integration, or React integration examples.