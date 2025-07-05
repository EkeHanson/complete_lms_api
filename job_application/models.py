
from django.db import models
from django.utils.text import slugify
from core.models import Tenant
from talent_engine.models import JobRequisition
import uuid
import logging
from datetime import date


logger = logging.getLogger('job_applications')

class ActiveApplicationsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class JobApplication(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('hired', 'Hired'),
    ]
    SCREENING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]

    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='job_applications')
    job_requisition = models.ForeignKey(JobRequisition, on_delete=models.CASCADE, related_name='applications')
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    phone = models.CharField(max_length=20)
    qualification = models.TextField(max_length=255)
    experience = models.TextField(max_length=255)
    knowledge_skill = models.TextField(blank=True, null=True)
    cover_letter = models.TextField(blank=True, null=True)
    resume_status = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    screening_status = models.CharField(max_length=20, choices=SCREENING_STATUS_CHOICES, default='pending')
    screening_score = models.FloatField(null=True, blank=True)
    employment_gaps = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=50, blank=True, null=True, default='Website')
    documents = models.JSONField(default=list, blank=True)
    is_deleted = models.BooleanField(default=False)
    applied_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    date_of_birth = models.DateField(blank=True, null=True)

    objects = models.Manager()
    active_objects = ActiveApplicationsManager()

    class Meta:
        db_table = 'job_applications_job_application'
        unique_together = ('tenant', 'job_requisition', 'email')

    def __str__(self):
        return f"{self.full_name} - {self.job_requisition.title} ({self.tenant.name})"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        if not self.id:
            prefix = self.tenant.name[:3].upper()
            latest = JobApplication.objects.filter(id__startswith=prefix).aggregate(models.Max('id'))['id__max']
            number = int(latest.split('-')[1]) + 1 if latest else 1
            self.id = f"{prefix}-{number:04d}"
        super().save(*args, **kwargs)
        if is_new:
            self.job_requisition.num_of_applications += 1
            self.job_requisition.save()


    # def save(self, *args, **kwargs):
    #     is_new = not self.pk
    #     if not self.id:
    #         # Get first 3 letters of tenant name
    #         tenant_prefix = self.tenant.name[:3].upper()
    #         # Get first 2 letters of model name ("Job Application" -> "JA")
    #         model_prefix = "JA"
            
    #         # Find latest ID with this pattern
    #         pattern = f"{tenant_prefix}-{model_prefix}-"
    #         latest = JobApplication.objects.filter(id__startswith=pattern).order_by('-id').first()
            
    #         if latest:
    #             # Extract the number part and increment
    #             try:
    #                 last_number = int(latest.id.split('-')[-1])
    #                 number = last_number + 1
    #             except (ValueError, IndexError):
    #                 number = 1
    #         else:
    #             number = 1
                
    #         self.id = f"{pattern}{number:04d}"

    #     # Validate date of birth is in the past
    #     if self.date_of_birth and self.date_of_birth > date.today():
    #         raise ValueError("_birthDate of birth cannot be in the future")
            
    #     super().save(*args, **kwargs)
        
    #     if is_new:
    #         self.job_requisition.num_of_applications += 1
    #         self.job_requisition.save()

    def soft_delete(self):
        self.is_deleted = True
        self.save()
        logger.info(f"JobApplication {self.id} soft-deleted for tenant {self.tenant.schema_name}")

    def restore(self):
        self.is_deleted = False
        self.save()
        logger.info(f"JobApplication {self.id} restored for tenant {self.tenant.schema_name}")


class Schedule(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='schedules')
    job_application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='schedules')
    interview_date_time = models.DateTimeField()
    meeting_mode = models.CharField(max_length=20, choices=[('Virtual', 'Virtual'), ('Physical', 'Physical')])
    meeting_link = models.URLField(max_length=255, blank=True, null=True)
    interview_address = models.TextField(max_length=255, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    cancellation_reason = models.TextField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)




    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active_objects = models.Manager()

    class ActiveManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_deleted=False)

    active_objects = ActiveManager()

    class Meta:
        db_table = 'job_applications_schedule'
        unique_together = ('tenant', 'job_application', 'interview_date_time')

    def __str__(self):
        return f"Schedule for {self.job_application.full_name} - {self.job_application.job_requisition.title} ({self.interview_date_time})"

    def save(self, *args, **kwargs):
        if not self.id:
            prefix = self.tenant.name[:3].upper()
            latest = Schedule.objects.filter(id__startswith=prefix).aggregate(models.Max('id'))['id__max']
            number = int(latest.split('-')[1]) + 1 if latest else 1
            self.id = f"{prefix}-{number:04d}"
        super().save(*args, **kwargs)


    # def save(self, *args, **kwargs):
    #     if not self.id:
    #         # Get first 3 letters of tenant name
    #         tenant_prefix = self.tenant.name[:3].upper()
    #         # Get first 2 letters of model name ("Schedule" -> "SC")
    #         model_prefix = "SC"
            
    #         # Find latest ID with this pattern
    #         pattern = f"{tenant_prefix}-{model_prefix}-"
    #         latest = Schedule.objects.filter(id__startswith=pattern).order_by('-id').first()
            
    #         if latest:
    #             # Extract the number part and increment
    #             try:
    #                 last_number = int(latest.id.split('-')[-1])
    #                 number = last_number + 1
    #             except (ValueError, IndexError):
    #                 number = 1
    #         else:
    #             number = 1
                
    #         self.id = f"{pattern}{number:04d}"

    #     super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_deleted = True
        self.save()
        logger.info(f"Schedule {self.id} soft-deleted for tenant {self.tenant.schema_name}")

    def restore(self):
        self.is_deleted = False
        self.save()
        logger.info(f"Schedule {self.id} restored for tenant {self.tenant.schema_name}")