# # analytics/admin.py
# from django.contrib import admin
# from .models import ProgressTracking, CourseAnalytics, UserActivityLog

# @admin.register(CourseAnalytics)
# class CourseAnalyticsAdmin(admin.ModelAdmin):
#     list_display = ('course', 'total_enrollments', 'completion_rate', 'average_rating', 'last_updated')
#     list_filter = ('course__category',)
#     search_fields = ('course__title',)

# @admin.register(ProgressTracking)
# class ProgressTrackingAdmin(admin.ModelAdmin):
#     list_display = ('enrollment', 'lesson', 'completed_at', 'score')
#     list_filter = ('enrollment__course', 'completed_at')
#     search_fields = ('enrollment__user__username', 'lesson__title')

# @admin.register(UserActivityLog)
# class UserActivityLogAdmin(admin.ModelAdmin):
#     list_display = ('user', 'activity_type', 'course', 'timestamp')
#     list_filter = ('activity_type', 'timestamp')
#     search_fields = ('user__username', 'course__title')

# # analytics/serializers.py
# from rest_framework import serializers
# from .models import CourseAnalytics, ProgressTracking, UserActivityLog
# from courses.models import Course, Enrollment

# class CourseAnalyticsSerializer(serializers.ModelSerializer):
#     course_title = serializers.CharField(source='course.title')
#     category = serializers.CharField(source='course.category.name')
    
#     class Meta:
#         model = CourseAnalytics
#         fields = [
#             'course_id', 'course_title', 'category', 'total_enrollments', 
#             'completion_rate', 'average_rating', 'average_time_to_complete', 
#             'last_updated'
#         ]

# class ProgressTrackingSerializer(serializers.ModelSerializer):
#     lesson_title = serializers.CharField(source='lesson.title')
#     module_title = serializers.CharField(source='lesson.module.title')
    
#     class Meta:
#         model = ProgressTracking
#         fields = [
#             'id', 'lesson_id', 'lesson_title', 'module_title', 'completed_at', 
#             'time_spent', 'score'
#         ]

# class UserActivityLogSerializer(serializers.ModelSerializer):
#     course_title = serializers.CharField(source='course.title', allow_null=True)
#     lesson_title = serializers.CharField(source='lesson.title', allow_null=True)
    
#     class Meta:
#         model = UserActivityLog
#         fields = [
#             'id', 'activity_type', 'course_id', 'course_title', 'lesson_id', 
#             'lesson_title', 'timestamp', 'metadata'
#         ]
