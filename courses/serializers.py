from rest_framework import serializers
from .models import (Category, Course , Module, Lesson,Badge,UserPoints,UserBadge,FAQ,Feedback,Analytics,
    Resource, Instructor, CourseInstructor, CertificateTemplate,UserBadge,Assignment,Cart, Wishlist,
    SCORMxAPISettings, LearningPath, Enrollment, Certificate, CourseRating, Grade)
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.core.exceptions import ValidationError
import json
import logging
from django.utils.text import slugify
from users.models import CustomUser
from utils.supabase import upload_to_supabase
logger = logging.getLogger('course')
import uuid
from utils.storage import get_storage_service



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
        fields = ['id', 'module', 'title', 'lesson_type', 'content_url', 'content_file', 'duration', 'order', 'is_published']
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
#     instructor_id = serializers.PrimaryKeyRelatedField(
#         queryset=CustomUser.objects.all(),
#         source='instructor.user',
#         write_only=True
#     )
#     module_titles = serializers.SerializerMethodField()
#     modules = serializers.PrimaryKeyRelatedField(
#         queryset=Module.objects.all(),
#         many=True,
#         required=False
#     )

#     class Meta:
#         model = CourseInstructor
#         fields = ['id', 'instructor', 'instructor_id', 'assignment_type', 'is_active', 'module_titles', 'modules']

#     def get_module_titles(self, obj):
#         return [module.title for module in obj.modules.all()]

#     def validate(self, data):
#         assignment_type = data.get('assignment_type', 'all')
#         modules = data.get('modules', None)
#         course = self.context.get('course')
#         if assignment_type == 'specific':
#             if not modules or len(modules) == 0:
#                 raise serializers.ValidationError("Modules must be provided for specific assignment type")
#         return data

#     def create(self, validated_data):
#         course = self.context.get('course')
#         assignment_type = validated_data.get('assignment_type', 'all')
#         instructor = validated_data['instructor']

#         # If assignment_type is 'all', assign all modules of the course
#         if assignment_type == 'all':
#             validated_data['modules'] = list(course.modules.all())

#         # If assignment_type is 'specific', modules must be provided (already validated above)
#         course_instructor = super().create(validated_data)
#         if validated_data.get('modules'):
#             course_instructor.modules.set(validated_data['modules'])
#         return course_instructor

#     def update(self, instance, validated_data):
#         user = validated_data.pop('instructor', {}).get('user')
#         if user:
#             instructor, created = Instructor.objects.get_or_create(
#                 user=user,
#                 defaults={'bio': 'Auto-created instructor profile', 'is_active': True}
#             )
#             validated_data['instructor'] = instructor
#         modules = validated_data.pop('modules', None)
#         instance = super().update(instance, validated_data)
#         if modules is not None:
#             instance.modules.set(modules)
#         return instance
    

# class CourseInstructorSerializer(serializers.ModelSerializer):
#     instructor = InstructorSerializer(read_only=True)
#     instructor_id = serializers.PrimaryKeyRelatedField(
#         queryset=CustomUser.objects.all(),
#         source='instructor.user',
#         write_only=True
#     )
#     module_titles = serializers.SerializerMethodField()
#     modules = serializers.PrimaryKeyRelatedField(
#         queryset=Module.objects.all(),
#         many=True,
#         required=False
#     )

#     class Meta:
#         model = CourseInstructor
#         fields = ['id', 'instructor', 'instructor_id', 'assignment_type', 'is_active', 'module_titles', 'modules']

#     def get_module_titles(self, obj):
#         return [module.title for module in obj.modules.all()]

#     def validate(self, data):
#         assignment_type = data.get('assignment_type', 'all')
#         modules = data.get('modules', None)
#         course = self.context.get('course')
#         if assignment_type == 'specific' and (not modules or len(modules) == 0):
#             raise serializers.ValidationError("Modules must be provided for specific assignment type")
#         return data

#     def create(self, validated_data):
#         # Extract course from context
#         course = self.context.get('course')
#         if not course:
#             raise serializers.ValidationError("Course context is required")

#         # Extract instructor_id (maps to instructor.user)
#         instructor_user = validated_data.pop('instructor.user', None)
#         if not instructor_user:
#             raise serializers.ValidationError("instructor_id is required")

#         # Get or create Instructor instance for the user
#         instructor, created = Instructor.objects.get_or_create(
#             user=instructor_user,
#             defaults={'bio': 'Auto-created instructor profile', 'is_active': True}
#         )

#         # Extract assignment_type and modules
#         assignment_type = validated_data.pop('assignment_type', 'all')
#         modules = validated_data.pop('modules', [])

#         # Create CourseInstructor instance
#         course_instructor = CourseInstructor.objects.create(
#             course=course,
#             instructor=instructor,
#             assignment_type=assignment_type,
#             is_active=validated_data.get('is_active', True)
#         )

#         # Assign modules based on assignment_type
#         if assignment_type == 'all':
#             course_instructor.modules.set(course.modules.all())
#         elif modules:
#             course_instructor.modules.set(modules)

#         return course_instructor

#     def update(self, instance, validated_data):
#         # Handle instructor.user (instructor_id) if provided
#         instructor_user = validated_data.pop('instructor.user', None)
#         if instructor_user:
#             instructor, created = Instructor.objects.get_or_create(
#                 user=instructor_user,
#                 defaults={'bio': 'Auto-created instructor profile', 'is_active': True}
#             )
#             validated_data['instructor'] = instructor

#         # Handle modules
#         modules = validated_data.pop('modules', None)
#         if modules is not None:
#             instance.modules.set(modules)
#         elif validated_data.get('assignment_type') == 'all':
#             instance.modules.set(instance.course.modules.all())

#         return super().update(instance, validated_data)   


class CourseInstructorSerializer(serializers.ModelSerializer):
    instructor = InstructorSerializer(read_only=True)
    instructor_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
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
        fields = [
            'id', 'instructor', 'instructor_id', 'assignment_type',
            'is_active', 'module_titles', 'modules'
        ]

    def get_module_titles(self, obj):
        return [module.title for module in obj.modules.all()]

    def validate(self, data):
        assignment_type = data.get('assignment_type', 'all')
        modules = data.get('modules', None)
        if assignment_type == 'specific':
            if not modules or len(modules) == 0:
                raise serializers.ValidationError(
                    "Modules must be provided for specific assignment type"
                )
        return data



    def create(self, validated_data):
        course = self.context.get('course')
        user = validated_data.pop('instructor_id')

        # Get or create Instructor
        instructor, _ = Instructor.objects.get_or_create(
            user=user,
            defaults={'bio': 'Auto-created instructor profile', 'is_active': True}
        )
        validated_data['instructor'] = instructor

        assignment_type = validated_data.get('assignment_type', 'all')

        # Handle modules separately
        modules = validated_data.pop('modules', [])

        if assignment_type == 'all':
            modules = list(course.modules.all())

        # First create the CourseInstructor object (without modules)
        course_instructor = CourseInstructor.objects.create(
            course=course,
            **validated_data
        )

        # Then assign modules
        if modules:
            course_instructor.modules.set(modules)

        return course_instructor



    def update(self, instance, validated_data):
        user = validated_data.pop('instructor_id', None)
        if user:
            instructor, _ = Instructor.objects.get_or_create(
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
        if instance.thumbnail:
            storage_service = get_storage_service()
            representation['thumbnail'] = storage_service.get_public_url(instance.thumbnail)
        
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
            # Delete old file if exists
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



    # def create(self, validated_data):
    #     if 'slug' not in validated_data or not validated_data['slug']:
    #         title = validated_data.get('title', '')
    #         validated_data['slug'] = slugify(title)
    #     return super().create(validated_data)

    # def update(self, instance, validated_data):
    #     if 'title' in validated_data:
    #         validated_data['slug'] = slugify(validated_data['title'])
    #     return super().update(instance, validated_data)

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
    course = serializers.SlugRelatedField(slug_field='title', read_only=True)
    class Meta:
        model = Assignment
        fields = ['id', 'title', 'course', 'due_date', 'status', 'grade', 'feedback', 'type']

class FeedbackSerializer(serializers.ModelSerializer):
    course = serializers.SlugRelatedField(slug_field='title', read_only=True, allow_null=True)
    user = serializers.SlugRelatedField(slug_field='email', read_only=True)
    class Meta:
        model = Feedback
        fields = ['id', 'user', 'course', 'type', 'content', 'rating', 'created_at']

class CartSerializer(serializers.ModelSerializer):
    course = serializers.SlugRelatedField(slug_field='title', read_only=True)
    class Meta:
        model = Cart
        fields = ['id', 'course', 'added_at']

class WishlistSerializer(serializers.ModelSerializer):
    course = serializers.SlugRelatedField(slug_field='title', read_only=True)
    class Meta:
        model = Wishlist
        fields = ['id', 'course', 'added_at']

class GradeSerializer(serializers.ModelSerializer):
    course = serializers.SlugRelatedField(slug_field='title', read_only=True)
    assignment = serializers.SlugRelatedField(slug_field='title', read_only=True, allow_null=True)
    class Meta:
        model = Grade
        fields = ['id', 'user', 'course', 'assignment', 'score', 'created_at']


class AnalyticsSerializer(serializers.ModelSerializer):
    course = serializers.SlugRelatedField(slug_field='title', read_only=True, allow_null=True)
    class Meta:
        model = Analytics
        fields = ['id', 'user', 'course', 'total_time_spent', 'weekly_time_spent', 'strengths', 'weaknesses', 'last_updated']