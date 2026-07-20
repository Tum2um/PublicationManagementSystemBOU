import json

from django.contrib.auth.models import Group, User
from django.test import TestCase

from bou_pms.api import create_token
from django.conf import settings


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

    def test_admin_can_view_audit_log(self):
        from accounts.models import record_audit

        record_audit(self.admin, "Test action", "user", self.author.id)
        response = self.client.get("/api/audit-logs", **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["action"], "Test action")

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            "/api/users",
            data=json.dumps({"name": "New Author", "email": "new@bou.or.ug", "password": "password", "roles": ["Author"]}),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_logout_revokes_server_side_token(self):
        token = create_token(self.admin)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        self.assertEqual(self.client.get("/api/auth/me", **headers).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout", **headers).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", **headers).status_code, 401)

    def test_cookie_authenticated_write_rejects_untrusted_origin(self):
        token = create_token(self.admin)
        self.client.cookies[settings.AUTH_TOKEN_COOKIE] = token
        response = self.client.put(
            f"/api/users/{self.author.id}",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
            HTTP_ORIGIN="https://attacker.example",
        )
        self.assertEqual(response.status_code, 403)
