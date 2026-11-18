# CodeAlpha Job Board Platform

Django and SQLite REST API for CodeAlpha Backend Development Task 4.

## Features

- Employer/company profiles and job listings
- Candidate profiles and PDF/DOC/DOCX resume uploads (up to 5 MB)
- Job search by keywords, location, and category
- Candidate applications with duplicate prevention and application tracking
- Employer-only application status updates
- In-app notifications for new applications and status changes
- Django admin dashboard

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Set `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=0` before deploying. Authenticated write endpoints use Django session authentication and CSRF protection. Uploaded resumes are stored under `media/`; configure private storage and access controls before deploying real candidate documents.

## API

- `POST /api/employers/` — create employer profile (`company_name`, optional `website`)
- `POST /api/candidates/` — create/update candidate profile (`phone`)
- `POST /api/jobs/` — employer posts a listing (`title`, `description`, `location`, `category`, optional salary bounds)
- `GET /api/jobs/?q=python&location=Pune&category=Engineering` — search active jobs
- `GET /api/jobs/<id>/` — job details
- `POST /api/resumes/` — candidate resume multipart upload using `file`
- `GET /api/resumes/<id>/` — download a resume as its owner or an employer with an application
- `POST /api/jobs/<id>/apply/` — apply with `resume_id` and optional `cover_letter`
- `GET /api/applications/` — candidate application history
- `GET /api/employer/applications/` — applications for the signed-in employer
- `POST /api/applications/<id>/status/` — employer updates status (`submitted`, `reviewing`, `interview`, `rejected`, `hired`)
- `GET|POST /api/notifications/` — list notifications or mark one read (`id`)

Run tests with `python manage.py test`.
