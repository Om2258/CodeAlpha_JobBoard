from django.contrib import admin
from .models import Application, Candidate, Company, Job, Notification, Resume

admin.site.register((Company, Candidate, Resume, Job, Application, Notification))

# Register your models here.
