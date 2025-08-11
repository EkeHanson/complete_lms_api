from rest_framework import serializers
from .models import (Category, Course , Module, Lesson,Badge,UserPoints,UserBadge,FAQ,
    Resource, Instructor, CourseInstructor, CertificateTemplate,UserBadge,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating)
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
import json
import logging
from django.utils.text import slugify
from users.models import CustomUser
from utils.supabase import upload_to_supabase
logger = logging.getLogger('course')
import uuid
from utils.storage import get_storage_service

from .models import Assignment, AssignmentSubmission

User = get_user_model()

# Serializer for CourseProgress
# class CourseProgressSerializer(serializers.ModelSerializer):
#     user_email = serializers.CharField(source='user.email', read_only=True)
#     course_title = serializers.CharField(source='course.title', read_only=True)

#     class Meta:
#         model = CourseProgress
#         fields = [
#             'id', 'user', 'user_email', 'course', 'course_title', 'tenant_id',
#             'started_at', 'completed_at', 'progress_percent', 'last_accessed'
#         ]
#         read_only_fields = ['user_email', 'course_title', 'last_accessed']

# Serializer for LessonCompletion
# class LessonCompletionSerializer(serializers.ModelSerializer):
#     lesson_title = serializers.CharField(source='lesson.title', read_only=True)
#     user_email = serializers.CharField(source='user.email', read_only=True)

#     class Meta:
#         model = LessonCompletion
#         fields = ['id', 'user', 'user_email', 'lesson', 'lesson_title', 'completed_at', 'tenant_id']
#         read_only_fields = ['user_email', 'lesson_title', 'completed_at']

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

    def validate(self, data):
        lesson_type = data.get('lesson_type', self.instance.lesson_type if self.instance else None)
        module = data.get('module', self.instance.module if self.instance else None)
        order = data.get('order', None)
        
        logger.debug(f"Validating lesson: lesson_type={lesson_type}, module={module}, order={order}")
        
        if order is not None and module:
            qs = Lesson.objects.filter(module=module, order=order)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                logger.warning(f"Order {order} already exists for module {module.id}")
                # Optionally, allow auto-increment here instead of raising an error
                # max_order = Lesson.objects.filter(module=module).aggregate(models.Max('order'))['order__max']
                # data['order'] = (max_order or 0) + 1
                raise serializers.ValidationError(f"A lesson with order {order} already exists in this module.")
        
        if lesson_type == 'link' and not data.get('content_url'):
            raise serializers.ValidationError("Content URL is required for link lessons")
        if lesson_type in ['video', 'file'] and not data.get('content_file') and not (self.instance and self.instance.content_file):
            raise serializers.ValidationError("Content file is required for this lesson type")
        if lesson_type == 'text' and not data.get('content_text'):
            raise serializers.ValidationError("Content text is required for text lessons")
        return data


    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        content_file = validated_data.pop('content_file', None)
        instance = super().create(validated_data)
        
        if content_file:
            file_name = f"courses/{instance.module.course.slug}/lessons/{uuid.uuid4().hex}_{content_file.name}"
            try:
                file_url = upload_to_supabase(content_file, file_name, content_type=content_file.content_type)
                instance.content_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload content file: {str(e)}")
                raise serializers.ValidationError("Failed to upload content file")
        
        return instance

    def update(self, instance, validated_data):
        tenant = self.context.get('tenant', None)
        content_file = validated_data.pop('content_file', None)
        instance = super().update(instance, validated_data)
        
        if content_file:
            if instance.content_file:
                storage_service = get_storage_service()
                storage_service.delete_file(instance.content_file)
            file_name = f"courses/{instance.module.course.slug}/lessons/{uuid.uuid4().hex}_{content_file.name}"
            try:
                file_url = upload_to_supabase(content_file, file_name, content_type=content_file.content_type)
                instance.content_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload content file: {str(e)}")
                raise serializers.ValidationError("Failed to upload content file")
        
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.content_file:
            storage_service = get_storage_service()
            representation['content_file'] = storage_service.get_public_url(instance.content_file)
        return representation

    class Meta:
        model = Lesson
        fields = "__all__"
        read_only_fields = ['id', 'module']



class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'course', 'description', 'order', 'is_published', 'lessons']

class ResourceSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        file_obj = validated_data.pop('file', None)
        instance = super().create(validated_data)
        
        if file_obj:
            file_name = f"courses/{instance.course.slug}/resources/{uuid.uuid4().hex}_{file_obj.name}"
            try:
                file_url = upload_to_supabase(file_obj, file_name, content_type=file_obj.content_type)
                instance.file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload resource file: {str(e)}")
                raise serializers.ValidationError("Failed to upload resource file")
        
        return instance

    def update(self, instance, validated_data):
        tenant = self.context.get('tenant', None)
        file_obj = validated_data.pop('file', None)
        instance = super().update(instance, validated_data)
        
        if file_obj:
            if instance.file:
                storage_service = get_storage_service()
                storage_service.delete_file(instance.file)
            file_name = f"courses/{instance.course.slug}/resources/{uuid.uuid4().hex}_{file_obj.name}"
            try:
                file_url = upload_to_supabase(file_obj, file_name, content_type=file_obj.content_type)
                instance.file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload resource file: {str(e)}")
                raise serializers.ValidationError("Failed to upload resource file")
        
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.file:
            storage_service = get_storage_service()
            representation['file'] = storage_service.get_public_url(instance.file)
        return representation

    class Meta:
        model = Resource
        fields = ['id', 'title', 'resource_type', 'url', 'file', 'order']



class InstructorUserSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(source='profile.avatar', read_only=True)
    phone = serializers.CharField(source='profile.phone', read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'avatar', 'phone']

# class StudentSummarySerializer(serializers.ModelSerializer):
#     progress = serializers.SerializerMethodField()
#     grade = serializers.SerializerMethodField()

#     class Meta:
#         model = CustomUser
#         fields = ['id', 'email', 'first_name', 'last_name', 'progress', 'grade']

#     def get_progress(self, obj):
#         course = self.context.get('course')
#         cp = CourseProgress.objects.filter(user=obj, course=course).first()
#         return cp.progress_percent if cp else 0

#     def get_grade(self, obj):
#         course = self.context.get('course')
#         grade = Grade.objects.filter(user=obj, course=course).first()
#         return grade.value if grade else None


# class AssignmentSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Assignment
#         fields = ['id', 'title', 'due_date', 'status']

# class QuizSerializer(serializers.ModelSerializer):
#     course_title = serializers.CharField(source='course.title', read_only=True)
#     module_title = serializers.CharField(source='module.title', read_only=True)

#     class Meta:
#         model = Quiz
#         fields = [
#             'id', 'title', 'description', 'quiz_type', 'course', 'course_title',
#             'module', 'module_title', 'start_date', 'end_date', 'duration_minutes',
#             'total_marks', 'passing_score', 'is_active', 'created_at', 'updated_at', 'tenant_id'
#         ]




# class CourseDetailForInstructorSerializer(serializers.ModelSerializer):
#     num_students = serializers.SerializerMethodField()
#     modules = ModuleSerializer(many=True, read_only=True)
#     assignments = AssignmentSerializer(many=True, read_only=True)
#     quizzes = QuizSerializer(many=True, read_only=True)
#     students = serializers.SerializerMethodField()
#     ratings = serializers.FloatField(source='average_rating', read_only=True)

#     class Meta:
#         model = Course
#         fields = '__all__'

#     def get_num_students(self, obj):
#         return obj.enrollments.filter(is_active=True).count()

#     def get_students(self, obj):
#         students = CustomUser.objects.filter(enrollments__course=obj, enrollments__is_active=True)
#         return StudentSummarySerializer(students, many=True, context={'course': obj}).data

# class CourseDetailForInstructorSerializer(serializers.ModelSerializer):
#     num_students = serializers.SerializerMethodField()
#     modules = ModuleSerializer(many=True, read_only=True)
#     assignments = AssignmentSerializer(many=True, read_only=True)
#     quizzes = QuizSerializer(many=True, read_only=True)
#     students = serializers.SerializerMethodField()
#     ratings = serializers.FloatField(source='average_rating', read_only=True)

#     class Meta:
#         model = Course
#         fields = "__all__"

#     # def get_num_students(self, obj):
#     #     return obj.enrollments.filter(is_active=True).count()

#     def get_students(self, obj):
#         students = CustomUser.objects.filter(enrollments__course=obj, enrollments__is_active=True)
#         return StudentSummarySerializer(students, many=True, context={'course': obj}).data




# class CourseDetailForInstructorSerializer(serializers.ModelSerializer):
#     num_students = serializers.SerializerMethodField()
#     modules = ModuleSerializer(many=True, read_only=True)
#     assignments = AssignmentSerializer(many=True, read_only=True)
#     quizzes = QuizSerializer(many=True, read_only=True)
#     students = serializers.SerializerMethodField()
#     ratings = serializers.FloatField(source='average_rating', read_only=True)

#     class Meta:
#         model = Course
#         fields = "__all__"

#     def get_num_students(self, obj):
#         if hasattr(obj, 'course'):
#             # Handle case where obj is a CourseInstructor
#             return obj.course.enrollments.filter(is_active=True).count()
#         elif hasattr(obj, 'enrollments'):
#             # Handle case where obj is a Course
#             return obj.enrollments.filter(is_active=True).count()
#         return 0

#     def get_students(self, obj):
#         students = CustomUser.objects.filter(enrollments__course=obj, enrollments__is_active=True)
#         return StudentSummarySerializer(students, many=True, context={'course': obj}).data




# class InstructorDashboardSerializer(serializers.ModelSerializer):
#     user = InstructorUserSerializer(read_only=True)
#     courses = serializers.SerializerMethodField()
#     messages = serializers.SerializerMethodField()
#     assignments = serializers.SerializerMethodField()
#     quizzes = serializers.SerializerMethodField()
#     students = serializers.SerializerMethodField()
#     schedule = serializers.SerializerMethodField()
#     analytics = serializers.SerializerMethodField()
#     feedbackHistory = serializers.SerializerMethodField()
#     compliance = serializers.SerializerMethodField()

#     class Meta:
#         model = Instructor
#         fields = [
#             'id', 'user', 'bio', 'is_active', 'department', 'courses',
#             'messages', 'assignments', 'quizzes', 'students', 'schedule',
#             'analytics', 'feedbackHistory', 'compliance'
#         ]

#     def get_courses(self, instructor):
#         course_ids = CourseInstructor.objects.filter(instructor=instructor).values_list('course_id', flat=True)
#         courses = Course.objects.filter(id__in=course_ids)
#         return CourseDetailForInstructorSerializer(courses, many=True).data

#     def get_messages(self, instructor):
#         # Implement your logic for instructor messages
#         return []

#     def get_assignments(self, instructor):
#         # All assignments for instructor's courses
#         course_ids = CourseInstructor.objects.filter(instructor=instructor).values_list('course_id', flat=True)
#         assignments = Assignment.objects.filter(course_id__in=course_ids)
#         return AssignmentSerializer(assignments, many=True).data

#     def get_quizzes(self, instructor):
#         # All quizzes for instructor's courses
#         course_ids = CourseInstructor.objects.filter(instructor=instructor).values_list('course_id', flat=True)
#         quizzes = Quiz.objects.filter(course_id__in=course_ids)
#         return QuizSerializer(quizzes, many=True).data

#     def get_students(self, instructor):
#         # All students enrolled in instructor's courses
#         course_ids = CourseInstructor.objects.filter(instructor=instructor).values_list('course_id', flat=True)
#         students = CustomUser.objects.filter(enrollments__course_id__in=course_ids, enrollments__is_active=True).distinct()
#         return StudentSummarySerializer(students, many=True).data

#     def get_schedule(self, instructor):
#         # Implement your logic for instructor schedule/calendar
#         return []

#     def get_analytics(self, instructor):
#         # Implement your logic for analytics
#         return {}

#     def get_feedbackHistory(self, instructor):
#         # All feedback for instructor's courses
#         course_ids = CourseInstructor.objects.filter(instructor=instructor).values_list('course_id', flat=True)
#         feedbacks = Feedback.objects.filter(course_id__in=course_ids)
#         return FeedbackSerializer(feedbacks, many=True).data

#     def get_compliance(self, instructor):
#         # Implement your logic for compliance documents/status
#         return {}

class CertificateTemplateSerializer(serializers.ModelSerializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), required=False)


    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        logo_file = validated_data.pop('logo', None)
        signature_file = validated_data.pop('signature', None)
        instance = super().create(validated_data)
        
        storage_service = get_storage_service()
        if logo_file:
            file_name = f"courses/{instance.course.slug}/certificates/logos/{uuid.uuid4().hex}_{logo_file.name}"
            try:
                file_url = upload_to_supabase(logo_file, file_name, content_type=logo_file.content_type)
                instance.logo = file_name
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload logo: {str(e)}")
                raise serializers.ValidationError("Failed to upload logo")
        
        if signature_file:
            file_name = f"courses/{instance.course.slug}/certificates/signatures/{uuid.uuid4().hex}_{signature_file.name}"
            try:
                file_url = upload_to_supabase(signature_file, file_name, content_type=signature_file.content_type)
                instance.signature = file_name
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload signature: {str(e)}")
                raise serializers.ValidationError("Failed to upload signature")
        
        if logo_file or signature_file:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        tenant = self.context.get('tenant', None)
        logo_file = validated_data.pop('logo', None)
        signature_file = validated_data.pop('signature', None)
        instance = super().update(instance, validated_data)
        
        storage_service = get_storage_service()
        if logo_file:
            if instance.logo:
                storage_service.delete_file(instance.logo)
            file_name = f"courses/{instance.course.slug}/certificates/logos/{uuid.uuid4().hex}_{logo_file.name}"
            try:
                file_url = upload_to_supabase(logo_file, file_name, content_type=logo_file.content_type)
                instance.logo = file_name
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload logo: {str(e)}")
                raise serializers.ValidationError("Failed to upload logo")
        
        if signature_file:
            if instance.signature:
                storage_service.delete_file(instance.signature)
            file_name = f"courses/{instance.course.slug}/certificates/signatures/{uuid.uuid4().hex}_{signature_file.name}"
            try:
                file_url = upload_to_supabase(signature_file, file_name, content_type=signature_file.content_type)
                instance.signature = file_name
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload signature: {str(e)}")
                raise serializers.ValidationError("Failed to upload signature")
        
        if logo_file or signature_file:
            instance.save()
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        storage_service = get_storage_service()
        if instance.logo:
            representation['logo'] = storage_service.get_public_url(instance.logo)
        if instance.signature:
            representation['signature'] = storage_service.get_public_url(instance.signature)
        return representation

    class Meta:
        model = CertificateTemplate
        fields = ['id', 'course', 'is_active', 'template', 'custom_text', 'logo', 'signature',
                  'signature_name', 'show_date', 'show_course_name', 'show_completion_hours',
                  'min_score', 'require_all_modules']
        
    
class SCORMxAPISettingsSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        package_file = validated_data.pop('package', None)
        instance = super().create(validated_data)
        
        if package_file:
            file_name = f"courses/{instance.course.slug}/scorm_packages/{uuid.uuid4().hex}_{package_file.name}"
            try:
                file_url = upload_to_supabase(package_file, file_name, content_type=package_file.content_type)
                instance.package = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload SCORM package: {str(e)}")
                raise serializers.ValidationError("Failed to upload SCORM package")
        
        return instance

    def update(self, instance, validated_data):
        tenant = self.context.get('tenant', None)
        package_file = validated_data.pop('package', None)
        instance = super().update(instance, validated_data)
        
        if package_file:
            if instance.package:
                storage_service = get_storage_service()
                storage_service.delete_file(instance.package)
            file_name = f"courses/{instance.course.slug}/scorm_packages/{uuid.uuid4().hex}_{package_file.name}"
            try:
                file_url = upload_to_supabase(package_file, file_name, content_type=package_file.content_type)
                instance.package = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload SCORM package: {str(e)}")
                raise serializers.ValidationError("Failed to upload SCORM package")
        
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.package:
            storage_service = get_storage_service()
            representation['package'] = storage_service.get_public_url(instance.package)
        return representation
    class Meta:
        model = SCORMxAPISettings
        fields = ['id', 'is_active', 'standard', 'version', 'completion_threshold', 'score_threshold', 'track_completion', 'track_score', 'track_time', 'track_progress', 'package']


class CourseSerializer(serializers.ModelSerializer):
    course_instructors = serializers.SerializerMethodField()
    faq_count = serializers.IntegerField(read_only=True)
    faqs = FAQSerializer(many=True, read_only=True)
    total_enrollments = serializers.IntegerField(read_only=True)
    resources = ResourceSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    learning_outcomes = serializers.ListField(
        child=serializers.CharField(max_length=500, allow_blank=True),
        required=False,
        default=list
    )
    prerequisites = serializers.ListField(
        child=serializers.CharField(max_length=500, allow_blank=True),
        required=False,
        default=list
    )
    modules = ModuleSerializer(many=True, read_only=True)
    certificate_settings = CertificateTemplateSerializer(read_only=True)
    scorm_settings = SCORMxAPISettingsSerializer(read_only=True)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    def get_course_instructors(self, obj):
        instructors = CourseInstructor.objects.filter(course=obj)
        return InstructorUserSerializer([ci.instructor.user for ci in instructors], many=True).data

    def to_internal_value(self, data):
        for field in ['learning_outcomes', 'prerequisites']:
            if field in data:
                value = data[field]
                if isinstance(value, list):
                    cleaned_value = []
                    for item in value:
                        try:
                            parsed = item if isinstance(item, str) else json.loads(item)
                            cleaned_value.append(str(parsed) if not isinstance(parsed, str) else parsed)
                        except (json.JSONDecodeError, TypeError):
                            cleaned_value.append(str(item))
                    data[field] = cleaned_value
        return super().to_internal_value(data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.thumbnail:
            storage_service = get_storage_service()
            representation['thumbnail'] = storage_service.get_public_url(instance.thumbnail)
        if 'learning_outcomes' in representation:
            representation['learning_outcomes'] = self.flatten_array(representation['learning_outcomes'])
        if 'prerequisites' in representation:
            representation['prerequisites'] = self.flatten_array(representation['prerequisites'])
        return representation

    def flatten_array(self, data):
        flat_list = []
        for item in data:
            if isinstance(item, list):
                flat_list.extend([str(i) for i in item])
            elif isinstance(item, str):
                try:
                    parsed = json.loads(item)
                    if isinstance(parsed, list):
                        flat_list.extend([str(i) for i in parsed])
                    else:
                        flat_list.append(item)
                except json.JSONDecodeError:
                    flat_list.append(item)
            else:
                flat_list.append(str(item))
        return flat_list

    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        thumbnail_file = validated_data.pop('thumbnail', None)
        if 'slug' not in validated_data or not validated_data['slug']:
            title = validated_data.get('title', '')
            validated_data['slug'] = slugify(title)
        instance = super().create(validated_data)
        if thumbnail_file:
            file_name = f"courses/{instance.slug}/thumbnails/{uuid.uuid4().hex}_{thumbnail_file.name}"
            try:
                file_url = upload_to_supabase(thumbnail_file, file_name, content_type=thumbnail_file.content_type)
                instance.thumbnail = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload thumbnail: {str(e)}")
                raise serializers.ValidationError("Failed to upload thumbnail")
        return instance

    def update(self, instance, validated_data):
        tenant = self.context.get('tenant', None)
        thumbnail_file = validated_data.pop('thumbnail', None)
        if 'title' in validated_data:
            validated_data['slug'] = slugify(validated_data['title'])
        instance = super().update(instance, validated_data)
        if thumbnail_file:
            if instance.thumbnail:
                storage_service = get_storage_service()
                storage_service.delete_file(instance.thumbnail)
            file_name = f"courses/{instance.slug}/thumbnails/{uuid.uuid4().hex}_{thumbnail_file.name}"
            try:
                file_url = upload_to_supabase(thumbnail_file, file_name, content_type=thumbnail_file.content_type)
                instance.thumbnail = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload thumbnail: {str(e)}")
                raise serializers.ValidationError("Failed to upload thumbnail")
        return instance

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'learning_outcomes', 'prerequisites', 'slug', 'code', 'description',
            'short_description', 'category', 'category_id', 'level', 'status', 'duration', 'price',
            'discount_price', 'currency', 'thumbnail', 'faq_count', 'faqs', 'created_at', 'updated_at',
            'created_by', 'created_by_username', 'completion_hours', 'current_price',
            'modules', 'resources', 'course_instructors', 'certificate_settings', 'scorm_settings',
            'total_enrollments'
        ]


# class CourseSerializer(serializers.ModelSerializer):
#     course_instructors = serializers.SerializerMethodField()
#     faq_count = serializers.IntegerField(read_only=True)
#     faqs = FAQSerializer(many=True, read_only=True)
#     total_enrollments = serializers.IntegerField(read_only=True)
#     resources = ResourceSerializer(many=True, read_only=True)
#     category = CategorySerializer(read_only=True)
#     category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
#     learning_outcomes = serializers.ListField(
#         child=serializers.CharField(max_length=500, allow_blank=True),
#         required=False,
#         default=list
#     )
#     prerequisites = serializers.ListField(
#         child=serializers.CharField(max_length=500, allow_blank=True),
#         required=False,
#         default=list
#     )
#     modules = ModuleSerializer(many=True, read_only=True)
#     resources = ResourceSerializer(many=True, read_only=True)
#     course_instructors = CourseDetailForInstructorSerializer(many=True, read_only=True)
#     certificate_settings = CertificateTemplateSerializer(read_only=True)
#     scorm_settings = SCORMxAPISettingsSerializer(read_only=True)
#     current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
#     created_by_username = serializers.CharField(source='created_by.username', read_only=True)


#     def get_course_instructors(self, obj):
#         instructors = CourseInstructor.objects.filter(course=obj)
#         return InstructorUserSerializer([ci.instructor for ci in instructors], many=True).data


#     def to_internal_value(self, data):
#         # Clean up learning_outcomes and prerequisites
#         for field in ['learning_outcomes', 'prerequisites']:
#             if field in data:
#                 value = data[field]
#                 if isinstance(value, list):
#                     cleaned_value = []
#                     for item in value:
#                         try:
#                             parsed = item if isinstance(item, str) else json.loads(item)
#                             cleaned_value.append(str(parsed) if not isinstance(parsed, str) else parsed)
#                         except (json.JSONDecodeError, TypeError):
#                             cleaned_value.append(str(item))
#                     data[field] = cleaned_value
#         return super().to_internal_value(data)

    
#     def to_representation(self, instance):
#         representation = super().to_representation(instance)
#         if instance.thumbnail:
#             storage_service = get_storage_service()
#             representation['thumbnail'] = storage_service.get_public_url(instance.thumbnail)
        
#         # Ensure learning_outcomes is a flat array of strings
#         if 'learning_outcomes' in representation:
#             representation['learning_outcomes'] = self.flatten_array(representation['learning_outcomes'])
        
#         # Ensure prerequisites is a flat array of strings
#         if 'prerequisites' in representation:
#             representation['prerequisites'] = self.flatten_array(representation['prerequisites'])
        
#         return representation


    
#     def flatten_array(self, data):
#         """Convert nested arrays into a flat array of strings"""
#         flat_list = []
#         for item in data:
#             if isinstance(item, list):
#                 flat_list.extend([str(i) for i in item])
#             elif isinstance(item, str):
#                 try:
#                     # Handle case where string might be JSON-encoded array
#                     parsed = json.loads(item)
#                     if isinstance(parsed, list):
#                         flat_list.extend([str(i) for i in parsed])
#                     else:
#                         flat_list.append(item)
#                 except json.JSONDecodeError:
#                     flat_list.append(item)
#             else:
#                 flat_list.append(str(item))
#         return flat_list


#     def create(self, validated_data):
#         tenant = self.context.get('tenant', None)
#         thumbnail_file = validated_data.pop('thumbnail', None)
#         if 'slug' not in validated_data or not validated_data['slug']:
#             title = validated_data.get('title', '')
#             validated_data['slug'] = slugify(title)
#         instance = super().create(validated_data)
        
#         if thumbnail_file:
#             file_name = f"courses/{instance.slug}/thumbnails/{uuid.uuid4().hex}_{thumbnail_file.name}"
#             try:
#                 file_url = upload_to_supabase(thumbnail_file, file_name, content_type=thumbnail_file.content_type)
#                 instance.thumbnail = file_name
#                 instance.save()
#             except Exception as e:
#                 logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload thumbnail: {str(e)}")
#                 raise serializers.ValidationError("Failed to upload thumbnail")
        
#         return instance

#     def update(self, instance, validated_data):
#         tenant = self.context.get('tenant', None)
#         thumbnail_file = validated_data.pop('thumbnail', None)
#         if 'title' in validated_data:
#             validated_data['slug'] = slugify(validated_data['title'])
#         instance = super().update(instance, validated_data)
        
#         if thumbnail_file:
#             # Delete old file if exists
#             if instance.thumbnail:
#                 storage_service = get_storage_service()
#                 storage_service.delete_file(instance.thumbnail)
#             file_name = f"courses/{instance.slug}/thumbnails/{uuid.uuid4().hex}_{thumbnail_file.name}"
#             try:
#                 file_url = upload_to_supabase(thumbnail_file, file_name, content_type=thumbnail_file.content_type)
#                 instance.thumbnail = file_name
#                 instance.save()
#             except Exception as e:
#                 logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload thumbnail: {str(e)}")
#                 raise serializers.ValidationError("Failed to upload thumbnail")
        
#         return instance



#     # def create(self, validated_data):
#     #     if 'slug' not in validated_data or not validated_data['slug']:
#     #         title = validated_data.get('title', '')
#     #         validated_data['slug'] = slugify(title)
#     #     return super().create(validated_data)

#     # def update(self, instance, validated_data):
#     #     if 'title' in validated_data:
#     #         validated_data['slug'] = slugify(validated_data['title'])
#     #     return super().update(instance, validated_data)

#     class Meta:
#         model = Course
#         fields = [  # your fields here...
#             'id', 'title', 'learning_outcomes', 'prerequisites', 'slug', 'code', 'description',
#             'short_description', 'category', 'category_id', 'level', 'status', 'duration', 'price',
#             'discount_price', 'currency', 'thumbnail', 'faq_count', 'faqs', 'created_at', 'updated_at',
#             'created_by', 'created_by_username', 'completion_hours', 'discount_price', 'current_price',
#             'modules', 'resources', 'course_instructors', 'certificate_settings', 'scorm_settings',
#             'total_enrollments'
#         ]


class LearningPathSerializer(serializers.ModelSerializer):
    courses = CourseSerializer(many=True, read_only=True)
    course_ids = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), many=True, source='courses', write_only=True)

    class Meta:
        model = LearningPath
        fields = ['id', 'title', 'description', 'courses', 'course_ids', 'is_active', 'order', 'created_at', 'updated_at', 'created_by']

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


class CertificateSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        pdf_file = validated_data.pop('pdf_file', None)
        instance = super().create(validated_data)
        
        if pdf_file:
            file_name = f"certificates/pdfs/{uuid.uuid4().hex}_{pdf_file.name}"
            try:
                file_url = upload_to_supabase(pdf_file, file_name, content_type=pdf_file.content_type)
                instance.pdf_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload PDF file: {str(e)}")
                raise serializers.ValidationError("Failed to upload PDF file")
        
        return instance

    def update(self,instance, validated_data):
        tenant = validated_data.get('tenant', None)
        pdf_file = validated_data.pop('pdf_file', None)
        instance = super().update(instance, validated_data)
        
        if pdf_file:
            if instance.pdf_file:
                storage_service = get_storage_service()
                storage_service.delete_file(instance.pdf_file)
            file_name = f"certificates/pdfs/{uuid.uuid4().hex}_{pdf_file.name}"
            try:
                file_url = upload_to_supabase(pdf_file, file_name, content_type=pdf_file.content_type)
                instance.pdf_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload PDF file: {str(e)}")
                raise serializers.ValidationError("Failed to upload PDF file")
        
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.pdf_file:
            storage_service = get_storage_service()
            representation['pdf_file'] = storage_service.get_public_url(instance.pdf_file)
        return representation



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

    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        image_file = validated_data.pop('image', None)
        instance = super().create(validated_data)
        
        if image_file:
            file_name = f"badges/{uuid.uuid4().hex}_{image_file.name}"
            try:
                file_url = upload_to_supabase(image_file, file_name, content_type=image_file.content_type)
                instance.image = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload badge image: {str(e)}")
                raise serializers.ValidationError("Failed to upload badge image")
        
        return instance

    def update(self, instance, validated_data):
        tenant = self.context.get('tenant', None)
        image_file = validated_data.pop('image', None)
        instance = super().update(instance, validated_data)
        
        if image_file:
            if instance.image:
                storage_service = get_storage_service()
                storage_service.delete_file(instance.image)
            file_name = f"badges/{uuid.uuid4().hex}_{image_file.name}"
            try:
                file_url = upload_to_supabase(image_file, file_name, content_type=image_file.content_type)
                instance.image = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload badge image: {str(e)}")
                raise serializers.ValidationError("Failed to upload badge image")
        
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.image:
            storage_service = get_storage_service()
            representation['image'] = storage_service.get_public_url(instance.image)
        return representation

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




# class AssignmentSerializer(serializers.ModelSerializer):
#     course_name = serializers.CharField(source='course.title', read_only=True)
#     module_name = serializers.CharField(source='module.title', read_only=True)
#     created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

#     def validate(self, data):
#         course = data.get('course', self.instance.course if self.instance else None)
#         module = data.get('module', self.instance.module if self.instance else None)
#         title = data.get('title', self.instance.title if self.instance else None)
#         due_date = data.get('due_date', self.instance.due_date if self.instance else None)
#         instructions_file = data.get('instructions_file', None)

#         logger.debug(f"Validating assignment: course={course}, module={module}, title={title}, due_date={due_date}")

#         if not course:
#             raise serializers.ValidationError("Course is required for assignment.")
#         if not title:
#             raise serializers.ValidationError("Title is required for assignment.")
#         if not due_date:
#             raise serializers.ValidationError("Due date is required for assignment.")

#         # Optionally, check for duplicate assignment titles in the same module/course
#         qs = Assignment.objects.filter(course=course, title=title)
#         if module:
#             qs = qs.filter(module=module)
#         if self.instance:
#             qs = qs.exclude(pk=self.instance.pk)
#         if qs.exists():
#             raise serializers.ValidationError("An assignment with this title already exists for this module/course.")

#         return data

#     def create(self, validated_data):
#         tenant = self.context.get('tenant', None)
#         instructions_file = validated_data.pop('instructions_file', None)
#         instance = super().create(validated_data)

#         if instructions_file:
#             if instance.module:
#                 file_name = f"courses/{instance.course.slug}/modules/{instance.module.id}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
#             else:
#                 file_name = f"courses/{instance.course.slug}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
#             try:
#                 from utils.supabase import upload_to_supabase
#                 file_url = upload_to_supabase(instructions_file, file_name, content_type=instructions_file.content_type)
#                 instance.instructions_file = file_name
#                 instance.save()
#             except Exception as e:
#                 logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload assignment file: {str(e)}")
#                 raise serializers.ValidationError("Failed to upload assignment file")

#         return instance

#     def update(self, instance, validated_data):
#         tenant = self.context.get('tenant', None)
#         instructions_file = validated_data.pop('instructions_file', None)
#         instance = super().update(instance, validated_data)

#         if instructions_file:
#             storage_service = get_storage_service()
#             if instance.instructions_file:
#                 storage_service.delete_file(instance.instructions_file)
#             if instance.module:
#                 file_name = f"courses/{instance.course.slug}/modules/{instance.module.id}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
#             else:
#                 file_name = f"courses/{instance.course.slug}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
#             try:
#                 from utils.supabase import upload_to_supabase
#                 file_url = upload_to_supabase(instructions_file, file_name, content_type=instructions_file.content_type)
#                 instance.instructions_file = file_name
#                 instance.save()
#             except Exception as e:
#                 logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload assignment file: {str(e)}")
#                 raise serializers.ValidationError("Failed to upload assignment file")

#         return instance

#     def to_representation(self, instance):
#         representation = super().to_representation(instance)
#         if instance.instructions_file:
#             storage_service = get_storage_service()
#             representation['instructions_file'] = storage_service.get_public_url(instance.instructions_file)
#         # Add names for course, module, and created_by
#         representation['course_name'] = instance.course.title if instance.course else None
#         representation['module_name'] = instance.module.title if instance.module else None
#         representation['created_by_name'] = instance.created_by.get_full_name() if instance.created_by else None
#         return representation

#     class Meta:
#         model = Assignment
#         fields = '__all__'





# class FeedbackSerializer(serializers.ModelSerializer):
#     course = serializers.SlugRelatedField(slug_field='title', read_only=True, allow_null=True)
#     user = serializers.SlugRelatedField(slug_field='email', read_only=True)
#     class Meta:
#         model = Feedback
#         fields = ['id', 'user', 'course', 'type', 'content', 'rating', 'created_at']

# class CartSerializer(serializers.ModelSerializer):
#     course = serializers.SlugRelatedField(slug_field='title', read_only=True)
#     class Meta:
#         model = Cart
#         fields = ['id', 'course', 'added_at']

# class WishlistSerializer(serializers.ModelSerializer):
#     course = serializers.SlugRelatedField(slug_field='title', read_only=True)
#     class Meta:
#         model = Wishlist
#         fields = ['id', 'course', 'added_at']

# class GradeSerializer(serializers.ModelSerializer):
#     course = serializers.SlugRelatedField(slug_field='title', read_only=True)
#     assignment = serializers.SlugRelatedField(slug_field='title', read_only=True, allow_null=True)
#     class Meta:
#         model = Grade
#         fields = ['id', 'user', 'course', 'assignment', 'score', 'created_at']


# class AnalyticsSerializer(serializers.ModelSerializer):
#     course = serializers.SlugRelatedField(slug_field='title', read_only=True, allow_null=True)
#     class Meta:
#         model = Analytics
#         fields = ['id', 'user', 'course', 'total_time_spent', 'weekly_time_spent', 'strengths', 'weaknesses', 'last_updated']

# class CourseProgressSerializer(serializers.ModelSerializer):
#     user_email = serializers.CharField(source='user.email', read_only=True)
#     course_title = serializers.CharField(source='course.title', read_only=True)

#     class Meta:
#         model = CourseProgress
#         fields = [
#             'id', 'user', 'user_email', 'course', 'course_title', 'tenant_id',
#             'started_at', 'completed_at', 'progress_percent', 'last_accessed'
#         ]
#         read_only_fields = ['user_email', 'course_title', 'last_accessed']

# def calculate_course_progress(user, course):
#     total_lessons = course.modules.aggregate(
#         total=models.Count('lessons')
#     )['total']
#     completed_lessons = LessonCompletion.objects.filter(
#         user=user, lesson__module__course=course
#     ).count()
#     if total_lessons == 0:
#         return 0
#     return round((completed_lessons / total_lessons) * 100, 2)

class InstructorCourseSummarySerializer(serializers.ModelSerializer):
    num_students = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'status', 'num_students']

    def get_num_students(self, obj):
        return obj.enrollments.filter(is_active=True).count()

# class InstructorFullProfileSerializer(serializers.ModelSerializer):
#     user = InstructorUserSerializer(read_only=True)
#     courses = serializers.SerializerMethodField()

#     class Meta:
#         model = Instructor
#         fields = ['id', 'user', 'bio', 'is_active', 'courses']

#     def get_courses(self, instructor):
#         course_ids = CourseInstructor.objects.filter(
#             instructor=instructor
#         ).values_list('course_id', flat=True)
#         courses = Course.objects.filter(id__in=course_ids)
#         return CourseDetailForInstructorSerializer(courses, many=True).data





# class CourseSerializer(serializers.ModelSerializer):
#     course_instructors = serializers.SerializerMethodField()
#     faq_count = serializers.IntegerField(read_only=True)
#     faqs = FAQSerializer(many=True, read_only=True)
#     total_enrollments = serializers.IntegerField(read_only=True)
#     resources = ResourceSerializer(many=True, read_only=True)
#     category = CategorySerializer(read_only=True)
#     category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
#     learning_outcomes = serializers.ListField(
#         child=serializers.CharField(max_length=500, allow_blank=True),
#         required=False,
#         default=list
#     )
#     prerequisites = serializers.ListField(
#         child=serializers.CharField(max_length=500, allow_blank=True),
#         required=False,
#         default=list
#     )
#     modules = ModuleSerializer(many=True, read_only=True)
#     resources = ResourceSerializer(many=True, read_only=True)
#     # course_instructors = CourseDetailForInstructorSerializer(many=True, read_only=True)
#     certificate_settings = CertificateTemplateSerializer(read_only=True)
#     scorm_settings = SCORMxAPISettingsSerializer(read_only=True)
#     current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
        
#         if thumbnail_file:
#             file_name = f"courses/{instance.slug}/thumbnails/{uuid.uuid4().hex}_{thumbnail_file.name}"
#             try:
#                 file_url = upload_to_supabase(thumbnail_file, file_name, content_type=thumbnail_file.content_type)
#                 instance.thumbnail = file_name
#                 instance.save()
#             except Exception as e:
#                 logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload thumbnail: {str(e)}")
#                 raise serializers.ValidationError("Failed to upload thumbnail")
        
#         return instance

#     def update(self, instance, validated_data):
#         tenant = self.context.get('tenant', None)
#         thumbnail_file = validated_data.pop('thumbnail', None)
#         if 'title' in validated_data:
#             validated_data['slug'] = slugify(validated_data['title'])
#         instance = super().update(instance, validated_data)
        
#         if thumbnail_file:
#             # Delete old file if exists
#             if instance.thumbnail:
#                 storage_service = get_storage_service()
#                 storage_service.delete_file(instance.thumbnail)
#             file_name = f"courses/{instance.slug}/thumbnails/{uuid.uuid4().hex}_{thumbnail_file.name}"
#             try:
#                 file_url = upload_to_supabase(thumbnail_file, file_name, content_type=thumbnail_file.content_type)
#                 instance.thumbnail = file_name
#                 instance.save()
#             except Exception as e:
#                 logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload thumbnail: {str(e)}")
#                 raise serializers.ValidationError("Failed to upload thumbnail")
        
#         return instance



#     # def create(self, validated_data):
#     #     if 'slug' not in validated_data or not validated_data['slug']:
#     #         title = validated_data.get('title', '')
#     #         validated_data['slug'] = slugify(title)
#     #     return super().create(validated_data)

#     # def update(self, instance, validated_data):
#     #     if 'title' in validated_data:
#     #         validated_data['slug'] = slugify(validated_data['title'])
#     #     return super().update(instance, validated_data)

#     class Meta:
#         model = Course
#         fields = [
#             'id', 'title', 'learning_outcomes', 'prerequisites', 'slug', 'code', 'description',
#             'short_description', 'category', 'category_id', 'level', 'status', 'duration', 'price',
#             'discount_price', 'currency', 'thumbnail', 'faq_count', 'faqs', 'created_at', 'updated_at',
#             'created_by', 'created_by_username', 'completion_hours', 'discount_price', 'current_price',
#             'modules', 'resources', 'course_instructors', 'certificate_settings', 'scorm_settings',
#             'total_enrollments'
#         ]


class LearningPathSerializer(serializers.ModelSerializer):
    courses = CourseSerializer(many=True, read_only=True)
    course_ids = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), many=True, source='courses', write_only=True)

    class Meta:
        model = LearningPath
        fields = ['id', 'title', 'description', 'courses', 'course_ids', 'is_active', 'order', 'created_at', 'updated_at', 'created_by']

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


class CertificateSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        pdf_file = validated_data.pop('pdf_file', None)
        instance = super().create(validated_data)
        
        if pdf_file:
            file_name = f"certificates/pdfs/{uuid.uuid4().hex}_{pdf_file.name}"
            try:
                file_url = upload_to_supabase(pdf_file, file_name, content_type=pdf_file.content_type)
                instance.pdf_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload PDF file: {str(e)}")
                raise serializers.ValidationError("Failed to upload PDF file")
        
        return instance

    def update(self,instance, validated_data):
        tenant = validated_data.get('tenant', None)
        pdf_file = validated_data.pop('pdf_file', None)
        instance = super().update(instance, validated_data)
        
        if pdf_file:
            if instance.pdf_file:
                storage_service = get_storage_service()
                storage_service.delete_file(instance.pdf_file)
            file_name = f"certificates/pdfs/{uuid.uuid4().hex}_{pdf_file.name}"
            try:
                file_url = upload_to_supabase(pdf_file, file_name, content_type=pdf_file.content_type)
                instance.pdf_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload PDF file: {str(e)}")
                raise serializers.ValidationError("Failed to upload PDF file")
        
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.pdf_file:
            storage_service = get_storage_service()
            representation['pdf_file'] = storage_service.get_public_url(instance.pdf_file)
        return representation



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

    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        image_file = validated_data.pop('image', None)
        instance = super().create(validated_data)
        
        if image_file:
            file_name = f"badges/{uuid.uuid4().hex}_{image_file.name}"
            try:
                file_url = upload_to_supabase(image_file, file_name, content_type=image_file.content_type)
                instance.image = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload badge image: {str(e)}")
                raise serializers.ValidationError("Failed to upload badge image")
        
        return instance

    def update(self, instance, validated_data):
        tenant = self.context.get('tenant', None)
        image_file = validated_data.pop('image', None)
        instance = super().update(instance, validated_data)
        
        if image_file:
            if instance.image:
                storage_service = get_storage_service()
                storage_service.delete_file(instance.image)
            file_name = f"badges/{uuid.uuid4().hex}_{image_file.name}"
            try:
                file_url = upload_to_supabase(image_file, file_name, content_type=image_file.content_type)
                instance.image = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload badge image: {str(e)}")
                raise serializers.ValidationError("Failed to upload badge image")
        
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.image:
            storage_service = get_storage_service()
            representation['image'] = storage_service.get_public_url(instance.image)
        return representation

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




class AssignmentSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.title', read_only=True)
    module_name = serializers.CharField(source='module.title', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    def validate(self, data):
        course = data.get('course', self.instance.course if self.instance else None)
        module = data.get('module', self.instance.module if self.instance else None)
        title = data.get('title', self.instance.title if self.instance else None)
        due_date = data.get('due_date', self.instance.due_date if self.instance else None)
        instructions_file = data.get('instructions_file', None)

        logger.debug(f"Validating assignment: course={course}, module={module}, title={title}, due_date={due_date}")

        if not course:
            raise serializers.ValidationError("Course is required for assignment.")
        if not title:
            raise serializers.ValidationError("Title is required for assignment.")
        if not due_date:
            raise serializers.ValidationError("Due date is required for assignment.")

        # Optionally, check for duplicate assignment titles in the same module/course
        qs = Assignment.objects.filter(course=course, title=title)
        if module:
            qs = qs.filter(module=module)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("An assignment with this title already exists for this module/course.")

        return data

    def create(self, validated_data):
        tenant = self.context.get('tenant', None)
        instructions_file = validated_data.pop('instructions_file', None)
        instance = super().create(validated_data)

        if instructions_file:
            if instance.module:
                file_name = f"courses/{instance.course.slug}/modules/{instance.module.id}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
            else:
                file_name = f"courses/{instance.course.slug}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
            try:
                from utils.supabase import upload_to_supabase
                file_url = upload_to_supabase(instructions_file, file_name, content_type=instructions_file.content_type)
                instance.instructions_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload assignment file: {str(e)}")
                raise serializers.ValidationError("Failed to upload assignment file")

        return instance

    def update(self, instance, validated_data):
        tenant = self.context.get('tenant', None)
        instructions_file = validated_data.pop('instructions_file', None)
        instance = super().update(instance, validated_data)

        if instructions_file:
            storage_service = get_storage_service()
            if instance.instructions_file:
                storage_service.delete_file(instance.instructions_file)
            if instance.module:
                file_name = f"courses/{instance.course.slug}/modules/{instance.module.id}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
            else:
                file_name = f"courses/{instance.course.slug}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
            try:
                from utils.supabase import upload_to_supabase
                file_url = upload_to_supabase(instructions_file, file_name, content_type=instructions_file.content_type)
                instance.instructions_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload assignment file: {str(e)}")
                raise serializers.ValidationError("Failed to upload assignment file")

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.instructions_file:
            storage_service = get_storage_service()
            representation['instructions_file'] = storage_service.get_public_url(instance.instructions_file)
        # Add names for course, module, and created_by
        representation['course_name'] = instance.course.title if instance.course else None
        representation['module_name'] = instance.module.title if instance.module else None
        representation['created_by_name'] = instance.created_by.get_full_name() if instance.created_by else None
        return representation

    class Meta:
        model = Assignment
        fields = '__all__'


class AssignmentBriefSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.title', read_only=True)
    module_name = serializers.CharField(source='module.title', read_only=True)

    class Meta:
        model = Assignment
        fields = ['id', 'title', 'course_name', 'module_name']



class AssignmentBriefSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.title', read_only=True)
    module_name = serializers.CharField(source='module.title', read_only=True)

    class Meta:
        model = Assignment
        fields = ['id', 'title', 'course_name', 'module_name']

class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(read_only=True)
    #assignment = serializers.PrimaryKeyRelatedField(queryset=Assignment.objects.all())
    assignment = AssignmentBriefSerializer(read_only=True)
    submission_file = serializers.FileField(required=False, allow_null=True)
    response_text = serializers.CharField(required=False, allow_blank=True)
    grade = serializers.IntegerField(required=False, allow_null=True)
    feedback = serializers.CharField(required=False, allow_blank=True)
    is_graded = serializers.BooleanField(required=False)
    submitted_at = serializers.DateTimeField(read_only=True)


 

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id', 'assignment', 'student', 'submitted_at', 'submission_file',
            'response_text', 'grade', 'feedback', 'is_graded'
        ]
        read_only_fields = ['id', 'student', 'submitted_at', 'grade', 'feedback', 'is_graded']




    def create(self, validated_data):
        submission_file = validated_data.pop('submission_file', None)
        instance = super().create(validated_data)

        if submission_file:
            file_name = f"assignments/submissions/{uuid.uuid4().hex}_{submission_file.name}"
            try:
                storage_service = get_storage_service()
                storage_service.upload_file(
                    submission_file,
                    file_name,
                    content_type=submission_file.content_type
                )
                instance.submission_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"Failed to upload submission file: {str(e)}")
                raise serializers.ValidationError("Failed to upload submission file")
        return instance

    def update(self, instance, validated_data):
        tenant = self.context.get('tenant', None)
        submission_file = validated_data.pop('submission_file', None)
        instance = super().update(instance, validated_data)

        if submission_file:
            storage_service = get_storage_service()
            if instance.submission_file:
                storage_service.delete_file(instance.submission_file)
            file_name = f"assignments/submissions/{uuid.uuid4().hex}_{submission_file.name}"
            try:
                from utils.supabase import upload_to_supabase
                file_url = upload_to_supabase(submission_file, file_name, content_type=submission_file.content_type)
                instance.submission_file = file_name
                instance.save()
            except Exception as e:
                logger.error(f"[{tenant.schema_name if tenant else 'unknown'}] Failed to upload submission file: {str(e)}")
                raise serializers.ValidationError("Failed to upload submission file")

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.submission_file:
            storage_service = get_storage_service()
            representation['submission_file'] = storage_service.get_public_url(instance.submission_file)
        return representation

