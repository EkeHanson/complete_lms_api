from rest_framework import serializers
from .models import UserProgress, QuizResult, CourseAnalytics
from courses.models import Course, Module, Lesson, Enrollment
from django.db.models import Avg, Count

class UserProgressSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    module_title = serializers.CharField(source='lesson.module.title', read_only=True)
    course_title = serializers.CharField(source='enrollment.course.title', read_only=True)

    class Meta:
        model = UserProgress
        fields = ['id', 'course_title', 'module_title', 'lesson_title', 'is_completed', 'time_spent', 'last_accessed', 'completion_date']

class QuizResultSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    course_title = serializers.CharField(source='enrollment.course.title', read_only=True)

    class Meta:
        model = QuizResult
        fields = ['id', 'course_title', 'lesson_title', 'score', 'total_questions', 'correct_answers', 'attempt_date', 'time_taken']

class CourseAnalyticsSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    category = serializers.CharField(source='course.category.name', read_only=True)
    average_completion_time = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    average_quiz_score = serializers.SerializerMethodField()

    class Meta:
        model = CourseAnalytics
        fields = [
            'course_title', 'category', 'total_enrollments', 'completion_rate',
            'average_rating', 'total_time_spent', 'last_updated',
            'average_completion_time', 'student_count', 'average_quiz_score'
        ]

    def get_average_completion_time(self, obj):
        progress = UserProgress.objects.filter(
            enrollment__course=obj.course, is_completed=True
        ).aggregate(avg_time=Avg('time_spent'))
        return progress['avg_time'] or 0

    def get_student_count(self, obj):
        return Enrollment.objects.filter(course=obj.course, is_active=True).count()

    def get_average_quiz_score(self, obj):
        quiz_results = QuizResult.objects.filter(enrollment__course=obj.course)
        avg_score = quiz_results.aggregate(avg_score=Avg('score'))['avg_score']
        return avg_score or 0