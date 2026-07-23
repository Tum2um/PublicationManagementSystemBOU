import json

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from bou_pms.api import create_token
from notifications.models import Notification
from reviews.models import ReviewAssignment, ReviewComment
from submissions.models import Call, DocumentVersion, Submission, Theme


class ReviewDocumentWorkflowTests(TestCase):
    def setUp(self):
        for role in ["Author", "ResearchOfficer", "InternalReviewer"]:
            Group.objects.create(name=role)
        self.author = User.objects.create_user("author@bou.or.ug", password="Author123!")
        self.author.groups.add(Group.objects.get(name="Author"))
        self.officer = User.objects.create_user("officer@bou.or.ug", password="Officer123!")
        self.officer.groups.add(Group.objects.get(name="ResearchOfficer"))
        self.reviewer = User.objects.create_user("reviewer@bou.or.ug", password="Reviewer123!")
        self.reviewer.groups.add(Group.objects.get(name="InternalReviewer"))
        call = Call.objects.create(
            fiscal_year="2027/2028", description="Test call",
            abstract_deadline=timezone.now(), paper_deadline=timezone.now(), status="published",
        )
        theme = Theme.objects.create(call=call, name="Financial Stability")
        self.submission = Submission.objects.create(
            call=call, theme=theme, title="Test paper", corresponding_author=self.author,
        )
        self.document = DocumentVersion.objects.create(
            submission=self.submission, doc_type="paper",
            file=SimpleUploadedFile("paper.pdf", b"%PDF-test", content_type="application/pdf"),
            uploaded_by=self.author,
        )
        self.assignment = ReviewAssignment.objects.create(
            submission=self.submission, reviewer=self.reviewer, reviewer_type="internal",
            assigned_by=self.officer, status="verified",
        )

    def auth(self, user):
        return {"HTTP_AUTHORIZATION": f"Bearer {create_token(user)}"}

    def test_reviewer_sees_and_downloads_assigned_paper(self):
        response = self.client.get("/api/review-assignments", **self.auth(self.reviewer))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["submission_documents"][0]["type"], "paper")
        self.assertEqual(
            self.client.get(f"/api/documents/{self.document.id}/download", **self.auth(self.reviewer)).status_code,
            200,
        )

    def test_review_attachment_reaches_officer_then_author(self):
        response = self.client.post(
            f"/api/review-assignments/{self.assignment.id}/comments",
            data={
                "recommendation": "major_revision",
                "comments": "Please revise the methodology.",
                "file": SimpleUploadedFile("comments.pdf", b"%PDF-review", content_type="application/pdf"),
            },
            **self.auth(self.reviewer),
        )
        self.assertEqual(response.status_code, 201)
        comment = ReviewComment.objects.get(id=response.json()["comment_id"])
        self.assertTrue(comment.attachment)
        self.assertTrue(Notification.objects.filter(user=self.officer, title="Reviewer comments submitted").exists())
        verify = self.client.put(
            f"/api/review-comments/{comment.id}/verify",
            data=json.dumps({"approved": True}), content_type="application/json", **self.auth(self.officer),
        )
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(Notification.objects.filter(user=self.author, title="Revision requested").exists())
        self.assertEqual(
            self.client.get(f"/api/review-comments/{comment.id}/attachment", **self.auth(self.author)).status_code,
            200,
        )
