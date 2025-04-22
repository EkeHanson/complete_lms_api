from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from courses.models import Course, Module, Lesson, Enrollment

class UserProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='user_progress')
    is_completed = models.BooleanField(default=False)
    time_spent = models.PositiveIntegerField(default=0, help_text="Time spent in seconds")
    last_accessed = models.DateTimeField(auto_now=True)
    completion_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['enrollment', 'lesson']
        indexes = [
            models.Index(fields=['enrollment', 'lesson']),
            models.Index(fields=['last_accessed']),
        ]

    def __str__(self):
        return f"{self.enrollment.user} - {self.lesson.title} Progress"

class QuizResult(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='quiz_results')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='quiz_results', limit_choices_to={'lesson_type': 'quiz'})
    score = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    total_questions = models.PositiveIntegerField()
    correct_answers = models.PositiveIntegerField()
    attempt_date = models.DateTimeField(auto_now_add=True)
    time_taken = models.PositiveIntegerField(default=0, help_text="Time taken in seconds")

    class Meta:
        indexes = [
            models.Index(fields=['enrollment', 'lesson']),
            models.Index(fields=['attempt_date']),
        ]

    def __str__(self):
        return f"{self.enrollment.user} - {self.lesson.title} Quiz Result"

class CourseAnalytics(models.Model):
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='analytics')
    total_enrollments = models.PositiveIntegerField(default=0)
    completion_rate = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    average_rating = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(5.0)])
    total_time_spent = models.PositiveIntegerField(default=0, help_text="Total time spent by all users in seconds")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['course']),
            models.Index(fields=['last_updated']),
        ]

    def __str__(self):
        return f"Analytics for {self.course.title}"