from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from bou_pms.api import (
    create_token,
    json_error,
    parse_json,
    serialize_user,
    token_required,
)


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
    user.groups.clear()
    for role_name in role_names or ["Author"]:
        if role_name in ROLE_NAMES:
            group, _created = Group.objects.get_or_create(name=role_name)
            user.groups.add(group)


def create_user_from_payload(data):
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    role_names = data.get("roles") or ["Author"]

    if not name or not email or not password:
        return None, ("Name, email and password are required", 400)
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

    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user = authenticate(username=email, password=password)
    if not user:
        return json_error("Invalid email or password", 401)
    if not user.is_active:
        return json_error("Account is disabled", 403)

    serialized = serialize_user(user)
    return JsonResponse({
        "token": create_token(user),
        "user_id": user.id,
        "roles": serialized["roles"],
        "email": user.email,
    })


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
        return JsonResponse({"message": "User created successfully", **serialize_user(user)}, status=201)

    return json_error("Method not allowed", 405)
