import json
from functools import wraps
from pathlib import Path

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Application, Candidate, Company, Job, Notification, Resume

MAX_RESUME_SIZE = 5 * 1024 * 1024
ALLOWED_RESUME_SUFFIXES = {".pdf", ".doc", ".docx"}


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required."}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def read_json(request):
    try:
        return json.loads(request.body or "{}"), None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse({"error": "Request body must be valid JSON."}, status=400)


def api(request):
    return JsonResponse({
        "service": "CodeAlpha Job Board",
        "endpoints": [
            "/api/employers/", "/api/candidates/", "/api/jobs/",
            "/api/resumes/", "/api/jobs/<id>/apply/",
            "/api/applications/", "/api/employer/applications/",
            "/api/notifications/",
        ],
    })


@api_login_required
@require_http_methods(["POST"])
def employers(request):
    data, error = read_json(request)
    if error:
        return error
    try:
        company = Company.objects.create(
            owner=request.user,
            name=data["company_name"],
            website=data.get("website", ""),
        )
        return JsonResponse({"id": company.id, "company_name": company.name}, status=201)
    except (KeyError, TypeError, ValueError, IntegrityError) as exc:
        return JsonResponse({"error": f"Invalid employer profile: {exc}"}, status=400)


@api_login_required
@require_http_methods(["POST"])
def candidates(request):
    data, error = read_json(request)
    if error:
        return error
    try:
        candidate, created = Candidate.objects.get_or_create(
            user=request.user, defaults={"phone": data.get("phone", "")}
        )
        if not created and "phone" in data:
            candidate.phone = data["phone"]
            candidate.save(update_fields=["phone"])
        return JsonResponse({"id": candidate.id, "created": created}, status=201 if created else 200)
    except (TypeError, ValueError) as exc:
        return JsonResponse({"error": f"Invalid candidate profile: {exc}"}, status=400)


@api_login_required
@require_http_methods(["POST"])
def resumes(request):
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "Upload a resume in the 'file' field."}, status=400)
    suffix = Path(uploaded.name).suffix.lower()
    if suffix not in ALLOWED_RESUME_SUFFIXES:
        return JsonResponse({"error": "Resume must be a PDF, DOC, or DOCX file."}, status=400)
    if uploaded.size > MAX_RESUME_SIZE:
        return JsonResponse({"error": "Resume must be 5 MB or smaller."}, status=400)
    try:
        candidate = Candidate.objects.get(user=request.user)
    except Candidate.DoesNotExist:
        return JsonResponse({"error": "Create a candidate profile before uploading a resume."}, status=403)
    resume = Resume.objects.create(
        candidate=candidate, file=uploaded, original_filename=Path(uploaded.name).name
    )
    return JsonResponse({
        "id": resume.id,
        "filename": resume.original_filename,
        "uploaded_at": resume.uploaded_at,
    }, status=201)


@api_login_required
@require_http_methods(["GET"])
def resume_download(request, resume_id):
    try:
        resume = Resume.objects.select_related("candidate__user").get(pk=resume_id)
    except Resume.DoesNotExist:
        return JsonResponse({"error": "Resume not found."}, status=404)
    is_candidate = resume.candidate.user_id == request.user.id
    is_employer = Application.objects.filter(
        resume=resume, job__company__owner=request.user
    ).exists()
    if not (is_candidate or is_employer):
        return JsonResponse({"error": "You cannot access this resume."}, status=403)
    try:
        response = FileResponse(resume.file.open("rb"), as_attachment=True, filename=resume.original_filename)
    except OSError:
        return JsonResponse({"error": "Resume file is unavailable."}, status=404)
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["GET", "POST"])
def jobs(request):
    if request.method == "GET":
        query = request.GET.get("q", "")
        location = request.GET.get("location", "")
        category = request.GET.get("category", "")
        qs = Job.objects.filter(is_active=True).select_related("company")
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(category__icontains=query)
                | Q(company__name__icontains=query)
            )
        if location:
            qs = qs.filter(location__icontains=location)
        if category:
            qs = qs.filter(category__icontains=category)
        return JsonResponse([{
            "id": job.id,
            "title": job.title,
            "employer": job.company.name,
            "location": job.location,
            "category": job.category,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "created_at": job.created_at,
        } for job in qs], safe=False)
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Employer login required."}, status=403)
    data, error = read_json(request)
    if error:
        return error
    try:
        company = Company.objects.get(owner=request.user)
        job = Job.objects.create(
            company=company,
            title=data["title"],
            description=data["description"],
            location=data["location"],
            category=data["category"],
            salary_min=data.get("salary_min"),
            salary_max=data.get("salary_max"),
        )
        return JsonResponse({"id": job.id, "title": job.title}, status=201)
    except Company.DoesNotExist:
        return JsonResponse({"error": "Create an employer profile before posting a job."}, status=403)
    except (KeyError, TypeError, ValueError, IntegrityError) as exc:
        return JsonResponse({"error": f"Invalid job listing: {exc}"}, status=400)


@require_http_methods(["GET"])
def job_detail(request, job_id):
    try:
        job = Job.objects.select_related("company").get(pk=job_id, is_active=True)
    except Job.DoesNotExist:
        return JsonResponse({"error": "Job not found."}, status=404)
    return JsonResponse({
        "id": job.id,
        "title": job.title,
        "employer": job.company.name,
        "description": job.description,
        "location": job.location,
        "category": job.category,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "created_at": job.created_at,
    })


@api_login_required
@require_http_methods(["POST"])
def apply(request, job_id):
    data, error = read_json(request)
    if error:
        return error
    try:
        candidate = Candidate.objects.get(user=request.user)
        job = Job.objects.select_related("company").get(pk=job_id, is_active=True)
        resume = Resume.objects.get(pk=data["resume_id"], candidate=candidate)
        with transaction.atomic():
            application = Application.objects.create(
                job=job,
                candidate=candidate,
                applicant=request.user,
                resume=resume,
                cover_letter=data.get("cover_letter", ""),
            )
            Notification.objects.create(
                user=job.company.owner,
                application=application,
                message=f"{candidate} applied for {job.title}.",
            )
        return JsonResponse({
            "id": application.id,
            "job": job.title,
            "status": application.status,
        }, status=201)
    except Candidate.DoesNotExist:
        return JsonResponse({"error": "Create a candidate profile before applying."}, status=403)
    except Job.DoesNotExist:
        return JsonResponse({"error": "Job not found or no longer active."}, status=404)
    except Resume.DoesNotExist:
        return JsonResponse({"error": "Resume not found for this candidate."}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "You have already applied for this job."}, status=409)
    except (KeyError, TypeError, ValueError) as exc:
        return JsonResponse({"error": f"Invalid application: {exc}"}, status=400)


@api_login_required
@require_http_methods(["GET"])
def applications(request):
    try:
        candidate = Candidate.objects.get(user=request.user)
    except Candidate.DoesNotExist:
        return JsonResponse({"error": "Candidate profile not found."}, status=403)
    qs = Application.objects.filter(candidate=candidate).select_related("job__company", "resume")
    return JsonResponse([{
        "id": application.id,
        "job": application.job.title,
        "employer": application.job.company.name,
        "status": application.status,
        "resume": application.resume.original_filename if application.resume else None,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
    } for application in qs], safe=False)


@api_login_required
@require_http_methods(["GET"])
def employer_applications(request):
    qs = Application.objects.filter(job__company__owner=request.user).select_related(
        "job", "candidate__user", "resume"
    )
    return JsonResponse([{
        "id": application.id,
        "job": application.job.title,
        "candidate": application.candidate.user.username if application.candidate else application.applicant.username,
        "resume": application.resume.original_filename if application.resume else None,
        "status": application.status,
        "created_at": application.created_at,
    } for application in qs], safe=False)


@api_login_required
@require_http_methods(["POST"])
def update_application_status(request, application_id):
    data, error = read_json(request)
    if error:
        return error
    status = data.get("status")
    if status not in Application.Status.values:
        return JsonResponse({"error": "Unknown application status."}, status=400)
    try:
        with transaction.atomic():
            application = Application.objects.select_for_update().select_related(
                "job__company", "candidate__user"
            ).get(pk=application_id)
            if application.job.company.owner_id != request.user.id:
                return JsonResponse({"error": "You cannot update this application."}, status=403)
            application.status = status
            application.save(update_fields=["status", "updated_at"])
            Notification.objects.create(
                user=application.candidate.user if application.candidate else application.applicant,
                application=application,
                message=f"Your application for {application.job.title} is now {status}.",
            )
        return JsonResponse({"id": application.id, "status": application.status})
    except Application.DoesNotExist:
        return JsonResponse({"error": "Application not found."}, status=404)


@api_login_required
@require_http_methods(["GET", "POST"])
def notifications(request):
    if request.method == "GET":
        return JsonResponse(list(request.user.job_notifications.order_by("-created_at").values(
            "id", "message", "application_id", "created_at", "read_at"
        )), safe=False)
    data, error = read_json(request)
    if error:
        return error
    notification_id = data.get("id")
    updated = request.user.job_notifications.filter(pk=notification_id, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    if not updated:
        return JsonResponse({"error": "Notification not found or already read."}, status=404)
    return JsonResponse({"id": notification_id, "read": True})
