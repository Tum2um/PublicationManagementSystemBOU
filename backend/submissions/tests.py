import json
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone

from bou_pms.api import create_token
from submissions.models import Call, Submission, Theme
from reviews.models import ReviewAssignment


class CallManagementTests(TestCase):
    def setUp(self):
        officer_group = Group.objects.create(name="ResearchOfficer")
        self.officer = User.objects.create_user("officer@bou.or.ug", password="Officer123!")
        self.officer.groups.add(officer_group)
        now = timezone.now()
        self.call = Call.objects.create(
            fiscal_year="2026/2027",
            description="Research call",
            abstract_deadline=now + timedelta(days=7),
            paper_deadline=now + timedelta(days=30),
            status="published",
        )
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {create_token(self.officer)}"}

    def test_officer_can_close_call(self):
        response = self.client.put(
            f"/api/calls/{self.call.id}",
            data=json.dumps({"status": "closed"}),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.call.refresh_from_db()
        self.assertEqual(self.call.status, "closed")

    def test_invalid_status_is_rejected(self):
        response = self.client.put(
            f"/api/calls/{self.call.id}",
            data=json.dumps({"status": "deleted"}),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_research_officer_cannot_make_final_publication_decision(self):
        author = User.objects.create_user("author@bou.or.ug", password="Author123!")
        theme = Theme.objects.create(call=self.call, name="Financial Stability")
        submission = Submission.objects.create(call=self.call, theme=theme, title="Test paper", corresponding_author=author)
        response = self.client.put(
            f"/api/submissions/{submission.id}/status",
            data=json.dumps({"status": "published", "current_stage": "published"}),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 403)

    def test_public_repository_lists_only_published_submissions(self):
        author = User.objects.create_user("public-author@bou.or.ug", first_name="Public", last_name="Author")
        theme = Theme.objects.create(call=self.call, name="Monetary Policy")
        Submission.objects.create(call=self.call, theme=theme, title="Published paper", corresponding_author=author, status="published", publication_reference="BOU-WP-2026-001")
        Submission.objects.create(call=self.call, theme=theme, title="Draft paper", corresponding_author=author, status="submitted")
        response = self.client.get("/api/publications")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["title"] for item in response.json()], ["Published paper"])

    def test_reviewer_only_sees_assigned_submissions(self):
        reviewer = User.objects.create_user("reviewer@bou.or.ug", password="Reviewer123!")
        reviewer.groups.add(Group.objects.create(name="InternalReviewer"))
        author = User.objects.create_user("author2@bou.or.ug", password="Author123!")
        theme = Theme.objects.create(call=self.call, name="Access Control")
        assigned = Submission.objects.create(call=self.call, theme=theme, title="Assigned", corresponding_author=author)
        Submission.objects.create(call=self.call, theme=theme, title="Private", corresponding_author=author)
        ReviewAssignment.objects.create(submission=assigned, reviewer=reviewer, reviewer_type="internal", assigned_by=self.officer)
        response = self.client.get(
            "/api/submissions",
            HTTP_AUTHORIZATION=f"Bearer {create_token(reviewer)}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["title"] for item in response.json()], ["Assigned"])

    def test_author_cannot_enumerate_review_assignments_or_create_notifications(self):
        author = User.objects.create_user("restricted-author@bou.or.ug", password="Author123!")
        author.groups.add(Group.objects.get_or_create(name="Author")[0])
        headers = {"HTTP_AUTHORIZATION": f"Bearer {create_token(author)}"}
        self.assertEqual(self.client.get("/api/review-assignments", **headers).status_code, 403)
        response = self.client.post(
            "/notifications",
            data=json.dumps({"user_id": self.officer.id, "title": "Forged", "message": "Forged"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 403)
