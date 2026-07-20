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
