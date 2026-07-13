from fastapi import FastAPI, HTTPException
from app.database import get_connection, create_tables, now
from app.schemas import NotificationCreate

app = FastAPI(title="BOU Notification Service")


@app.on_event("startup")
def startup():
    create_tables()


@app.get("/health")
def health_check():
    return {
        "service": "notification-service",
        "status": "running"
    }


@app.post("/notifications")
def create_notification(notification: NotificationCreate):
    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO notifications (
            user_id,
            title,
            message,
            notification_type,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            notification.user_id,
            notification.title,
            notification.message,
            notification.notification_type,
            now(),
        ),
    )

    conn.commit()
    notification_id = cursor.lastrowid
    conn.close()

    return {
        "message": "Notification created successfully",
        "notification_id": notification_id
    }


@app.get("/notifications/user/{user_id}")
def get_user_notifications(user_id: int):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM notifications
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,),
    ).fetchall()

    conn.close()

    return {
        "user_id": user_id,
        "notifications": [dict(row) for row in rows]
    }


@app.get("/notifications/user/{user_id}/unread-count")
def get_unread_count(user_id: int):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    return {
        "user_id": user_id,
        "unread_count": row["unread_count"]
    }


@app.put("/notifications/{notification_id}/read")
def mark_notification_as_read(notification_id: int):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM notifications
        WHERE id = ?
        """,
        (notification_id,),
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Notification not found")

    conn.execute(
        """
        UPDATE notifications
        SET is_read = 1
        WHERE id = ?
        """,
        (notification_id,),
    )

    conn.commit()
    conn.close()

    return {
        "message": "Notification marked as read",
        "notification_id": notification_id
    }


@app.put("/notifications/user/{user_id}/read-all")
def mark_all_notifications_as_read(user_id: int):
    conn = get_connection()

    conn.execute(
        """
        UPDATE notifications
        SET is_read = 1
        WHERE user_id = ?
        """,
        (user_id,),
    )

    conn.commit()
    conn.close()

    return {
        "message": "All notifications marked as read",
        "user_id": user_id
    }