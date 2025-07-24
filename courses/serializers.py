from rest_framework import serializers
from .models import (Category, Course , Module, Lesson,Badge,UserPoints,UserBadge,FAQ,
    Resource, Instructor, CourseInstructor, CertificateTemplate,UserBadge,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating)
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.core.exceptions import ValidationError
import json
import logging
from django.utils.text import slugify
from users.models import CustomUser

logger = logging.getLogger('course')


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

class InstructorUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name']

class InstructorSerializer(serializers.ModelSerializer):
    user = InstructorUserSerializer(read_only=True)
    expertise = CategorySerializer(many=True, read_only=True)

    class Meta:
        model = Instructor
        fields = ['id', 'user', 'bio', 'expertise', 'is_active']






# class CourseInstructorSerializer(serializers.ModelSerializer):
#     instructor = InstructorSerializer(read_only=True)
#     module_titles = serializers.SerializerMethodField()

#     class Meta:
#         model = CourseInstructor
#         fields = ['id', 'instructor', 'assignment_type', 'is_active', 'module_titles']

#     def get_module_titles(self, obj):
#         return [module.title for module in obj.modules.all()]


class CourseInstructorSerializer(serializers.ModelSerializer):
    instructor = InstructorSerializer(read_only=True)
    instructor_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        source='instructor.user',
        write_only=True
    )
    module_titles = serializers.SerializerMethodField()
    modules = serializers.PrimaryKeyRelatedField(
        queryset=Module.objects.all(),
        many=True,
        required=False
    )

    class Meta:
        model = CourseInstructor
        fields = ['id', 'instructor', 'instructor_id', 'assignment_type', 'is_active', 'module_titles', 'modules']

    def get_module_titles(self, obj):
        return [module.title for module in obj.modules.all()]

    def validate(self, data):
        assignment_type = data.get('assignment_type', self.instance.assignment_type if self.instance else 'all')
        modules = data.get('modules', [])
        if assignment_type == 'specific' and not modules:
            raise serializers.ValidationError("Modules must be provided for specific assignment type")
        return data

    def create(self, validated_data):
        logger.debug(f"Validated data: {validated_data}")
        user = validated_data.pop('instructor')['user']
        logger.info(f"Creating/finding Instructor for user: {user.id}, {user.email}")
        instructor, created = Instructor.objects.get_or_create(
            user=user,
            defaults={'bio': 'Auto-created instructor profile', 'is_active': True}
        )
        logger.info(f"Instructor {'created' if created else 'found'}, ID: {instructor.id}")
        validated_data['instructor'] = instructor
        course = self.context.get('course')
        if not course:
            logger.error("No course provided in serializer context")
            raise serializers.ValidationError("Course is required")
        validated_data['course'] = course

        # Check for existing CourseInstructor record
        existing_assignment = CourseInstructor.objects.filter(
            course=course,
            instructor=instructor
        ).first()
        if existing_assignment:
            request = self.context.get('request')
            if request:
                logger.warning(f"[{request.tenant.schema_name}] Instructor {instructor.id} already assigned to course {course.id}")
            else:
                logger.warning(f"Instructor {instructor.id} already assigned to course {course.id}")

            # logger.warning(f"[{self.context['request'].tenant.schema_name}] Instructor {instructor.id} already assigned to course {course.id}")
            
            
            raise serializers.ValidationError(
                f"Instructor {instructor.user.get_username()} is already assigned to this course."
            )

        course_instructor = super().create(validated_data)
        if validated_data.get('modules'):
            course_instructor.modules.set(validated_data['modules'])
        logger.info(f"CourseInstructor created, ID: {course_instructor.id}")
        return course_instructor

    def update(self, instance, validated_data):
        user = validated_data.pop('instructor', {}).get('user')
        if user:
            instructor, created = Instructor.objects.get_or_create(
                user=user,
                defaults={'bio': 'Auto-created instructor profile', 'is_active': True}
            )
            validated_data['instructor'] = instructor
        modules = validated_data.pop('modules', None)
        instance = super().update(instance, validated_data)
        if modules is not None:
            instance.modules.set(modules)
        return instance
    

    
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
    resources = ResourceSerializer(many=True, read_only=True)
    course_instructors = CourseInstructorSerializer(many=True, read_only=True)
    certificate_settings = CertificateTemplateSerializer(read_only=True)
    scorm_settings = SCORMxAPISettingsSerializer(read_only=True)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)


    # def validate_description(self, value):
    #     logger.debug(f"Validating description: {value}")
    #     if not value:
    #         logger.info("Description is empty, returning default empty Draft.js content")
    #         return json.dumps({
    #             "blocks": [{"key": "empty", "text": "", "type": "unstyled", "depth": 0, "inlineStyleRanges": [], "entityRanges": [], "data": {}}],
    #             "entityMap": {}
    #         })
    #     try:
    #         parsed = json.loads(value)
    #         if not isinstance(parsed, dict):
    #             logger.error(f"Description is not a valid JSON object: {value}")
    #             raise ValidationError("Description must be a valid JSON object")
    #         if not parsed.get('blocks') or not isinstance(parsed['blocks'], list):
    #             logger.error(f"Description missing 'blocks' or 'blocks' is not a list: {value}")
    #             raise ValidationError("Description must contain a 'blocks' array")
    #         if not parsed.get('entityMap') or not isinstance(parsed['entityMap'], dict):
    #             logger.error(f"Description missing 'entityMap' or 'entityMap' is not an object: {value}")
    #             raise ValidationError("Description must contain an 'entityMap' object")
            
    #         # Validate each block
    #         for block in parsed['blocks']:
    #             required_keys = {'key', 'text', 'type', 'depth', 'inlineStyleRanges', 'entityRanges', 'data'}
    #             if not all(key in block for key in required_keys):
    #                 logger.error(f"Invalid block structure in description: {block}")
    #                 raise ValidationError(f"Each block must contain all required keys: {required_keys}")
    #             if not isinstance(block['text'], str):
    #                 logger.error(f"Block 'text' must be a string: {block}")
    #                 raise ValidationError("Block 'text' must be a string")
    #             if not isinstance(block['inlineStyleRanges'], list):
    #                 logger.error(f"Block 'inlineStyleRanges' must be a list: {block}")
    #                 raise ValidationError("Block 'inlineStyleRanges' must be a list")
    #             if not isinstance(block['entityRanges'], list):
    #                 logger.error(f"Block 'entityRanges' must be a list: {block}")
    #                 raise ValidationError("Block 'entityRanges' must be a list")
    #             if not isinstance(block['data'], dict):
    #                 logger.error(f"Block 'data' must be an object: {block}")
    #                 raise ValidationError("Block 'data' must be an object")
            
    #         logger.info("Description validation passed")
    #         return value
    #     except json.JSONDecodeError as e:
    #         logger.error(f"Description JSON parsing failed: {value}, error: {str(e)}")
    #         raise ValidationError("Description must be a valid JSON string")
        

    # def validate_description(self, value):
    #     if not value:
    #         # Return a valid empty Draft.js JSON string
    #         return json.dumps({
    #             "blocks": [{"key": "empty", "text": "", "type": "unstyled", "depth": 0, "inlineStyleRanges": [], "entityRanges": [], "data": {}}],
    #             "entityMap": {}
    #         })
    #     try:
    #         parsed = json.loads(value)
    #         if not isinstance(parsed, dict) or not parsed.get('blocks') or not isinstance(parsed['blocks'], list) or not parsed.get('entityMap'):
    #             raise ValidationError("Description must be a valid Draft.js RawDraftContentState JSON string")
    #         return value
    #     except json.JSONDecodeError:
    #         raise ValidationError("Description must be a valid JSON string")

    def to_internal_value(self, data):
        # Clean up learning_outcomes and prerequisites
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
        
        # Ensure learning_outcomes is a flat array of strings
        if 'learning_outcomes' in representation:
            representation['learning_outcomes'] = self.flatten_array(representation['learning_outcomes'])
        
        # Ensure prerequisites is a flat array of strings
        if 'prerequisites' in representation:
            representation['prerequisites'] = self.flatten_array(representation['prerequisites'])
        
        return representation
    
    def flatten_array(self, data):
        """Convert nested arrays into a flat array of strings"""
        flat_list = []
        for item in data:
            if isinstance(item, list):
                flat_list.extend([str(i) for i in item])
            elif isinstance(item, str):
                try:
                    # Handle case where string might be JSON-encoded array
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
        if 'slug' not in validated_data or not validated_data['slug']:
            title = validated_data.get('title', '')
            validated_data['slug'] = slugify(title)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'title' in validated_data:
            validated_data['slug'] = slugify(validated_data['title'])
        return super().update(instance, validated_data)

    class Meta:
        model = Course
        fields = [  # your fields here...
            'id', 'title', 'learning_outcomes', 'prerequisites', 'slug', 'code', 'description',
            'short_description', 'category', 'category_id', 'level', 'status', 'duration', 'price',
            'discount_price', 'currency', 'thumbnail', 'faq_count', 'faqs', 'created_at', 'updated_at',
            'created_by', 'created_by_username', 'completion_hours', 'discount_price', 'current_price',
            'modules', 'resources', 'course_instructors', 'certificate_settings', 'scorm_settings',
            'total_enrollments'
        ]



# class CourseSerializer(serializers.ModelSerializer):
#     faq_count = serializers.IntegerField(read_only=True)
#     faqs = FAQSerializer(many=True, read_only=True)
#     total_enrollments = serializers.IntegerField(read_only=True)
#     resources = ResourceSerializer(many=True, read_only=True)
#     category = CategorySerializer(read_only=True)
#     category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
#     learning_outcomes = serializers.ListField(
#         child=serializers.CharField(max_length=200, allow_blank=True),
#         required=False,
#         default=list
#     )
#     prerequisites = serializers.ListField(
#         child=serializers.CharField(max_length=200, allow_blank=True),
#         required=False,
#         default=list
#     )
#     modules = ModuleSerializer(many=True, read_only=True)
#     resources = ResourceSerializer(many=True, read_only=True)
#     course_instructors = CourseInstructorSerializer(many=True, read_only=True)
#     certificate_settings = CertificateTemplateSerializer(read_only=True)
#     scorm_settings = SCORMxAPISettingsSerializer(read_only=True)
#     current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
#     created_by_username = serializers.CharField(source='created_by.username', read_only=True)

#     class Meta:
#         model = Course
#         fields = [
#             'id', 'title', 'learning_outcomes', 'prerequisites', 'slug', 'code', 'description', 'short_description', 'category', 'category_id',
#             'level', 'status', 'duration', 'price', 'discount_price', 'currency', 'thumbnail','faq_count','faqs',
#             'created_at', 'updated_at', 'created_by', 'created_by_username', 'completion_hours',
#             'current_price', 'learning_outcomes', 'prerequisites', 'modules', 'resources',
#             'course_instructors', 'certificate_settings', 'scorm_settings','total_enrollments',
#         ]

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

