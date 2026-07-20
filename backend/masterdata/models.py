"""Administrator-managed reference data and reusable content templates."""

from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ResearchTheme(models.Model):
    name = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ContentTemplate(models.Model):
    TEMPLATE_TYPES = [
        ("review_comments", "Reviewer comments template"),
        ("review_guidelines", "Reviewer guidelines"),
        ("notification", "Notification notice"),
    ]

    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=40, choices=TEMPLATE_TYPES)
    subject = models.CharField(max_length=250, blank=True)
    body = models.TextField(blank=True)
    file = models.FileField(upload_to="system_templates/", blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
