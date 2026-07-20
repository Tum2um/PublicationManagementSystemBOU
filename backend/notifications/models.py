"""In-application notification persistence and creation helper."""

from django.conf import settings
from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, default="info")
    related_submission_id = models.IntegerField(null=True, blank=True)
    channel = models.CharField(max_length=50, default="in_app")
    email_sent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


def create_notification(user_id, title, message, notification_type="info", related_submission_id=None):
    return Notification.objects.create(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_submission_id=related_submission_id,
    )
