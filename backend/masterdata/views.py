from pathlib import Path

from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from bou_pms.api import json_error, parse_json, token_required
from masterdata.models import ContentTemplate, Department, ResearchTheme


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


def serialize_theme(theme):
    return {"id": theme.id, "name": theme.name, "is_active": theme.is_active}


@csrf_exempt
@token_required()
def themes(request):
    if request.method == "GET":
        return JsonResponse([serialize_theme(item) for item in ResearchTheme.objects.all().order_by("name")], safe=False)
    if request.method == "POST" and "Admin" in request.user_roles:
        data = parse_json(request)
        if data is None:
            return json_error("Invalid JSON", 400)
        name = data.get("name", "").strip()
        if not name:
            return json_error("Name is required", 400)
        item, created = ResearchTheme.objects.get_or_create(name=name, defaults={"is_active": True})
        if not created and not item.is_active:
            item.is_active = True
            item.save()
        return JsonResponse(serialize_theme(item), status=201)
    return json_error("Permission denied" if request.method == "POST" else "Method not allowed", 403 if request.method == "POST" else 405)


@csrf_exempt
@token_required(required_roles=["Admin"])
def theme_detail(request, theme_id):
    if request.method != "PUT":
        return json_error("Method not allowed", 405)
    try:
        item = ResearchTheme.objects.get(id=theme_id)
    except ResearchTheme.DoesNotExist:
        return json_error("Theme not found", 404)
    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)
    if data.get("name"):
        item.name = data["name"].strip()
    if "is_active" in data:
        item.is_active = bool(data["is_active"])
    item.save()
    return JsonResponse(serialize_theme(item))


def serialize_template(item):
    return {
        "id": item.id,
        "name": item.name,
        "template_type": item.template_type,
        "subject": item.subject,
        "body": item.body,
        "file_path": f"/api/templates/{item.id}/download" if item.file else "",
        "version": item.version,
        "is_active": item.is_active,
        "updated_at": item.updated_at.isoformat(),
    }


@csrf_exempt
@token_required(required_roles=["Admin", "ResearchOfficer", "EditorialBoard", "InternalReviewer", "ExternalReviewer"])
def templates(request):
    if request.method == "GET":
        return JsonResponse([serialize_template(item) for item in ContentTemplate.objects.filter(is_active=True)], safe=False)
    if request.method != "POST" or "Admin" not in request.user_roles:
        return json_error("Permission denied" if request.method == "POST" else "Method not allowed", 403 if request.method == "POST" else 405)
    name = request.POST.get("name", "").strip()
    template_type = request.POST.get("template_type", "")
    if not name or template_type not in dict(ContentTemplate.TEMPLATE_TYPES):
        return json_error("A name and valid template type are required", 400)
    uploaded_file = request.FILES.get("file")
    if uploaded_file:
        extension = Path(uploaded_file.name).suffix.lower()
        if uploaded_file.size > 10 * 1024 * 1024 or extension not in {".pdf", ".docx"}:
            return json_error("Template files must be PDF or DOCX and no larger than 10 MB", 400)
        header = uploaded_file.read(4)
        uploaded_file.seek(0)
        if (extension == ".pdf" and header != b"%PDF") or (extension == ".docx" and header[:2] != b"PK"):
            return json_error("The template content does not match its file extension", 400)
    item = ContentTemplate.objects.create(
        name=name,
        template_type=template_type,
        subject=request.POST.get("subject", ""),
        body=request.POST.get("body", ""),
        file=uploaded_file,
    )
    return JsonResponse(serialize_template(item), status=201)


@csrf_exempt
@token_required(required_roles=["Admin"])
def template_detail(request, template_id):
    try:
        item = ContentTemplate.objects.get(id=template_id)
    except ContentTemplate.DoesNotExist:
        return json_error("Template not found", 404)
    if request.method == "PUT":
        data = parse_json(request)
        if data is None:
            return json_error("Invalid JSON", 400)
        for field in ["name", "subject", "body", "is_active"]:
            if field in data:
                setattr(item, field, data[field])
        item.version += 1
        item.save()
        return JsonResponse(serialize_template(item))
    if request.method == "DELETE":
        item.is_active = False
        item.save()
        return JsonResponse({"message": "Template deactivated"})
    return json_error("Method not allowed", 405)


@token_required(required_roles=["Admin", "ResearchOfficer", "EditorialBoard", "InternalReviewer", "ExternalReviewer"])
def template_download(request, template_id):
    if request.method != "GET":
        return json_error("Method not allowed", 405)
    try:
        item = ContentTemplate.objects.get(id=template_id, is_active=True)
    except ContentTemplate.DoesNotExist:
        return json_error("Template not found", 404)
    if not item.file:
        return json_error("Template file not found", 404)
    return FileResponse(item.file.open("rb"), as_attachment=True, filename=Path(item.file.name).name)
