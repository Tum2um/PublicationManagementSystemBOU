from typing import Optional

from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    user_id: int
    title: str = Field(min_length=3, max_length=150)
    message: str = Field(min_length=3, max_length=1000)
    notification_type: str = "info"
    related_submission_id: Optional[int] = None
    channel: str = "in_app"


class NotificationRead(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    related_submission_id: Optional[int]
    channel: str
    is_read: bool
    email_sent: bool
    created_at: str
