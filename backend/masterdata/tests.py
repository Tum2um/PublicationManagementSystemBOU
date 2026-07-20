import json

from django.contrib.auth.models import Group, User
from django.test import TestCase

from bou_pms.api import create_token


class MasterDataManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin@bou.or.ug", password="Admin123!")
        self.admin.groups.add(Group.objects.create(name="Admin"))
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {create_token(self.admin)}"}

    def test_admin_can_create_and_deactivate_research_theme(self):
        created = self.client.post("/api/themes", data=json.dumps({"name": "Financial Stability"}), content_type="application/json", **self.headers)
        self.assertEqual(created.status_code, 201)
        updated = self.client.put(f"/api/themes/{created.json()['id']}", data=json.dumps({"is_active": False}), content_type="application/json", **self.headers)
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["is_active"])

    def test_admin_can_create_notification_template(self):
        response = self.client.post("/api/templates", data={"name": "Submission received", "template_type": "notification", "subject": "Received", "body": "Your paper was received."}, **self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["version"], 1)
