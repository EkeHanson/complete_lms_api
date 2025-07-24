from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
import json
from users.models import CustomUser

def course_thumbnail_path(instance, filename):
    return f'courses/{instance.slug}/thumbnails/{filename}'

def certificate_logo_path(instance, filename):
    return f'courses/{instance.course.slug}/certificates/logos/{filename}'

def certificate_signature_path(instance, filename):
    return f'courses/{instance.course.slug}/certificates/signatures/{filename}'

# def resource_file_path(instance, filename):
#     return f'courses/{instance.module.course.slug}/resources/{filename}'
def resource_file_path(instance, filename):
    """
    Generate a file path for resource uploads based on the course slug.
    """
    return f'courses/{instance.course.slug}/resources/{filename}'

def scorm_package_path(instance, filename):
    return f'courses/{instance.course.slug}/scorm_packages/{filename}'



class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_categories'
    )

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
        ('GBP', 'Pound (£)'),
        ('JPY', 'Yen (¥)'),
        ('AUD', 'Australian Dollar (A$)'),
        ('CAD', 'Canadian Dollar (C$)'),
        ('CHF', 'Swiss Franc (CHF)'),
        ('CNY', 'Yuan (¥)'),
        ('INR', 'Indian Rupee (₹)'),
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
    learning_outcomes = models.JSONField(default=list)
    prerequisites = models.JSONField(default=list)
    completion_hours = models.PositiveIntegerField(default=0, help_text="Estimated hours to complete the course")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    # def save(self, *args, **kwargs):
    #     if not self.slug:
    #         self.slug = slugify(self.title)
    #     super().save(*args, **kwargs)
    
    def save(self, *args, **kwargs):
        # Ensure learning_outcomes is stored as a flat array
        if isinstance(self.learning_outcomes, list):
            self.learning_outcomes = [str(item) for item in self.learning_outcomes]
        elif isinstance(self.learning_outcomes, str):
            try:
                parsed = json.loads(self.learning_outcomes)
                self.learning_outcomes = [str(item) for item in parsed] if isinstance(parsed, list) else [self.learning_outcomes]
            except json.JSONDecodeError:
                self.learning_outcomes = [self.learning_outcomes]
        
        # Ensure prerequisites is stored as a flat array
        if isinstance(self.prerequisites, list):
            self.prerequisites = [str(item) for item in self.prerequisites]
        elif isinstance(self.prerequisites, str):
            try:
                parsed = json.loads(self.prerequisites)
                self.prerequisites = [str(item) for item in parsed] if isinstance(parsed, list) else [self.prerequisites]
            except json.JSONDecodeError:
                self.prerequisites = [self.prerequisites]
                
        super().save(*args, **kwargs)
    
    @property
    def current_price(self):
        return self.discount_price if self.discount_price else self.price



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
        ('link', 'Link'),  # Add 'link' as a valid choice
    ]
    
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES, default='video')
    duration = models.CharField(max_length=20, help_text="Duration in minutes", default= "1 hour")
    content_url = models.URLField(blank=True)
    content_file = models.FileField(upload_to='lessons/files/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']
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
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='instructor_profile')
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

class Badge(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='badges/', null=True, blank=True)
    criteria = models.JSONField(default=dict, help_text="Criteria for earning the badge, e.g., {'courses_completed': 5}")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class UserPoints(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)
    points = models.PositiveIntegerField(default=0)
    activity_type = models.CharField(max_length=50, choices=[
        ('course_completion', 'Course Completion'),
        ('module_completion', 'Module Completion'),
        ('lesson_completion', 'Lesson Completion'),
        ('quiz_score', 'Quiz Score'),
        ('discussion', 'Discussion Participation'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'course', 'activity_type']

    def __str__(self):
        return f"{self.user} - {self.points} points"

class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    awarded_at = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ['user', 'badge', 'course']

    def __str__(self):
        return f"{self.user} - {self.badge.title}"

class FAQ(models.Model):
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='faqs'
    )
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return f"{self.course.title} - {self.question[:50]}..."
    

    