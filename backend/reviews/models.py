"""Reviewer assignment and comment entities for the verification workflow."""

from django.conf import settings
from django.db import models

from submissions.models import Submission


class ReviewAssignment(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="review_assignments")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="review_assignments")
    reviewer_type = models.CharField(max_length=20)
    status = models.CharField(max_length=60, default="pending_editorial_verification")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_reviews")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="verified_review_assignments")
    verify_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReviewComment(models.Model):
    assignment = models.ForeignKey(ReviewAssignment, on_delete=models.CASCADE, related_name="comments")
    recommendation = models.CharField(max_length=80)
    comments = models.TextField()
    verification_status = models.CharField(max_length=30, default="pending")
    verification_reason = models.TextField(blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
