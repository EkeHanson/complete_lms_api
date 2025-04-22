from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, CourseViewSet, ModuleViewSet, LessonViewSet,ResourceViewSet,
    EnrollmentView, CourseRatingView, LearningPathViewSet, CertificateView
)

# Initialize the router
router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'learning-paths', LearningPathViewSet)
router.register(r'courses/(?P<course_id>\d+)/resources', ResourceViewSet, basename='resource')

# Define nested routes for modules and lessons
urlpatterns = [
    # Include default router URLs
    path('', include(router.urls)),

    # path(
    #     'courses/<int:course_id>/resources/reorder/',
    #     ResourceViewSet.as_view({'post': 'reorder'}),
    #     name='resource-reorder'
    # ),

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
    path('enrollments/', EnrollmentView.as_view(), name='enrollments'),
    path('enrollments/course/<int:course_id>/', EnrollmentView.as_view(), name='enrollment-course'),
    path('ratings/', CourseRatingView.as_view(), name='ratings'),
    path('ratings/course/<int:course_id>/', CourseRatingView.as_view(), name='rating-course'),
    path('certificates/', CertificateView.as_view(), name='certificates'),
    path('certificates/course/<int:course_id>/', CertificateView.as_view(), name='certificate-course'),
]