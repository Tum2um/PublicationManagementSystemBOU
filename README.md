# PublicationManagementSystemBOU

## Local Backend Services

Run this once to create/install each service environment:

```bash
python3 setup_local.py
```

Start all backend services:

```bash
python3 run_all.py
```

Service ports:

| Service | Port |
|---|---:|
| Identity | 5001 |
| Submission | 5002 |
| Review | 5003 |
| Master Data | 5004 |
| Notification | 5005 |

Open Gareth's Notification Service docs:

```text
http://127.0.0.1:5005/docs
```
