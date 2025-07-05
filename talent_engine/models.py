from django.db import models
from django.db.models import Max
from django.utils.text import slugify
from users.models import CustomUser
from core.models import Tenant
import uuid
import logging

logger = logging.getLogger('talent_engine')

class ActiveRequisitionsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class JobRequisition(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('pending', 'Pending'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
    ]
    ROLE_CHOICES = [
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    ]
    JOB_TYPE_CHOICES = [
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('contract', 'Contract'),
        ('freelance', 'Freelance'),
        ('internship', 'Internship'),
    ]
    LOCATION_TYPE_CHOICES = [
        ('on_site', 'On-site'),
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
    ]

    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
  
    job_requisition_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    job_application_code  = models.CharField(max_length=50, unique=True, blank=True, null=True)


    num_of_applications = models.IntegerField(default=0, help_text="Number of successful (hired) applications")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='talent_requisitions')
    title = models.CharField(max_length=255)
    unique_link = models.CharField(max_length=255, unique=True, blank=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rejected')
    requested_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='talent_requisitions')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    company_name = models.CharField(max_length=255, blank=True, null=True)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='full_time')
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES, default='on_site')
    company_address = models.TextField(blank=True, null=True)
    job_location = models.TextField(blank=True, null=True)
    salary_range = models.CharField(max_length=100, blank=True, null=True)
    job_description = models.TextField(blank=True, null=True)
    number_of_candidates = models.IntegerField(blank=True, null=True)
    qualification_requirement = models.TextField(blank=True, null=True)
    experience_requirement = models.TextField(blank=True, null=True)
    knowledge_requirement = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    deadline_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    responsibilities = models.JSONField(default=list, blank=True)
    documents_required = models.JSONField(default=list, blank=True)
    compliance_checklist = models.JSONField(default=list, blank=True)
    advert_banner = models.ImageField(upload_to='advert_banners/', blank=True, null=True)
    requested_date = models.DateField(auto_now_add=True)
    publish_status = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active_objects = ActiveRequisitionsManager()

    class Meta:
        db_table = 'talent_engine_job_requisition'

    def __str__(self):
        return f"{self.title} ({self.tenant.schema_name})"
        
    def save(self, *args, **kwargs):
        is_new = self._state.adding  # check if object is new

        # Generate ID
        if not self.id:
            prefix = self.tenant.name[:3].upper()
            latest = JobRequisition.objects.filter(id__startswith=prefix).aggregate(Max('id'))['id__max']
            if latest:
                try:
                    number = int(latest.split('-')[1]) + 1
                except (IndexError, ValueError):
                    number = 1
            else:
                number = 1
            self.id = f"{prefix}-{number:04d}"

        # Generate unique_link
        if not self.unique_link:
            base_slug = slugify(f"{self.title}")
            short_uuid = str(uuid.uuid4())[:8]
            slug = f"{self.tenant.schema_name}-{base_slug}-{short_uuid}"
            counter = 1
            original_slug = slug
            while JobRequisition.objects.filter(unique_link=slug).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1
            self.unique_link = slug

        # Generate job_requisition_code
        if not self.job_requisition_code:
            code_prefix = self.tenant.name[:2].upper()
            latest_code = JobRequisition.objects.filter(job_requisition_code__startswith=f"{code_prefix}-JR-") \
                .order_by('-job_requisition_code').first()

            if latest_code and latest_code.job_requisition_code:
                try:
                    last_number = int(latest_code.job_requisition_code.split('-')[-1])
                    new_number = last_number + 1
                except (IndexError, ValueError):
                    new_number = 1
            else:
                new_number = 1

            self.job_requisition_code = f"{code_prefix}-JR-{new_number:04d}"

        # Generate job_application_code
        if not self.job_application_code:
            code_prefix = self.tenant.name[:2].upper()
            latest_app_code = JobRequisition.objects.filter(job_application_code__startswith=f"{code_prefix}-JA-") \
                .order_by('-job_application_code').first()

            if latest_app_code and latest_app_code.job_application_code:
                try:
                    last_number = int(latest_app_code.job_application_code.split('-')[-1])
                    new_number = last_number + 1
                except (IndexError, ValueError):
                    new_number = 1
            else:
                new_number = 1

            self.job_application_code = f"{code_prefix}-JA-{new_number:04d}"

        super().save(*args, **kwargs)


    def soft_delete(self):
        self.is_deleted = True
        self.save()
        logger.info(f"JobRequisition {self.id} soft-deleted for tenant {self.tenant.schema_name}")

    def restore(self):
        self.is_deleted = False
        self.save()
        logger.info(f"JobRequisition {self.id} restored for tenant {self.tenant.schema_name}")
