from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg, Count, Sum  # Add Sum to imports
from courses.models import Enrollment, CourseRating
from .models import UserProgress, CourseAnalytics

@receiver(post_save, sender=Enrollment)
def update_course_analytics_enrollment(sender, instance, created, **kwargs):
    if created:
        analytics, _ = CourseAnalytics.objects.get_or_create(course=instance.course)
        analytics.total_enrollments = Enrollment.objects.filter(course=instance.course, is_active=True).count()
        analytics.save()

@receiver(post_delete, sender=Enrollment)
def update_course_analytics_enrollment_delete(sender, instance, **kwargs):
    analytics, _ = CourseAnalytics.objects.get_or_create(course=instance.course)
    analytics.total_enrollments = Enrollment.objects.filter(course=instance.course, is_active=True).count()
    analytics.save()

@receiver(post_save, sender=UserProgress)
def update_course_analytics_progress(sender, instance, **kwargs):
    if instance.is_completed:
        course = instance.enrollment.course
        analytics, _ = CourseAnalytics.objects.get_or_create(course=course)
        total_enrollments = Enrollment.objects.filter(course=course, is_active=True).count()
        completed_enrollments = Enrollment.objects.filter(
            course=course, is_active=True, completed_at__isnull=False
        ).count()
        analytics.completion_rate = (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0
        analytics.total_time_spent = UserProgress.objects.filter(
            enrollment__course=course
        ).aggregate(total=Sum('time_spent'))['total'] or 0
        analytics.save()

@receiver(post_save, sender=CourseRating)
def update_course_analytics_rating(sender, instance, **kwargs):
    analytics, _ = CourseAnalytics.objects.get_or_create(course=instance.course)
    avg_rating = CourseRating.objects.filter(course=instance.course).aggregate(avg=Avg('rating'))['avg']
    analytics.average_rating = avg_rating or 0
    analytics.save()