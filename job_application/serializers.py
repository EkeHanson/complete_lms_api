
from rest_framework import serializers
from .models import JobApplication, Schedule
from talent_engine.models import JobRequisition
import logging
from django.conf import settings
from django.utils import timezone
import os
import uuid
from django.core.validators import URLValidator
from .utils import parse_resume, screen_resume, extract_resume_fields

logger = logging.getLogger('job_applications')


class DocumentSerializer(serializers.Serializer):
    document_type = serializers.CharField(max_length=50)
    file = serializers.FileField(write_only=True)
    file_url = serializers.SerializerMethodField(read_only=True)
    uploaded_at = serializers.DateTimeField(read_only=True, default=timezone.now)

    def get_file_url(self, obj):
        file_url = obj.get('file_url', None)
        if file_url:
            return file_url
        return None

    def validate_file(self, value):
        allowed_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Invalid file type: {value.content_type}. Only PDF and Word (.doc, .docx) files are allowed."
            )
        max_size = 50 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(f"File size exceeds 50 MB limit.")
        return value

    def validate_document_type(self, value):
        if value.lower() == 'resume':
            return value
        job_requisition = self.context.get('job_requisition')
        if not job_requisition:
            raise serializers.ValidationError("Job requisition context is missing.")
        documents_required = job_requisition.documents_required or []
        if documents_required and value not in documents_required:
            raise serializers.ValidationError(
                f"Invalid document type: {value}. Must be one of {documents_required}."
            )
        return value

class JobApplicationSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, required=False)
    job_requisition_id = serializers.CharField(source='job_requisition.id', read_only=True)
    job_requisition_title = serializers.CharField(source='job_requisition.title', read_only=True)
    tenant_schema = serializers.CharField(source='tenant.schema_name', read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id', 'tenant', 'tenant_schema', 'job_requisition', 'job_requisition_id',
            'job_requisition_title', 'date_of_birth',
            'full_name', 'email', 'phone', 'qualification', 'experience', 'screening_status', 'screening_score',
            'knowledge_skill', 'cover_letter', 'resume_status', 'employment_gaps', 'status', 'source',
            'documents', 'is_deleted', 'applied_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'tenant_schema', 'job_requisition_id', 'job_requisition_title',
            'is_deleted', 'applied_at', 'created_at', 'updated_at'
        ]

    def validate(self, data):
        job_requisition = data.get('job_requisition')
        if not job_requisition:
            raise serializers.ValidationError("Job requisition is required.")
        if not job_requisition.publish_status:
            raise serializers.ValidationError("This job is not published.")
        documents_required = job_requisition.documents_required or []
        documents_data = data.get('documents', [])
        if documents_required:
            provided_types = {doc['document_type'] for doc in documents_data}
            missing_docs = [doc for doc in documents_required if doc not in provided_types]
            if missing_docs:
                raise serializers.ValidationError(
                    f"Missing required documents: {', '.join(missing_docs)}."
                )
        return data

    def create(self, validated_data):
        documents_data = validated_data.pop('documents', [])
        tenant = self.context['request'].tenant
        validated_data['tenant'] = tenant
        logger.debug(f"Creating application for tenant: {tenant.schema_name}, job_requisition: {validated_data['job_requisition'].title}")

        documents = []
        for doc_data in documents_data:
            file = doc_data['file']
            folder_path = os.path.join('application_documents', timezone.now().strftime('%Y/%m/%d'))
            full_folder_path = os.path.join(settings.MEDIA_ROOT, folder_path)
            os.makedirs(full_folder_path, exist_ok=True)
            file_extension = os.path.splitext(file.name)[1]
            filename = f"{uuid.uuid4()}{file_extension}"
            upload_path = os.path.join(folder_path, filename).replace('\\', '/')
            full_upload_path = os.path.join(settings.MEDIA_ROOT, upload_path)
            logger.debug(f"Saving file to full_upload_path: {full_upload_path}")

            try:
                with open(full_upload_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
                logger.debug(f"File saved successfully: {full_upload_path}")
            except Exception as e:
                logger.error(f"Failed to save file {full_upload_path}: {str(e)}")
                raise serializers.ValidationError(f"Failed to save file: {str(e)}")

            file_url = f"/media/{upload_path.lstrip('/')}"
            logger.debug(f"Constructed file_url: {file_url}")

            # Parse resume for other fields if document_type is resume or cv
            if doc_data['document_type'].lower() in ['resume', 'cv']:
                resume_text = parse_resume(upload_path)
                if resume_text:
                    resume_data = extract_resume_fields(resume_text)
                    validated_data['full_name'] = resume_data.get('full_name', validated_data.get('full_name', ''))
                    validated_data['email'] = resume_data.get('email', validated_data.get('email', ''))
                    validated_data['phone'] = resume_data.get('phone', validated_data.get('phone', ''))
                    validated_data['qualification'] = resume_data.get('qualification', validated_data.get('qualification', ''))
                    validated_data['experience'] = "; ".join(resume_data.get('experience', [])) or validated_data.get('experience', '')
                    validated_data['knowledge_skill'] = resume_data.get('knowledge_skill', validated_data.get('knowledge_skill', ''))

            documents.append({
                'document_type': doc_data['document_type'],
                'file_path': upload_path,
                'file_url': file_url,
                'uploaded_at': timezone.now().isoformat()
            })
            if doc_data['document_type'].lower() in ['resume', 'cv']:
                validated_data['resume_status'] = True

        validated_data['documents'] = documents
        logger.debug(f"Documents to be saved: {documents}")
        application = JobApplication.objects.create(**validated_data)
        logger.info(f"Application created: {application.id} for {application.full_name}")
        return application

    def get_fields(self):
        fields = super().get_fields()
        if 'documents' in fields:
            fields['documents'].child.context.update({'job_requisition': self.context.get('job_requisition')})
        return fields

class ScheduleSerializer(serializers.ModelSerializer):
    job_application_id = serializers.CharField(source='job_application.id', read_only=True)
    tenant_schema = serializers.CharField(source='tenant.schema_name', read_only=True)
    candidate_name = serializers.CharField(source='job_application.full_name', read_only=True)
    job_requisition_title = serializers.CharField(source='job_application.job_requisition.title', read_only=True)

    class Meta:
        model = Schedule
        fields = [
            'id', 'tenant', 'tenant_schema', 'job_application', 'job_application_id',
            'candidate_name', 'job_requisition_title', 'interview_date_time',
            'meeting_mode', 'meeting_link', 'interview_address', 'message',
            'status', 'cancellation_reason', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'tenant_schema', 'job_application_id', 'candidate_name', 'job_requisition_title', 'is_deleted', 'created_at', 'updated_at']

    def validate(self, data):
        #logger.debug(f"Validating schedule data: {data}, instance: {self.instance}")
        job_application = data.get('job_application', getattr(self.instance, 'job_application', None))
        if not job_application:
            logger.error("Job application is required but not provided or found on instance")
            raise serializers.ValidationError("Job application is required.")
        if job_application.status != 'shortlisted':
            #logger.warning(f"Invalid job application status: {job_application.status} for job_application {job_application.id}")
            raise serializers.ValidationError("Schedules can only be created for shortlisted applicants.")
        if data.get('meeting_mode') == 'Virtual' and not data.get('meeting_link'):
            #logger.warning("Missing meeting link for virtual interview")
            raise serializers.ValidationError("Meeting link is required for virtual interviews.")
        if data.get('meeting_mode') == 'Virtual' and data.get('meeting_link'):
            validate_url = URLValidator()
            try:
                validate_url(data['meeting_link'])
            except serializers.ValidationError:
                logger.error(f"Invalid meeting link URL: {data['meeting_link']}")
                raise serializers.ValidationError("Invalid meeting link URL.")
        if data.get('meeting_mode') == 'Physical' and not data.get('interview_address'):
            logger.warning("Missing interview address for physical interview")
            raise serializers.ValidationError("Interview address is required for physical interviews.")
        if data.get('status') == 'cancelled' and not data.get('cancellation_reason'):
            logger.warning("Missing cancellation reason for cancelled schedule")
            raise serializers.ValidationError("Cancellation reason is required for cancelled schedules.")
        if data.get('interview_date_time') and data['interview_date_time'] <= timezone.now():
            logger.warning(f"Interview date in the past: {data['interview_date_time']}")
            raise serializers.ValidationError("Interview date and time must be in the future.")
        return data

    def create(self, validated_data):
        tenant = self.context['request'].tenant
        validated_data['tenant'] = tenant
        #logger.debug(f"Creating schedule for tenant: {tenant.schema_name}, application: {validated_data['job_application'].id}")
        schedule = Schedule.objects.create(**validated_data)
        #logger.info(f"Schedule created: {schedule.id} for {schedule.job_application.full_name}")
        return schedule

    def update(self, instance, validated_data):
        #logger.debug(f"Updating schedule {instance.id} with data: {validated_data}")
        if validated_data.get('status') == 'cancelled' and instance.status != 'cancelled' and not validated_data.get('cancellation_reason'):
            logger.warning(f"Missing cancellation reason for cancelling schedule {instance.id}")
            raise serializers.ValidationError("Cancellation reason is required when cancelling a schedule.")
        if validated_data.get('status') != 'cancelled':
            validated_data['cancellation_reason'] = None
        return super().update(instance, validated_data)