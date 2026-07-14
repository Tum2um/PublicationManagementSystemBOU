import json
from functools import wraps

from django.contrib.auth.models import User
from django.core import signing
from django.http import JsonResponse


TOKEN_SALT = "bou-pms-auth"
TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60


def parse_json(request):
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
    return signing.dumps(
        {"user_id": user.id, "email": user.email, "roles": user_roles(user)},
        salt=TOKEN_SALT,
    )


def get_user_from_request(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, "Token is missing!"

    token = auth_header.split(" ", 1)[1]
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE_SECONDS)
    except signing.SignatureExpired:
        return None, "Token has expired!"
    except signing.BadSignature:
        return None, "Invalid token!"

    try:
        return User.objects.get(id=payload["user_id"], is_active=True), None
    except User.DoesNotExist:
        return None, "User not found"


def token_required(required_roles=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
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
