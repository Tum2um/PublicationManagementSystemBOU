from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from bou_pms.api import json_error, parse_json, token_required
from masterdata.models import Department


def serialize_department(department):
    return {
        "id": department.id,
        "name": department.name,
        "is_active": department.is_active,
    }


@csrf_exempt
@token_required()
def departments(request):
    if request.method == "GET":
        items = Department.objects.filter(is_active=True).order_by("name")
        return JsonResponse([serialize_department(item) for item in items], safe=False)

    if request.method == "POST":
        if "Admin" not in request.user_roles:
            return json_error("Permission denied", 403)
        data = parse_json(request)
        if data is None:
            return json_error("Invalid JSON", 400)
        name = data.get("name", "").strip()
        if not name:
            return json_error("Name is required", 400)
        department, _created = Department.objects.get_or_create(name=name)
        return JsonResponse(serialize_department(department), status=201)

    return json_error("Method not allowed", 405)


@csrf_exempt
@token_required(required_roles=["Admin"])
def department_detail(request, department_id):
    try:
        department = Department.objects.get(id=department_id)
    except Department.DoesNotExist:
        return json_error("Department not found", 404)

    if request.method != "PUT":
        return json_error("Method not allowed", 405)

    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)
    if "name" in data:
        department.name = data["name"].strip()
    if "is_active" in data:
        department.is_active = bool(data["is_active"])
    department.save()
    return JsonResponse(serialize_department(department))
