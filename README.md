# PublicationManagementSystemBOU

## Local Development

Run this once to create/install each service environment:

```bash
# macOS / Linux
python3 setup_local.py
```

```powershell
# Windows
python setup_local.py
```

Start the Django backend and the frontend:

```bash
# macOS / Linux
python3 run_all.py
```

```powershell
# Windows
python run_all.py
```

Service ports:

| Service | Port |
|---|---:|
| Frontend | 3000 |
| Django backend | 8000 |

Open the system in the browser:

```text
http://127.0.0.1:3000
```

The main URL loads the authenticated frontend. Users must sign in with an
account created by the System Admin, and the available workspace is determined
by the roles assigned to that account.

`BOU_PMS_Mockup.html` is retained as a design reference only and is not served
as the running application's entry point.

Local development admin account:

```text
Email: admin@bou.or.ug
Password: Admin123!
```

This credential is for an isolated local workstation only. Set
`DEV_ADMIN_PASSWORD` before running `setup_local.py` to choose a different
development password. The seed command is disabled when `DJANGO_DEBUG=false`.

The frontend does not have public registration. Accounts are created by the System Admin from inside the app.

## Implemented workflow

- System Admin: user and role management, departments, research themes,
  versioned templates/notices, public repository oversight, and audit logs.
- Research Officer: draft/publish/close calls, select approved themes, assign
  internal or external reviewers, conflict-of-interest checks, verify comments,
  and export reports.
- Editorial Board: verify reviewer assignments, record final decisions, assign
  publication references, and publish approved papers.
- Reviewers: see only their assignments, download current guidance/templates,
  and submit recommendations and comments.
- Authors: create submissions, manage co-authors and affiliations, upload
  versioned PDF/DOCX documents, view details, and track revisions and decisions.
- Public visitors: browse and download published working papers without signing
  in.

Uploaded submission documents and system templates are stored in
`backend/uploads/` during local development.

Run the automated backend checks with:

```bash
backend/venv/bin/python backend/manage.py test accounts masterdata submissions reviews notifications
```

The active backend is the Django application in `backend/`.

## Security and production deployment

The application includes server-side role and object authorization, revocable
random session tokens in HTTP-only cookies, origin validation for cookie-based
writes, login throttling, Django password validation, restricted CORS, security
headers and CSP, protected private-document downloads, upload size/type/signature
checks, and audit logging. Private uploads are no longer served directly from
the media directory.

Do not deploy with the local defaults. Configure at least:

```bash
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<long-random-secret-from-a-secret-manager>
DJANGO_ALLOWED_HOSTS=research.example.org
CORS_ALLOWED_ORIGINS=https://research.example.org
AUTH_COOKIE_SECURE=true
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_PRELOAD=true
```

Run the deployment and test checks before each release:

```bash
DJANGO_DEBUG=false \
DJANGO_SECRET_KEY='<long-random-secret>' \
DJANGO_ALLOWED_HOSTS=research.example.org \
CORS_ALLOWED_ORIGINS=https://research.example.org \
SECURE_HSTS_PRELOAD=true \
backend/venv/bin/python backend/manage.py check --deploy

backend/venv/bin/python backend/manage.py test accounts masterdata submissions reviews notifications
backend/venv/bin/python -m pip check
```

### Controls that still require deployment or operational work

- Terminate HTTPS with a maintained reverse proxy/load balancer and use a valid
  certificate. HSTS should only be enabled after HTTPS is confirmed everywhere.
- Replace SQLite with a managed production database, encrypt disks/backups,
  restrict database and upload-storage access, and test restores regularly.
- Add organisation-managed MFA or single sign-on. This cannot be completed
  safely without choosing and configuring the Bank's identity provider.
- Connect uploads to an antivirus/content-disarm service. The application now
  rejects mismatched file signatures, but this is not malware scanning.
- Send security logs to protected central monitoring and configure alerts for
  repeated login failures, access denials, and privileged account changes.
- Run dependency scanning, SAST/DAST, and an independent penetration test before
  launch and after material changes. OWASP alignment is an ongoing verification
  process, not a one-time certification supplied by application code alone.
- Define session-retention and scheduled cleanup for expired/revoked
  `accounts_authtoken` records, plus incident-response and key-rotation procedures.
