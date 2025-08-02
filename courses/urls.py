from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (AssignmentViewSet,FeedbackViewSet,CartViewSet, WishlistViewSet,
    GradeViewSet,
    CategoryViewSet, CourseViewSet, ModuleViewSet, LessonViewSet, AnalyticsViewSet,
    EnrollmentViewSet, CertificateTemplateView, CourseProgressViewSet, LessonCompletionViewSet,
    InstructorViewSet, QuizViewSet
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'courses', CourseViewSet, basename='courses')
router.register(r'assignments', AssignmentViewSet, basename='assignments')
router.register(r'feedback', FeedbackViewSet, basename='feedback')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'wishlist', WishlistViewSet, basename='wishlist')
router.register(r'grades', GradeViewSet, basename='grades')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')
router.register(r'progress', CourseProgressViewSet, basename='progress')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollments')
router.register(r'lesson-completion', LessonCompletionViewSet, basename='lesson-completion')
router.register(r'instructors', InstructorViewSet, basename='instructor')
router.register(r'quizzes', QuizViewSet, basename='quizzes')

urlpatterns = [
    path('', include(router.urls)),
    
    path('courses/most_popular/', CourseViewSet.as_view({'get': 'most_popular'}), name='course-most-popular'),
    path('courses/least_popular/', CourseViewSet.as_view({'get': 'least_popular'}), name='course-least-popular'),
    path('courses/<int:course_id>/modules/', ModuleViewSet.as_view({'get': 'list', 'post': 'create'}), name='module-list'),
    path('courses/<int:course_id>/modules/<int:pk>/', ModuleViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='module-detail'),
    path('courses/<int:course_id>/modules/<int:module_id>/lessons/', LessonViewSet.as_view({'get': 'list', 'post': 'create'}), name='lesson-list'),
    path('courses/<int:course_id>/modules/<int:module_id>/lessons/<int:pk>/', LessonViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='lesson-detail'),
    
    path('certificates/course/<int:course_id>/template/', CertificateTemplateView.as_view(), name='certificate-template'),

    path('enrollments/course/<int:course_id>/', EnrollmentViewSet.as_view({'get': 'list'}), name='course-enrollments'),
    path('enrollments/course/<int:course_id>/enroll/', EnrollmentViewSet.as_view({'post': 'enroll_to_course'}), name='enroll-to-course'),
    path('enrollments/course/<int:course_id>/bulk/', EnrollmentViewSet.as_view({'post': 'bulk_enroll'}), name='bulk-enroll'),
    path('enrollments/user/<int:user_id>/', EnrollmentViewSet.as_view({'get': 'user_enrollments'}), name='user-enrollments'),
    path('enrollments/all/', EnrollmentViewSet.as_view({'get': 'all_enrollments'}), name='all-enrollments'),

    path('progress/update/', CourseProgressViewSet.as_view({'patch': 'update_progress'}), name='progress-update'),
]





