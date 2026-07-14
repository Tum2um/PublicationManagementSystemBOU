# Notification Service

This service handles in-app notifications for the BOU Publication Management System.

## What This Service Does

- Create a notification for a user.
- View all notifications for a user.
- View only unread notifications.
- Count unread notifications.
- Mark one notification as read.
- Mark one notification as unread.
- Mark all notifications as read.
- Delete a notification.

## Folder Structure

```text
notification
├── app
│   ├── __init__.py
│   ├── database.py
│   ├── main.py
│   └── schemas.py
├── requirements.txt
└── README.md
```

## How To Run In VS Code

1. Open VS Code.
2. Click `File`.
3. Click `Open Folder...`.
4. Open the project folder:

```text
/Users/garethtusiime/Desktop/BOU Internship/PublicationManagementSystemBOU
```

5. Click `Terminal`.
6. Click `New Terminal`.
7. Move into your service folder:

```bash
cd services/notification
```

8. Activate your virtual environment:

```bash
source venv/bin/activate
```

9. Install requirements if needed:

```bash
pip install -r requirements.txt
```

10. Run the service:

```bash
uvicorn app.main:app --reload --port 5005
```

11. Open this in your browser:

```text
http://127.0.0.1:5005/docs
```

## Test Examples

Create a notification:

```bash
curl -X POST http://127.0.0.1:5005/notifications \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "title": "Submission received",
    "message": "Your paper has been received and is awaiting review.",
    "notification_type": "submission",
    "related_submission_id": 10
  }'
```

View notifications for user 1:

```bash
curl http://127.0.0.1:5005/notifications/user/1
```

View unread notifications only:

```bash
curl "http://127.0.0.1:5005/notifications/user/1?unread_only=true"
```

Count unread notifications:

```bash
curl http://127.0.0.1:5005/notifications/user/1/unread-count
```

Mark notification 1 as read:

```bash
curl -X PUT http://127.0.0.1:5005/notifications/1/read
```

Mark all notifications for user 1 as read:

```bash
curl -X PUT http://127.0.0.1:5005/notifications/user/1/read-all
```

## What To Tell The Team

I am handling the Notification Service. It runs on port `5005` and supports creating notifications, viewing notifications, unread counts, marking notifications as read/unread, marking all as read, and deleting notifications.
