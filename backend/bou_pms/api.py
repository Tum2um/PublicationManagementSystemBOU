"""Shared JSON, authentication, and role-authorization helpers for the API.

Tokens are opaque random values. Only their SHA-256 digests are stored, so a
database read does not directly disclose usable session credentials.
"""

import hashlib
import json
import secrets
from datetime import timedelta
from functools import wraps

from django.contrib.auth.models import User
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

from accounts.models import AuthToken


TOKEN_MAX_AGE_SECONDS = settings.AUTH_TOKEN_MAX_AGE


def parse_json(request):
    """Decode a JSON request body, returning ``None`` for malformed JSON."""
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def json_error(message, status=400):
    return JsonResponse({"message": message}, status=status)


def user_roles(user):
    return list(user.groups.values_list("name", flat=True))


def serialize_user(user):
    return {
        "id": user.id,
        "name": user.get_full_name() or user.username,
        "email": user.email,
        "roles": user_roles(user),
        "is_active": user.is_active,
    }


def create_token(user):
    """Create a revocable, expiring API session and return its raw token once."""
    raw_token = secrets.token_urlsafe(48)
    AuthToken.objects.create(
        user=user,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(seconds=TOKEN_MAX_AGE_SECONDS),
    )
    return raw_token


def revoke_token(raw_token):
    """Revoke a presented token without storing or logging its raw value."""
    if raw_token:
        AuthToken.objects.filter(
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())


def get_user_from_request(request):
    """Resolve an active user from a bearer token or the HTTP-only cookie."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else request.COOKIES.get(settings.AUTH_TOKEN_COOKIE)
    if not token:
        return None, "Token is missing!"
    token_record = AuthToken.objects.select_related("user").filter(
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
        user__is_active=True,
    ).first()
    if not token_record:
        return None, "Invalid token!"
    return token_record.user, None


def token_required(required_roles=None):
    """Require authentication and, when supplied, membership in any given role.

    Cookie-authenticated writes also require a trusted Origin. This is the API's
    CSRF defence because the browser attaches the HTTP-only cookie automatically.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            uses_cookie = bool(request.COOKIES.get(settings.AUTH_TOKEN_COOKIE)) and not request.headers.get("Authorization", "").startswith("Bearer ")
            if uses_cookie and request.method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("Origin", "").rstrip("/")
                if origin not in settings.CORS_ALLOWED_ORIGINS:
                    return json_error("Request origin is not allowed", 403)
            user, error = get_user_from_request(request)
            if error:
                return json_error(error, 401)

            roles = set(user_roles(user))
            if required_roles and not roles.intersection(set(required_roles)):
                return json_error("Permission denied", 403)

            request.user = user
            request.user_roles = roles
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
