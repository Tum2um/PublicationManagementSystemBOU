from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from bou_pms.api import json_error, parse_json, token_required
from accounts.models import record_audit
from notifications.models import create_notification
from submissions.models import Call, DocumentVersion, Submission, SubmissionAuthor, Theme


STAFF_ROLES = {"ResearchOfficer", "EditorialBoard", "InternalReviewer", "ExternalReviewer"}


def serialize_call(call):
    return {
        "id": call.id,
        "fiscal_year": call.fiscal_year,
        "description": call.description,
        "abstract_deadline": call.abstract_deadline.isoformat(),
        "paper_deadline": call.paper_deadline.isoformat(),
        "status": call.status,
        "themes": [{"id": theme.id, "name": theme.name} for theme in call.themes.all()],
    }


def tracking_steps(submission):
    stages = [
        ("submitted", "Submitted"),
        ("assigned_internal_reviewer", "Internal reviewer assigned"),
        ("internal_review", "Internal review"),
        ("author_revision", "Author revision"),
        ("revised_submission", "Revision submitted"),
        ("external_review", "External review if needed"),
        ("editorial_board", "Editorial Board"),
        ("published", "Publication decision"),
    ]
    current_index = 0
    for index, (key, _label) in enumerate(stages):
        if submission.current_stage == key or submission.status == key:
            current_index = index
            break
    if submission.status in ["approved_for_publishing", "published", "declined"]:
        current_index = len(stages) - 1
    return [
        {
            "key": key,
            "label": label,
            "state": "completed" if index < current_index else "current" if index == current_index else "pending",
        }
        for index, (key, label) in enumerate(stages)
    ]


def serialize_submission(submission, include_details=False):
    result = {
        "id": submission.id,
        "title": submission.title,
        "status": submission.status,
        "current_stage": submission.current_stage,
        "call_id": submission.call_id,
        "theme_id": submission.theme_id,
        "theme_name": submission.theme.name,
        "corresponding_author_id": submission.corresponding_author_id,
        "corresponding_author": {
            "name": submission.corresponding_author.get_full_name() or submission.corresponding_author.email,
            "email": submission.corresponding_author.email,
        },
        "author_emails": list(submission.authors.values_list("email", flat=True)),
        "decision_reason": submission.decision_reason,
        "publication_reference": submission.publication_reference,
        "publication_date": submission.publication_date.isoformat() if submission.publication_date else None,
        "created_at": submission.created_at.isoformat(),
        "tracking_steps": tracking_steps(submission),
        "call": {
            "id": submission.call_id,
            "fiscal_year": submission.call.fiscal_year,
            "abstract_deadline": submission.call.abstract_deadline.isoformat(),
            "paper_deadline": submission.call.paper_deadline.isoformat(),
            "status": submission.call.status,
        },
    }
    if include_details:
        result["authors"] = [
            {
                "id": author.id,
                "name": author.name,
                "email": author.email,
                "is_bou_staff": author.is_bou_staff,
                "department_id": author.department_id,
                "institution": author.institution,
                "is_corresponding": author.is_corresponding,
            }
            for author in submission.authors.all()
        ]
        result["documents"] = [
            {
                "id": document.id,
                "type": document.doc_type,
                "file_path": document.file.url if document.file else "",
                "uploaded_at": document.uploaded_at.isoformat(),
                "version_number": document.version_number,
            }
            for document in submission.documents.all()
        ]
    return result


@csrf_exempt
@token_required()
def calls(request):
    if request.method == "GET":
        return JsonResponse([serialize_call(call) for call in Call.objects.prefetch_related("themes").all().order_by("-id")], safe=False)

    if request.method == "POST":
        if "ResearchOfficer" not in request.user_roles:
            return json_error("Permission denied", 403)
        data = parse_json(request)
        if data is None:
            return json_error("Invalid JSON", 400)
        required = ["fiscal_year", "description", "abstract_deadline", "paper_deadline"]
        if not all(data.get(field) for field in required):
            return json_error("Missing required fields", 400)

        abstract_deadline = parse_datetime(data["abstract_deadline"])
        paper_deadline = parse_datetime(data["paper_deadline"])
        if not abstract_deadline or not paper_deadline:
            return json_error("Invalid date format. Use ISO format.", 400)
        if timezone.is_naive(abstract_deadline):
            abstract_deadline = timezone.make_aware(abstract_deadline)
        if timezone.is_naive(paper_deadline):
            paper_deadline = timezone.make_aware(paper_deadline)
        if paper_deadline <= abstract_deadline:
            return json_error("Paper deadline must be after the abstract deadline", 400)

        call = Call.objects.create(
            fiscal_year=data["fiscal_year"],
            description=data["description"],
            abstract_deadline=abstract_deadline,
            paper_deadline=paper_deadline,
        )
        for theme_name in data.get("themes", []):
            Theme.objects.create(call=call, name=theme_name)
        record_audit(request.user, "Created call for papers", "call", call.id, details=call.fiscal_year)
        return JsonResponse({"message": "Call created", "call_id": call.id}, status=201)

    return json_error("Method not allowed", 405)


@csrf_exempt
@token_required(required_roles=["ResearchOfficer"])
def publish_call(request, call_id):
    if request.method != "PUT":
        return json_error("Method not allowed", 405)
    try:
        call = Call.objects.get(id=call_id)
    except Call.DoesNotExist:
        return json_error("Call not found", 404)
    call.status = "published"
    call.save()
    record_audit(request.user, "Published call for papers", "call", call.id, details=call.fiscal_year)
    return JsonResponse({"message": "Call published"})


@csrf_exempt
@token_required(required_roles=["ResearchOfficer"])
def call_detail(request, call_id):
    if request.method != "PUT":
        return json_error("Method not allowed", 405)
    try:
        call = Call.objects.prefetch_related("themes").get(id=call_id)
    except Call.DoesNotExist:
        return json_error("Call not found", 404)
    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)
    for field in ["abstract_deadline", "paper_deadline"]:
        if field in data:
            value = parse_datetime(data[field])
            if not value:
                return json_error(f"Invalid {field.replace('_', ' ')}", 400)
            if timezone.is_naive(value):
                value = timezone.make_aware(value)
            setattr(call, field, value)
    if data.get("status"):
        if data["status"] not in ["draft", "published", "closed"]:
            return json_error("Invalid call status", 400)
        call.status = data["status"]
    call.save()
    return JsonResponse({"message": "Call updated", "call": serialize_call(call)})


@csrf_exempt
@token_required()
def submissions(request):
    if request.method == "GET":
        if STAFF_ROLES.intersection(request.user_roles):
            query = Submission.objects.select_related("call", "theme").all()
        else:
            query = Submission.objects.select_related("call", "theme").filter(corresponding_author=request.user)
        return JsonResponse([serialize_submission(item) for item in query.order_by("-id")], safe=False)

    if request.method == "POST":
        if "Author" not in request.user_roles:
            return json_error("Permission denied", 403)
        data = parse_json(request)
        if data is None:
            return json_error("Invalid JSON", 400)
        if not all(field in data for field in ["call_id", "theme_id", "title", "authors"]):
            return json_error("Missing required fields", 400)
        if not str(data["title"]).strip() or not isinstance(data["authors"], list) or not data["authors"]:
            return json_error("A title and at least one author are required", 400)
        for author_data in data["authors"]:
            if not author_data.get("name") or not author_data.get("email"):
                return json_error("Every author requires a name and email", 400)
            try:
                validate_email(author_data["email"])
            except ValidationError:
                return json_error(f'Invalid author email: {author_data["email"]}', 400)
            if author_data.get("is_bou_staff") and not author_data.get("department_id"):
                return json_error("BOU staff authors require a department", 400)
            if not author_data.get("is_bou_staff") and not author_data.get("institution"):
                return json_error("External authors require an institution", 400)
        try:
            call = Call.objects.get(id=data["call_id"], status="published")
            theme = Theme.objects.get(id=data["theme_id"], call=call)
        except (Call.DoesNotExist, Theme.DoesNotExist):
            return json_error("Call or theme not available", 400)

        submission = Submission.objects.create(
            call=call,
            theme=theme,
            title=data["title"],
            corresponding_author=request.user,
        )
        for index, author_data in enumerate(data["authors"]):
            SubmissionAuthor.objects.create(
                submission=submission,
                name=author_data["name"],
                email=author_data["email"],
                is_bou_staff=author_data.get("is_bou_staff", False),
                department_id=author_data.get("department_id"),
                institution=author_data.get("institution", ""),
                is_corresponding=author_data.get("is_corresponding", index == 0),
            )
        create_notification(
            request.user.id,
            "Submission received",
            f'Your submission "{submission.title}" has been received and is awaiting review.',
            "submission",
            submission.id,
        )
        record_audit(request.user, "Created submission", "submission", submission.id, details=submission.title)
        return JsonResponse({"message": "Submission created", "submission_id": submission.id}, status=201)

    return json_error("Method not allowed", 405)


@csrf_exempt
@token_required()
def submission_detail(request, submission_id):
    try:
        submission = Submission.objects.select_related("call", "theme").get(id=submission_id)
    except Submission.DoesNotExist:
        return json_error("Submission not found", 404)

    if submission.corresponding_author_id != request.user.id and not STAFF_ROLES.intersection(request.user_roles):
        return json_error("Permission denied", 403)

    if request.method == "GET":
        return JsonResponse(serialize_submission(submission, include_details=True))

    if request.method == "PUT":
        if submission.corresponding_author_id != request.user.id:
            return json_error("You can only edit your own submissions", 403)
        if submission.status in ["approved_for_publishing", "published", "declined"]:
            return json_error("This submission can no longer be edited", 400)
        data = parse_json(request)
        if data is None:
            return json_error("Invalid JSON", 400)
        if data.get("title"):
            submission.title = data["title"]
        if data.get("theme_id"):
            try:
                submission.theme = Theme.objects.get(id=data["theme_id"], call=submission.call)
            except Theme.DoesNotExist:
                return json_error("Invalid theme for this call", 400)
        if isinstance(data.get("authors"), list) and data["authors"]:
            submission.authors.all().delete()
            for index, author_data in enumerate(data["authors"]):
                SubmissionAuthor.objects.create(
                    submission=submission,
                    name=author_data["name"],
                    email=author_data["email"],
                    is_bou_staff=author_data.get("is_bou_staff", False),
                    department_id=author_data.get("department_id"),
                    institution=author_data.get("institution", ""),
                    is_corresponding=author_data.get("is_corresponding", index == 0),
                )
        if data.get("is_revision"):
            submission.current_stage = "revised_submission"
        submission.status = "submitted"
        submission.save()
        return JsonResponse({"message": "Submission updated", "submission": serialize_submission(submission, True)})

    if request.method == "DELETE":
        if submission.corresponding_author_id != request.user.id:
            return json_error("You can only delete your own submissions", 403)
        if submission.status in ["approved_for_publishing", "published", "declined"]:
            return json_error("This submission can no longer be deleted", 400)
        submission.delete()
        return JsonResponse({"message": "Submission deleted"})

    return json_error("Method not allowed", 405)


@csrf_exempt
@token_required(required_roles=["ResearchOfficer", "EditorialBoard"])
def submission_status(request, submission_id):
    if request.method != "PUT":
        return json_error("Method not allowed", 405)
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        return json_error("Submission not found", 404)
    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)
    allowed_statuses = {
        "submitted", "assigned_internal_reviewer", "internal_review", "author_revision",
        "revised_submission", "external_review", "editorial_board",
        "approved_for_publishing", "published", "declined",
    }
    if data.get("status") and data["status"] not in allowed_statuses:
        return json_error("Invalid submission status", 400)
    final_statuses = {"approved_for_publishing", "published", "declined"}
    if data.get("status") in final_statuses and "EditorialBoard" not in request.user_roles:
        return json_error("Only the Editorial Board can record a final decision", 403)
    if data.get("status"):
        submission.status = data["status"]
    if data.get("current_stage"):
        submission.current_stage = data["current_stage"]
    if "reason" in data:
        submission.decision_reason = data["reason"]
    if data.get("publication_reference"):
        submission.publication_reference = data["publication_reference"].strip()
    if data.get("status") == "published":
        submission.publication_date = timezone.localdate()
    submission.save()
    record_audit(request.user, "Updated submission status", "submission", submission.id, details=submission.status)
    if data.get("notify_author", True):
        create_notification(
            submission.corresponding_author_id,
            data.get("title", "Submission status updated"),
            data.get("message") or f'Your submission "{submission.title}" is now at {submission.current_stage}.',
            "decision",
            submission.id,
        )
    return JsonResponse({"message": "Submission status updated", "submission": serialize_submission(submission, True)})


def publications(request):
    if request.method != "GET":
        return json_error("Method not allowed", 405)
    query = Submission.objects.select_related("call", "theme", "corresponding_author").filter(status="published").order_by("-publication_date", "-id")
    return JsonResponse([
        {
            "id": item.id,
            "title": item.title,
            "theme_name": item.theme.name,
            "fiscal_year": item.call.fiscal_year,
            "author": item.corresponding_author.get_full_name() or item.corresponding_author.email,
            "publication_reference": item.publication_reference,
            "publication_date": item.publication_date.isoformat() if item.publication_date else None,
            "paper": next((doc.file.url for doc in item.documents.filter(doc_type__in=["paper", "revision"]).order_by("-version_number", "-id") if doc.file), ""),
        }
        for item in query
    ], safe=False)


@csrf_exempt
@token_required(required_roles=["Author"])
def submission_documents(request, submission_id):
    if request.method != "POST":
        return json_error("Method not allowed", 405)
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        return json_error("Submission not found", 404)
    if submission.corresponding_author_id != request.user.id:
        return json_error("You can only upload documents for your own submissions", 403)
    uploaded_file = request.FILES.get("file")
    doc_type = request.POST.get("doc_type")
    if not uploaded_file:
        return json_error("No file part", 400)
    if doc_type not in ["abstract", "paper", "revision"]:
        return json_error("doc_type must be abstract, paper, or revision", 400)
    if uploaded_file.size > 10 * 1024 * 1024:
        return json_error("File too large. Max 10 MB", 400)
    if not uploaded_file.name.lower().endswith((".pdf", ".docx")):
        return json_error("File type not allowed. Allowed: pdf, docx", 400)

    path = default_storage.save(f"submission_documents/{submission.id}_{doc_type}_{uploaded_file.name}", uploaded_file)
    document = DocumentVersion.objects.create(
        submission=submission,
        doc_type=doc_type,
        file=path,
        uploaded_by=request.user,
        version_number=(submission.documents.filter(doc_type=doc_type).aggregate(Max("version_number"))["version_number__max"] or 0) + 1,
    )
    if doc_type == "revision":
        submission.status = "revised_submission"
        submission.current_stage = "revised_submission"
        submission.save()
    record_audit(request.user, "Uploaded submission document", "submission", submission.id, details=f"{doc_type} v{document.version_number}")
    create_notification(
        request.user.id,
        "Document uploaded",
        f'Your {doc_type} document for "{submission.title}" has been uploaded successfully.',
        "document",
        submission.id,
    )
    return JsonResponse({"message": "File uploaded", "document_id": document.id}, status=201)
