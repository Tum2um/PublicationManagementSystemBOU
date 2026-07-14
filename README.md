# PublicationManagementSystemBOU

## Local Development

Run this once to create/install each service environment:

```bash
python3 setup_local.py
```

Start all backend services and the frontend:

```bash
python3 run_all.py
```

Service ports:

| Service | Port |
|---|---:|
| Frontend | 3000 |
| Identity | 5001 |
| Submission | 5002 |
| Review | 5003 |
| Master Data | 5004 |
| Notification | 5005 |

Open the system in the browser:

```text
http://127.0.0.1:3000
```

Local development admin account:

```text
Email: admin@bou.or.ug
Password: Admin123!
```

The frontend does not have public registration. Accounts are created by the System Admin from inside the app.

Open Gareth's Notification Service docs:

```text
http://127.0.0.1:5005/docs
```
