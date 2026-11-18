from django.urls import path
from . import views

urlpatterns = [
    path('', views.api),
    path('api/employers/', views.employers),
    path('api/candidates/', views.candidates),
    path('api/jobs/', views.jobs),
    path('api/jobs/<int:job_id>/', views.job_detail),
    path('api/jobs/<int:job_id>/apply/', views.apply),
    path('api/applications/', views.applications),
    path('api/employer/applications/', views.employer_applications),
    path('api/applications/<int:application_id>/status/', views.update_application_status),
    path('api/resumes/', views.resumes),
    path('api/resumes/<int:resume_id>/', views.resume_download),
    path('api/notifications/', views.notifications),
]
