# Notification Service

This service handles in-app notifications for the BOU Publication Management System.

## Main Features

- Create notification
- View notifications for a user
- Count unread notifications
- Mark one notification as read
- Mark all notifications as read

## Run Service

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 5005