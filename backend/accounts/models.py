from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    actor_email = models.EmailField(blank=True)
    action = models.CharField(max_length=250)
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.CharField(max_length=80, blank=True)
    outcome = models.CharField(max_length=30, default="success")
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


def record_audit(user, action, entity_type="", entity_id="", outcome="success", details=""):
    return AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        actor_email=getattr(user, "email", "") or "",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ""),
        outcome=outcome,
        details=details,
    )
