from django.urls import path
from .views import (
    JobApplicationListCreateView,    JobApplicationDetailView,    JobApplicationBulkDeleteView,    SoftDeletedJobApplicationsView,
    RecoverSoftDeletedJobApplicationsView,    PermanentDeleteJobApplicationsView,
    ScheduleListCreateView,    ScheduleDetailView,    ScheduleBulkDeleteView,    SoftDeletedSchedulesView,
    RecoverSoftDeletedSchedulesView,    PermanentDeleteSchedulesView,JobApplicationWithSchedulesView,
    ResumeParseView,    JobApplicationsByRequisitionView,    PublishedJobRequisitionsWithShortlistedApplicationsView,
    ResumeScreeningView,
)
app_name = 'job_applications'

 # Job Application Endpoints
urlpatterns = [
    path('applications/', JobApplicationListCreateView.as_view(), name='application-list-create'),
    path('applications/<str:id>/', JobApplicationDetailView.as_view(), name='application-detail'),
    path('applications/bulk-delete/applications/', JobApplicationBulkDeleteView.as_view(), name='application-bulk-delete'),
    path('applications/deleted/soft_deleted/', SoftDeletedJobApplicationsView.as_view(), name='soft-deleted-applications'),
    path('applications/recover/application/', RecoverSoftDeletedJobApplicationsView.as_view(), name='recover-applications'),
    path('applications/permanent-delete/application/', PermanentDeleteJobApplicationsView.as_view(), name='permanent-delete-applications'),
    path('applications/job-requisitions/<str:job_requisition_id>/applications/', JobApplicationsByRequisitionView.as_view(), name='job-applications-by-requisition'),


    path('applications/code/<str:code>/email/<str:email>/with-schedules/schedules/', JobApplicationWithSchedulesView.as_view(), name='application-with-schedules'),

    # path('applications/<str:id>/with-schedules/schedules/', JobApplicationWithSchedulesView.as_view(), name='application-with-schedules'),


    path('applications/parse-resume/autofil/', ResumeParseView.as_view(), name='resume-parse'),

    
    path('requisitions/<str:job_requisition_id>/screen-resumes/', ResumeScreeningView.as_view(), name='resume-screening'),
    path('published-requisitions-with-shortlisted/', PublishedJobRequisitionsWithShortlistedApplicationsView.as_view(), name='published-requisitions-with-shortlisted'),


    # Schedule Endpoints
    path('schedules/', ScheduleListCreateView.as_view(), name='schedule-list-create'),
    path('schedules/bulk-delete/', ScheduleBulkDeleteView.as_view(), name='schedule-bulk-delete'),
    path('schedules/<str:id>/', ScheduleDetailView.as_view(), name='schedule-detail'),
    path('schedules/deleted/soft_deleted/', SoftDeletedSchedulesView.as_view(), name='soft-deleted-schedules'),
    path('schedules/recover/schedule/', RecoverSoftDeletedSchedulesView.as_view(), name='recover-schedules'),
    path('schedules/permanent-delete/schedule/', PermanentDeleteSchedulesView.as_view(), name='permanent-delete-schedules'),
    
    # Resume Parsing and Screening
    path('parse-resume/', ResumeParseView.as_view(), name='parse-resume'),
    path('requisitions/<uuid:job_requisition_id>/screen-resumes/', ResumeScreeningView.as_view(), name='screen-resumes'),
    
    # Published Requisitions with Shortlisted Applications
    path('published-requisitions-with-shortlisted/', PublishedJobRequisitionsWithShortlistedApplicationsView.as_view(), name='published-requisitions-with-shortlisted'),
]