# Bank of Uganda Publication Management System

A role-based web application for managing Bank of Uganda research calls,
working-paper submissions, reviewer assignments, decisions, notifications, and
publication of approved papers.

The repository contains a Django JSON API and a dependency-free HTML, CSS, and
JavaScript frontend. `BOU_PMS_Mockup.html` is retained only as the original
design reference; it is not part of the running application.

## Contents

- [Features](#features)
- [Roles and workflow](#roles-and-workflow)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Local installation](#local-installation)
- [Configuration](#configuration)
- [Testing](#testing)
- [API overview](#api-overview)
- [Security](#security)
- [Production deployment](#production-deployment)
- [Maintenance and extension](#maintenance-and-extension)
- [Troubleshooting](#troubleshooting)

## Features

- Controlled account creation with one or more application roles
- Research-call drafting, publishing, deadline editing, and closure
- Approved research themes and departmental master data
- Multi-author submissions with internal and external affiliations
- Versioned PDF/DOCX abstracts, papers, and revisions
- Internal and external reviewer assignment with conflict-of-interest checks
- Editorial verification of reviewer assignments
- Research Officer verification of reviewer comments
- Editorial decisions, publication references, and public working-paper listing
- In-application notifications, audit logs, and workflow reports
- Responsive, role-specific workspaces without public account registration

## Roles and workflow

| Role | Primary responsibilities |
|---|---|
| System Admin | Accounts, roles, departments, themes, templates, repository oversight, and audit logs |
| Research Officer | Calls for papers, reviewer assignments, review verification, and reports |
| Editorial Board | Assignment verification, final decisions, references, and publication |
| Internal Reviewer | View assigned papers and submit recommendations/comments |
| External Reviewer | View assigned papers and submit recommendations/comments |
| Author | Create submissions, maintain authors, upload versions, and track decisions |
| Public visitor | Browse and download papers whose status is `published` |

The normal workflow is:

```text
Call published
    -> author submission
    -> reviewer assignment
    -> Editorial Board assignment verification
    -> reviewer comments
    -> Research Officer comment verification
    -> revision or next review stage
    -> Editorial Board decision
    -> public working-paper repository
```

Workflow state is stored on each submission using `status` and
`current_stage`. When adding transitions, update the validation and tracker in
`backend/submissions/views.py`, the relevant role UI in `frontend/app.js`, and
the regression tests together.

## Architecture

| Component | Technology | Local address | Responsibility |
|---|---|---|---|
| Frontend | HTML, CSS, vanilla JavaScript | `http://127.0.0.1:3000` | Role-specific SPA and public repository |
| Backend | Django 4.2 JSON API | `http://127.0.0.1:8000` | Authentication, authorization, workflow, persistence, and files |
| Database | SQLite for development | `backend/db.sqlite3` | Local application data |
| File storage | Django filesystem storage | `backend/uploads/` | Local templates and submission versions |

Authentication uses opaque random session tokens. Only token hashes are stored
in the database; the browser receives the raw value in an HTTP-only cookie.
Every protected backend endpoint performs its own role check, and submission
documents additionally use object-level access checks.

## Project structure

```text
PublicationManagementSystemBOU/
├── backend/
│   ├── accounts/       # users, roles, sessions, audit events
│   ├── masterdata/     # departments, research themes, templates
│   ├── submissions/    # calls, papers, authors, documents, publication
│   ├── reviews/        # reviewer assignments and comments
│   ├── notifications/  # in-application notifications
│   ├── bou_pms/        # Django settings, URLs, middleware, API helpers
│   ├── manage.py
│   └── requirements.txt
├── frontend/           # active browser application and assets
├── BOU_PMS_Mockup.html # design reference only
├── setup_local.py      # creates the venv, migrates, and seeds development data
├── run_all.py          # starts backend and frontend development servers
└── serve_frontend.py   # local static frontend server with security headers
```

Generated databases, uploads, virtual environments, caches, environment files,
and local tooling metadata are excluded by `.gitignore`.

## Local installation

### Prerequisites

- Python 3.10 or newer
- `pip` and Python virtual-environment support
- A modern browser

### One-time setup

From the repository root:

```bash
# macOS / Linux
python3 setup_local.py
```

```powershell
# Windows
python setup_local.py
```

The script creates `backend/venv`, installs `backend/requirements.txt`, applies
migrations, and seeds local roles, departments, and a development administrator.

To choose a safer development password before initial setup:

```bash
export DEV_ADMIN_PASSWORD='use-a-strong-local-password'
python3 setup_local.py
```

If not overridden, the isolated local-development account is:

```text
Email: admin@bou.or.ug
Password: Admin123!
```

Never use that credential outside an isolated development workstation. The seed
command refuses to run when `DJANGO_DEBUG=false`.

### Start the application

```bash
# macOS / Linux
python3 run_all.py
```

```powershell
# Windows
python run_all.py
```

Open `http://127.0.0.1:3000`. Stop both services with `Ctrl+C`.

## Configuration

Copy [.env.example](.env.example) as a reference for supported variables. The
application reads process environment variables directly and does not load a
`.env` file automatically; use your shell, IDE, container platform, or process
manager to provide them.

| Variable | Development default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `true` | Enables Django development behavior |
| `DJANGO_SECRET_KEY` | Local-only fallback | Django cryptographic secret; mandatory in production |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated accepted host names |
| `CORS_ALLOWED_ORIGINS` | Local frontend origins | Comma-separated trusted frontend origins |
| `AUTH_COOKIE_SECURE` | Follows production mode | Restricts the session cookie to HTTPS |
| `AUTH_COOKIE_SAMESITE` | `Lax` | Browser cross-site cookie policy |
| `SECURE_SSL_REDIRECT` | Follows production mode | Redirects HTTP requests to HTTPS |
| `SECURE_HSTS_SECONDS` | `0` locally, one year in production | HSTS duration |
| `SECURE_HSTS_PRELOAD` | `false` | Marks the site for HSTS preload eligibility |
| `DEV_ADMIN_PASSWORD` | Development password above | Initial local seed password only |

After model changes, create and apply migrations with:

```bash
backend/venv/bin/python backend/manage.py makemigrations
backend/venv/bin/python backend/manage.py migrate
```

Commit reviewed migration files. Never commit `backend/db.sqlite3`.

## Testing

Run the complete backend suite:

```bash
backend/venv/bin/python backend/manage.py test accounts masterdata submissions reviews notifications
```

Additional release checks:

```bash
backend/venv/bin/python backend/manage.py makemigrations --check --dry-run
backend/venv/bin/python -m pip check
git diff --check
```

Tests cover account administration, token revocation, hostile-origin rejection,
call management, publication visibility, reviewer object access, and restricted
notification creation. Add regression coverage whenever permissions or workflow
states change.

## API overview

All request and response bodies are JSON unless an endpoint accepts a file.
Protected endpoints use the `bou_session` HTTP-only cookie. Bearer tokens remain
supported for controlled automated tests and integrations.

| Area | Main endpoints | Access |
|---|---|---|
| Authentication | `/api/auth/login`, `/api/auth/logout`, `/api/auth/me` | Login/public; session endpoints/authenticated |
| Accounts | `/api/users`, `/api/users/<id>`, `/api/audit-logs` | Admin and selected workflow roles |
| Master data | `/api/departments`, `/api/themes`, `/api/templates` | Authenticated reads; Admin writes |
| Calls | `/api/calls`, `/api/calls/<id>`, `/api/calls/<id>/publish` | Authenticated reads; Research Officer writes |
| Submissions | `/api/submissions`, `/api/submissions/<id>`, `/api/submissions/<id>/status` | Object and role restricted |
| Documents | `/api/submissions/<id>/documents`, `/api/documents/<id>/download` | Author upload; object-restricted download |
| Reviews | `/api/review-assignments`, assignment/comment verification routes | Role and assignment restricted |
| Notifications | `/notifications/...` | User-scoped; arbitrary creation is Admin-only |
| Publications | `/api/publications` | Public read |

The authoritative route list is `backend/bou_pms/urls.py`. Keep frontend calls,
URL patterns, access decorators, and tests synchronized when changing an API.

## Security

Implemented application controls include:

- Server-side role and object authorization
- Revocable, expiring, hashed session tokens in HTTP-only cookies
- Trusted-origin validation for cookie-authenticated writes
- Login throttling and Django password validation
- Restricted credentialed CORS
- CSP, clickjacking, MIME-sniffing, referrer, and permissions headers
- Protected private-document and template downloads
- Upload limits plus extension, MIME, and basic file-signature validation
- Randomized stored submission filenames
- Audit records for authentication and important workflow actions
- Generic login errors that do not reveal whether an account exists

These controls reduce risk but do not constitute a permanent OWASP
certification. Security must be re-evaluated whenever functionality, hosting, or
dependencies change.

## Production deployment

The included servers are development tools. Production requires a supported
WSGI server, reverse proxy/load balancer, HTTPS certificate, managed secrets,
persistent database, and protected file storage.

Minimum production environment:

```bash
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<long-random-value-from-a-secret-manager>
DJANGO_ALLOWED_HOSTS=research.example.org
CORS_ALLOWED_ORIGINS=https://research.example.org
AUTH_COOKIE_SECURE=true
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_PRELOAD=true
```

Before release, run:

```bash
DJANGO_DEBUG=false \
DJANGO_SECRET_KEY='<long-random-secret>' \
DJANGO_ALLOWED_HOSTS=research.example.org \
CORS_ALLOWED_ORIGINS=https://research.example.org \
SECURE_HSTS_PRELOAD=true \
backend/venv/bin/python backend/manage.py check --deploy
```

Deployment and operational controls still required:

- Replace SQLite with a managed production database and test encrypted backups.
- Configure the reverse proxy to overwrite forwarded-protocol headers and serve
  the complete application over HTTPS before enabling HSTS/preload.
- Integrate organisation-managed MFA or SSO with the selected identity provider.
- Scan uploaded documents using an antivirus or content-disarm service.
- Send security and application logs to access-controlled central monitoring.
- Schedule removal of expired/revoked `accounts_authtoken` records.
- Establish key rotation, incident response, retention, recovery, and access
  review procedures.
- Run dependency scanning, SAST/DAST, and an independent penetration test before
  launch and after material changes.

## Maintenance and extension

When extending the system:

1. Enforce permissions in Django; frontend role checks are presentation only.
2. Apply object-level checks before returning submissions, reviews, files, or
   notifications.
3. Validate all state transitions and input on the server.
4. Use `record_audit` for privileged or consequential actions.
5. Use `create_notification` inside trusted workflow code rather than exposing
   broad notification creation to ordinary users.
6. Add a migration for model changes and regression tests for permission changes.
7. Update this README and `.env.example` when configuration or architecture changes.

Comments and docstrings intentionally explain security boundaries, business
rules, and surprising decisions. Avoid comments that merely restate obvious
syntax; they become stale and make the code harder to maintain.

## Troubleshooting

### The frontend cannot reach Django

Confirm `run_all.py` is still running and that ports `3000` and `8000` are free.
Use exactly `http://127.0.0.1:3000` during local development so origins and
cookie behavior match the defaults.

### Sign-in stops working after authentication changes

Clear the site's cookies and sign in again. Existing sessions can be revoked by
password changes or security updates.

### Database errors mention missing tables or columns

Apply migrations:

```bash
backend/venv/bin/python backend/manage.py migrate
```

### Uploads are rejected

Submission and template files must be valid PDF or DOCX files no larger than
10 MB. Renaming another file type does not make it valid.

### Local administrator already exists

The seed command does not overwrite an existing administrator password. Change
it from the Admin workspace or with Django's password-management tooling.
