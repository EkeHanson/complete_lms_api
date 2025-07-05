from rest_framework import serializers
from .models import JobRequisition
from users.models import CustomUser

class JobRequisitionSerializer(serializers.ModelSerializer):
    requested_by = serializers.SerializerMethodField()
    tenant = serializers.SlugRelatedField(
        slug_field='schema_name',
        read_only=True
    )
    tenant_domain = serializers.SerializerMethodField()

    class Meta:
        model = JobRequisition
        fields = [
            'id', 'tenant', 'tenant_domain', 'title', 'unique_link', 'status', 'requested_by', 'role', 'company_name',
            'job_type', 'location_type', 'company_address', 'salary_range',
            'job_description', 'number_of_candidates', 'qualification_requirement',
            'experience_requirement', 'knowledge_requirement', 'reason', 'job_requisition_code', 'job_application_code',
            'deadline_date', 'start_date', 'responsibilities', 'documents_required',
            'compliance_checklist', 'advert_banner', 'requested_date', 'publish_status',
            'is_deleted', 'created_at', 'updated_at', 'num_of_applications', 'job_location'
        ]
        read_only_fields = ['id', 'tenant', 'tenant_domain', 'unique_link', 'requested_date', 'is_deleted', 'created_at', 'updated_at']

    def get_requested_by(self, obj):
        if obj.requested_by:
            return {
                'email': obj.requested_by.email,
                'first_name': obj.requested_by.first_name or '',
                'last_name': obj.requested_by.last_name or '',
                'job_role': obj.requested_by.job_role or '',
            }
        return None

    def get_tenant_domain(self, obj):
        primary_domain = obj.tenant.domain_set.filter(is_primary=True).first()
        return primary_domain.domain if primary_domain else None

    def validate(self, data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            data['requested_by'] = request.user

        if data.get('publish_status', False):
            required_fields = [
                'title', 'company_name', 'job_description', 'deadline_date', 'responsibilities',
                'documents_required', 'compliance_checklist'
            ]
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError({field: f'{field.replace("_", " ").title()} is required to publish.'})
            if data.get('location_type') == 'on_site' and not data.get('company_address'):
                raise serializers.ValidationError({'company_address': 'Company Address is required for on-site jobs.'})
            if not data.get('responsibilities') or not any(r.strip() for r in data.get('responsibilities')):
                raise serializers.ValidationError({'responsibilities': 'At least one responsibility is required.'})

        return data