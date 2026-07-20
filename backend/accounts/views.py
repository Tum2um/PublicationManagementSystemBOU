"""Account lifecycle, sign-in, role assignment, and audit-log endpoints."""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.models import Group, User
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from bou_pms.api import (
    create_token,
    json_error,
    parse_json,
    revoke_token,
    serialize_user,
    token_required,
)
from accounts.models import AuditLog, record_audit


ROLE_NAMES = [
    "Admin",
    "ResearchOfficer",
    "EditorialBoard",
    "InternalReviewer",
    "ExternalReviewer",
    "Author",
]


def health(_request):
    return JsonResponse({"status": "Django PMS backend is running"})


def apply_roles(user, role_names):
    """Replace a user's roles with the validated role set supplied by an admin."""
    user.groups.clear()
    for role_name in role_names or ["Author"]:
        if role_name in ROLE_NAMES:
            group, _created = Group.objects.get_or_create(name=role_name)
            user.groups.add(group)


def create_user_from_payload(data):
    """Validate an account payload and create a Django user plus role groups."""
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    role_names = data.get("roles") or ["Author"]

    if not name or not email or not password:
        return None, ("Name, email and password are required", 400)
    try:
        validate_email(email)
    except ValidationError:
        return None, ("Enter a valid email address", 400)
    if not isinstance(role_names, list) or not role_names or any(role not in ROLE_NAMES for role in role_names):
        return None, ("Select one or more valid roles", 400)
    try:
        validate_password(password)
    except ValidationError as error:
        return None, (" ".join(error.messages), 400)
    if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
        return None, ("User with this email already exists", 409)

    user = User.objects.create_user(username=email, email=email, password=password)
    name_parts = name.split(" ", 1)
    user.first_name = name_parts[0]
    user.last_name = name_parts[1] if len(name_parts) > 1 else ""
    user.save()
    apply_roles(user, role_names)
    return user, None


@csrf_exempt
def login(request):
    if request.method != "POST":
        return json_error("Method not allowed", 405)
    origin = request.headers.get("Origin", "").rstrip("/")
    if origin and origin not in settings.CORS_ALLOWED_ORIGINS:
        return json_error("Request origin is not allowed", 403)

    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    client_ip = request.META.get("REMOTE_ADDR", "unknown")
    throttle_key = f"login-attempts:{client_ip}:{email}"
    attempts = cache.get(throttle_key, 0)
    if attempts >= 5:
        return json_error("Too many sign-in attempts. Try again in 15 minutes.", 429)
    user = authenticate(username=email, password=password)
    if not user:
        cache.set(throttle_key, attempts + 1, 15 * 60)
        AuditLog.objects.create(actor_email=email, action="Login attempt", outcome="failed", details="Invalid credentials")
        return json_error("Invalid email or password", 401)
    if not user.is_active:
        return json_error("Account is disabled", 403)

    cache.delete(throttle_key)
    serialized = serialize_user(user)
    record_audit(user, "Login")
    response = JsonResponse({
        "user_id": user.id,
        "roles": serialized["roles"],
        "email": user.email,
    })
    response.set_cookie(
        settings.AUTH_TOKEN_COOKIE,
        create_token(user),
        max_age=settings.AUTH_TOKEN_MAX_AGE,
        httponly=True,
        secure=settings.AUTH_TOKEN_COOKIE_SECURE,
        samesite=settings.AUTH_TOKEN_COOKIE_SAMESITE,
        path="/",
    )
    return response


@csrf_exempt
def logout(request):
    if request.method != "POST":
        return json_error("Method not allowed", 405)
    origin = request.headers.get("Origin", "").rstrip("/")
    if request.COOKIES.get(settings.AUTH_TOKEN_COOKIE) and origin not in settings.CORS_ALLOWED_ORIGINS:
        return json_error("Request origin is not allowed", 403)
    auth_header = request.headers.get("Authorization", "")
    raw_token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else request.COOKIES.get(settings.AUTH_TOKEN_COOKIE)
    revoke_token(raw_token)
    response = JsonResponse({"message": "Signed out"})
    response.delete_cookie(settings.AUTH_TOKEN_COOKIE, path="/", samesite=settings.AUTH_TOKEN_COOKIE_SAMESITE)
    return response


@token_required()
def me(request):
    return JsonResponse(serialize_user(request.user))


@csrf_exempt
@token_required(required_roles=["Admin", "ResearchOfficer", "EditorialBoard"])
def users(request):
    if request.method == "GET":
        return JsonResponse([serialize_user(user) for user in User.objects.all().order_by("id")], safe=False)

    if request.method == "POST":
        if "Admin" not in request.user_roles:
            return json_error("Permission denied", 403)
        data = parse_json(request)
        if data is None:
            return json_error("Invalid JSON", 400)
        user, error = create_user_from_payload(data)
        if error:
            message, status = error
            return json_error(message, status)
        record_audit(request.user, "Created user account", "user", user.id, details=user.email)
        return JsonResponse({"message": "User created successfully", **serialize_user(user)}, status=201)

    return json_error("Method not allowed", 405)


@csrf_exempt
@token_required(required_roles=["Admin"])
def user_detail(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return json_error("User not found", 404)

    if request.method != "PUT":
        return json_error("Method not allowed", 405)

    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)
    if user.id == request.user.id and data.get("is_active") is False:
        return json_error("You cannot deactivate your own account", 400)
    if "roles" in data:
        if not isinstance(data["roles"], list):
            return json_error("Roles must be a list", 400)
        selected_roles = data["roles"]
        if not selected_roles or any(role not in ROLE_NAMES for role in selected_roles):
            return json_error("Select at least one valid role", 400)
        apply_roles(user, selected_roles)
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    if data.get("password"):
        try:
            validate_password(data["password"], user=user)
        except ValidationError as error:
            return json_error(" ".join(error.messages), 400)
        user.set_password(data["password"])
        user.api_tokens.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    user.save()
    record_audit(request.user, "Updated user account", "user", user.id, details=user.email)
    return JsonResponse({"message": "User account updated", **serialize_user(user)})


@token_required(required_roles=["Admin"])
def audit_logs(request):
    if request.method != "GET":
        return json_error("Method not allowed", 405)
    items = AuditLog.objects.select_related("user").all()[:500]
    return JsonResponse([
        {
            "id": item.id,
            "user": item.user.get_full_name() if item.user and item.user.get_full_name() else item.actor_email or "System",
            "email": item.actor_email,
            "action": item.action,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "outcome": item.outcome,
            "details": item.details,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ], safe=False)
