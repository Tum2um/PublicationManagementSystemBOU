import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "notifications.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def create_tables():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT NOT NULL DEFAULT 'info',
            related_submission_id INTEGER,
            channel TEXT NOT NULL DEFAULT 'in_app',
            is_read INTEGER NOT NULL DEFAULT 0,
            email_sent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(notifications)").fetchall()
    }
    new_columns = {
        "related_submission_id": "INTEGER",
        "channel": "TEXT NOT NULL DEFAULT 'in_app'",
        "email_sent": "INTEGER NOT NULL DEFAULT 0",
    }
    for column_name, column_sql in new_columns.items():
        if column_name not in existing_columns:
            conn.execute(
                f"ALTER TABLE notifications ADD COLUMN {column_name} {column_sql}"
            )
    conn.commit()
    conn.close()
