from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (BadgeViewSet, UserBadgeViewSet,UserPointsViewSet,FAQViewSet,
    CategoryViewSet, CourseViewSet, ModuleViewSet, LessonViewSet,ResourceViewSet,
    EnrollmentViewSet, CourseRatingView, LearningPathViewSet, CertificateView
)

# Initialize the router
router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'learning-paths', LearningPathViewSet)
router.register(r'courses/(?P<course_id>\d+)/resources', ResourceViewSet, basename='resource')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')

router.register(r'badges', BadgeViewSet)
router.register(r'user-points', UserPointsViewSet)
router.register(r'user-badges', UserBadgeViewSet)

# Define nested routes for modules and lessons
urlpatterns = [
    # Include default router URLs
    path('', include(router.urls)),

    # Add this to your urlpatterns
    path('courses/<int:course_id>/faqs/',FAQViewSet.as_view({'get': 'list', 'post': 'create'}),name='faq-list'),
    path('courses/<int:course_id>/faqs/<int:pk>/',FAQViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'}),
        name='faq-detail'),
    path('courses/<int:course_id>/faqs/reorder/',FAQViewSet.as_view({'post': 'reorder'}),name='faq-reorder'),
    # path(
    #     'courses/<int:course_id>/resources/reorder/',
    #     ResourceViewSet.as_view({'post': 'reorder'}),
    #     name='resource-reorder'
    # ),
    path('courses/most_popular/',CourseViewSet.as_view({'get': 'most_popular'}),
        name='course-most-popular'),
    path('courses/least_popular/',CourseViewSet.as_view({'get': 'least_popular'}),
        name='course-least-popular'),

    # Nested routes for modules under courses
    path(
        'courses/<int:course_id>/modules/',
        ModuleViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='module-list'
    ),
    path(
        'courses/<int:course_id>/modules/<int:module_id>/',
        ModuleViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'}),
        name='module-detail'
    ),
    # Nested routes for lessons under modules (if needed)
    path(
        'courses/<int:course_id>/modules/<int:module_id>/lessons/',
        LessonViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='lesson-list'
    ),
    path(
        'courses/<int:course_id>/modules/<int:module_id>/lessons/<int:pk>/',
        LessonViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'}),
        name='lesson-detail'
    ),
    # Existing non-nested routes
    path('ratings/', CourseRatingView.as_view(), name='ratings'),
    path('ratings/course/<int:course_id>/', CourseRatingView.as_view(), name='rating-course'),
    path('certificates/', CertificateView.as_view(), name='certificates'),
    path('certificates/course/<int:course_id>/', CertificateView.as_view(), name='certificate-course'),
    
    # Specific enrollment endpoints
    path('enrollments/course/<int:course_id>/', EnrollmentViewSet.as_view({'get': 'list'}), name='course-enrollments'),
    path('enrollments/course/<int:course_id>/bulk/', EnrollmentViewSet.as_view({'post': 'create'}), name='bulk-enroll'),

]