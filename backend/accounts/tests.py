import json

from django.contrib.auth.models import Group, User
from django.test import TestCase

from bou_pms.api import create_token


class UserManagementTests(TestCase):
    def setUp(self):
        admin_group = Group.objects.create(name="Admin")
        self.admin = User.objects.create_user("admin@bou.or.ug", password="Admin123!")
        self.admin.groups.add(admin_group)
        self.author = User.objects.create_user("author@bou.or.ug", password="Author123!")
        self.author.groups.add(Group.objects.create(name="Author"))
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {create_token(self.admin)}"}

    def test_admin_can_change_roles_and_account_status(self):
        response = self.client.put(
            f"/api/users/{self.author.id}",
            data=json.dumps({"roles": ["Author", "InternalReviewer"], "is_active": False}),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.author.refresh_from_db()
        self.assertFalse(self.author.is_active)
        self.assertSetEqual(set(self.author.groups.values_list("name", flat=True)), {"Author", "InternalReviewer"})

    def test_admin_cannot_deactivate_self(self):
        response = self.client.put(
            f"/api/users/{self.admin.id}",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)
