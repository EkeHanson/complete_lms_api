from django.urls import path
from .views import UserProgressView, QuizResultView, CourseAnalyticsView, DashboardAnalyticsView

urlpatterns = [
    path('progress/', UserProgressView.as_view(), name='user-progress'),
    path('progress/course/<int:course_id>/', UserProgressView.as_view(), name='user-progress-course'),
    path('quiz-results/', QuizResultView.as_view(), name='quiz-results'),
    path('quiz-results/course/<int:course_id>/', QuizResultView.as_view(), name='quiz-results-course'),
    path('course-analytics/', CourseAnalyticsView.as_view(), name='course-analytics'),
    path('course-analytics/<int:course_id>/', CourseAnalyticsView.as_view(), name='course-analytics-detail'),
    path('dashboard/', DashboardAnalyticsView.as_view(), name='dashboard-analytics'),
]