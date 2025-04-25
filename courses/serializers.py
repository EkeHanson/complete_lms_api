from rest_framework import serializers
from .models import (Category, Course , Module, Lesson,Badge,UserPoints,UserBadge,FAQ,
    Resource, Instructor, CourseInstructor, CertificateTemplate,UserBadge,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating
)
from django.contrib.auth import get_user_model
from django.utils.text import slugify


User = get_user_model()

class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer', 'order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class CategorySerializer(serializers.ModelSerializer):
    course_count = serializers.IntegerField(read_only=True)
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'created_by', 'course_count']
        read_only_fields = ['slug', 'created_by', 'course_count']


    def create(self, validated_data):
        validated_data['slug'] = slugify(validated_data['name'])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'name' in validated_data:
            validated_data['slug'] = slugify(validated_data['name'])
        return super().update(instance, validated_data)

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'module', 'title', 'lesson_type', 'content_url', 'content_file', 'duration', 'order', 'is_published']
        read_only_fields = ['id', 'module']
        
    def validate(self, data):
        """
        Validate that either content_url or content_file is provided based on lesson_type
        """
        lesson_type = data.get('lesson_type', self.instance.lesson_type if self.instance else None)
        
        if lesson_type == 'link' and not data.get('content_url'):
            raise serializers.ValidationError("Content URL is required for link lessons")
            
        if lesson_type in ['video', 'file'] and not data.get('content_file') and not (self.instance and self.instance.content_file):
            raise serializers.ValidationError("Content file is required for this lesson type")
            
        return data
class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'course', 'description', 'order', 'is_published', 'lessons']

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
    faq_count = serializers.IntegerField(read_only=True)
    faqs = FAQSerializer(many=True, read_only=True)
    total_enrollments = serializers.IntegerField(read_only=True)
    resources = ResourceSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    learning_outcomes = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=True),
        required=False,
        default=list
    )
    prerequisites = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=True),
        required=False,
        default=list
    )
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
            'id', 'title', 'learning_outcomes', 'prerequisites', 'slug', 'code', 'description', 'short_description', 'category', 'category_id',
            'level', 'status', 'duration', 'price', 'discount_price', 'currency', 'thumbnail','faq_count','faqs',
            'created_at', 'updated_at', 'created_by', 'created_by_username', 'completion_hours',
            'current_price', 'learning_outcomes', 'prerequisites', 'modules', 'resources',
            'course_instructors', 'certificate_settings', 'scorm_settings','total_enrollments',
        ]

class LearningPathSerializer(serializers.ModelSerializer):
    courses = CourseSerializer(many=True, read_only=True)
    course_ids = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), many=True, source='courses', write_only=True)

    class Meta:
        model = LearningPath
        fields = ['id', 'title', 'description', 'courses', 'course_ids', 'is_active', 'order', 'created_at', 'updated_at']

class EnrollmentCourseSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    
    class Meta:
        model = Course
        fields = "__all__"

class EnrollmentSerializer(serializers.ModelSerializer):
    course = EnrollmentCourseSerializer(read_only=True)
    
    class Meta:
        model = Enrollment
        fields = "__all__"
        # read_only_fields = ['enrollment_date', 'completion_status', 'is_active']


class BulkEnrollmentSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    course_id = serializers.IntegerField(required=False)  # Optional for course-specific endpoints
    
    def validate_user_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User does not exist")
        return value
    
    def validate_course_id(self, value):
        if not Course.objects.filter(id=value, status='Published').exists():
            raise serializers.ValidationError("Course does not exist or is not published")
        return value
    
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


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'title', 'description', 'image', 'criteria', 'is_active', 'created_at', 'updated_at']

class UserPointsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPoints
        fields = ['id', 'user', 'course', 'points', 'activity_type', 'created_at']

class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer()

    class Meta:
        model = UserBadge
        fields = ['id', 'user', 'badge', 'awarded_at', 'course']

