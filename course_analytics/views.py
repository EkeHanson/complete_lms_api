from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from .models import UserProgress, QuizResult, CourseAnalytics
from .serializers import UserProgressSerializer, QuizResultSerializer, CourseAnalyticsSerializer
from courses.models import Course, Enrollment
from django.db.models import Count, Avg, Sum
from rest_framework.pagination import PageNumberPagination

class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class UserProgressView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get(self, request, course_id=None):
        if course_id:
            enrollments = Enrollment.objects.filter(user=request.user, course_id=course_id, is_active=True)
            if not enrollments.exists():
                return Response({"error": "Not enrolled in this course"}, status=status.HTTP_403_FORBIDDEN)
            progress = UserProgress.objects.filter(enrollment__in=enrollments)
        else:
            enrollments = Enrollment.objects.filter(user=request.user, is_active=True)
            progress = UserProgress.objects.filter(enrollment__in=enrollments)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(progress, request)
        serializer = UserProgressSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

class QuizResultView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get(self, request, course_id=None):
        if course_id:
            enrollments = Enrollment.objects.filter(user=request.user, course_id=course_id, is_active=True)
            if not enrollments.exists():
                return Response({"error": "Not enrolled in this course"}, status=status.HTTP_403_FORBIDDEN)
            results = QuizResult.objects.filter(enrollment__in=enrollments)
        else:
            enrollments = Enrollment.objects.filter(user=request.user, is_active=True)
            results = QuizResult.objects.filter(enrollment__in=enrollments)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(results, request)
        serializer = QuizResultSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

class CourseAnalyticsView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsPagination

    def get(self, request, course_id=None):
        if course_id:
            try:
                analytics = CourseAnalytics.objects.get(course_id=course_id)
                serializer = CourseAnalyticsSerializer(analytics)
                return Response(serializer.data)
            except CourseAnalytics.DoesNotExist:
                return Response({"error": "Analytics not found for this course"}, status=status.HTTP_404_NOT_FOUND)
        else:
            analytics = CourseAnalytics.objects.all()
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(analytics, request)
            serializer = CourseAnalyticsSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

class DashboardAnalyticsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        data = {
            'total_courses': Course.objects.count(),
            'total_enrollments': Enrollment.objects.count(),
            'average_completion_rate': CourseAnalytics.objects.aggregate(avg=Avg('completion_rate'))['avg'] or 0,
            'average_rating': CourseAnalytics.objects.aggregate(avg=Avg('average_rating'))['avg'] or 0,
            'top_courses': CourseAnalytics.objects.order_by('-total_enrollments')[:5].values(
                'course__title', 'total_enrollments', 'completion_rate'
            ),
            'recent_enrollments': Enrollment.objects.order_by('-enrolled_at')[:5].values(
                'user__username', 'course__title', 'enrolled_at'
            ),
        }
        return Response(data)