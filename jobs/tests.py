import json
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import Application, Candidate, Company, Job, Notification, Resume


class JobBoardTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.TemporaryDirectory()
        cls._media_settings = override_settings(MEDIA_ROOT=cls._media_dir.name)
        cls._media_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_settings.disable()
        cls._media_dir.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.employer_user = User.objects.create_user(username="employer", password="test-pass")
        self.candidate_user = User.objects.create_user(username="candidate", password="test-pass")
        self.employer = Company.objects.create(name="TechCo", owner=self.employer_user)
        self.candidate = Candidate.objects.create(user=self.candidate_user)
        self.job = Job.objects.create(
            company=self.employer,
            title="Python Developer",
            description="Build APIs",
            location="Pune",
            category="Engineering",
        )
        self.resume = Resume.objects.create(
            candidate=self.candidate,
            file="resumes/sample.pdf",
            original_filename="sample.pdf",
        )

    def test_job_search_with_filters(self):
        response = self.client.get("/api/jobs/?q=Python&location=Pune&category=Engineering")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Python Developer", response.content.decode())

    def test_job_detail(self):
        response = self.client.get(f"/api/jobs/{self.job.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("TechCo", response.content.decode())

    def test_resume_upload(self):
        self.client.force_login(self.candidate_user)
        response = self.client.post("/api/resumes/", {
            "file": SimpleUploadedFile("resume.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Resume.objects.filter(candidate=self.candidate).count(), 2)

    def test_candidate_application_notifies_employer(self):
        self.client.force_login(self.candidate_user)
        response = self.client.post(
            f"/api/jobs/{self.job.id}/apply/",
            data=json.dumps({"resume_id": self.resume.id, "cover_letter": "Interested"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        application = Application.objects.get()
        self.assertEqual(application.status, Application.Status.SUBMITTED)
        self.assertEqual(Notification.objects.filter(user=self.employer_user).count(), 1)

    def test_duplicate_application_is_rejected(self):
        Application.objects.create(
            job=self.job, applicant=self.candidate_user, candidate=self.candidate, resume=self.resume
        )
        self.client.force_login(self.candidate_user)
        response = self.client.post(
            f"/api/jobs/{self.job.id}/apply/",
            data=json.dumps({"resume_id": self.resume.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_employer_status_update_notifies_candidate(self):
        application = Application.objects.create(
            job=self.job, applicant=self.candidate_user, candidate=self.candidate, resume=self.resume
        )
        self.client.force_login(self.employer_user)
        response = self.client.post(
            f"/api/applications/{application.id}/status/",
            data=json.dumps({"status": Application.Status.INTERVIEW}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.INTERVIEW)
        self.assertEqual(Notification.objects.filter(user=self.candidate_user).count(), 1)

    def test_other_employer_cannot_update_application(self):
        application = Application.objects.create(
            job=self.job, applicant=self.candidate_user, candidate=self.candidate, resume=self.resume
        )
        other_user = User.objects.create_user(username="other", password="test-pass")
        Company.objects.create(name="Other", owner=other_user)
        self.client.force_login(other_user)
        response = self.client.post(
            f"/api/applications/{application.id}/status/",
            data=json.dumps({"status": Application.Status.REJECTED}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
