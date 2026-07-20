# PublicationManagementSystemBOU

## Local Development

Run this once to create/install each service environment:

```bash
python3 setup_local.py
```

Start the Django backend and the frontend:

```bash
python3 run_all.py
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

The main URL loads `BOU_PMS_Mockup.html`, which is the complete role-based
Publication Management System experience used for the approved mockup.

Local development admin account:

```text
Email: admin@bou.or.ug
Password: Admin123!
```

The frontend does not have public registration. Accounts are created by the System Admin from inside the app.

The old `services/` Flask/FastAPI folders are kept for reference only. Active development now runs through the Django backend in `backend/`.
