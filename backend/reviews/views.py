from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from bou_pms.api import json_error, parse_json, token_required
from accounts.models import record_audit
from notifications.models import create_notification
from reviews.models import ReviewAssignment, ReviewComment
from submissions.models import Submission


def serialize_comment(comment):
    return {
        "id": comment.id,
        "recommendation": comment.recommendation,
        "comments": comment.comments,
        "verification_status": comment.verification_status,
        "verification_reason": comment.verification_reason,
        "submitted_at": comment.submitted_at.isoformat(),
    }


def serialize_assignment(assignment):
    return {
        "id": assignment.id,
        "submission_id": assignment.submission_id,
        "reviewer_id": assignment.reviewer_id,
        "reviewer_name": assignment.reviewer.get_full_name() or assignment.reviewer.email,
        "reviewer_email": assignment.reviewer.email,
        "submission_title": assignment.submission.title,
        "reviewer_type": assignment.reviewer_type,
        "status": assignment.status,
        "assigned_by": assignment.assigned_by_id,
        "verified_by": assignment.verified_by_id,
        "verify_reason": assignment.verify_reason,
        "created_at": assignment.created_at.isoformat(),
        "comments": [serialize_comment(comment) for comment in assignment.comments.all()],
    }


@csrf_exempt
@token_required()
def review_assignments(request):
    if request.method == "GET":
        query = ReviewAssignment.objects.select_related("submission", "reviewer").prefetch_related("comments")
        if {"InternalReviewer", "ExternalReviewer"}.intersection(request.user_roles):
            query = query.filter(reviewer=request.user)
        return JsonResponse([serialize_assignment(item) for item in query.order_by("-id")], safe=False)

    if request.method == "POST":
        if "ResearchOfficer" not in request.user_roles:
            return json_error("Permission denied", 403)
        data = parse_json(request)
        if data is None:
            return json_error("Invalid JSON", 400)
        required = ["submission_id", "reviewer_id", "reviewer_type"]
        if not all(data.get(field) for field in required):
            return json_error("submission_id, reviewer_id and reviewer_type are required", 400)
        if data["reviewer_type"] not in ["internal", "external"]:
            return json_error("reviewer_type must be internal or external", 400)
        try:
            submission = Submission.objects.get(id=data["submission_id"])
        except Submission.DoesNotExist:
            return json_error("Submission not found", 404)
        try:
            reviewer = User.objects.get(id=data["reviewer_id"], is_active=True)
        except User.DoesNotExist:
            return json_error("Reviewer not found", 404)
        required_role = "InternalReviewer" if data["reviewer_type"] == "internal" else "ExternalReviewer"
        if not reviewer.groups.filter(name=required_role).exists():
            return json_error(f"Selected user is not an {required_role}", 400)
        author_emails = {email.lower() for email in submission.authors.values_list("email", flat=True)}
        author_emails.add(submission.corresponding_author.email.lower())
        if reviewer.email.lower() in author_emails:
            return json_error("Conflict of interest: the reviewer is an author or co-author", 409)
        if ReviewAssignment.objects.filter(submission=submission, reviewer=reviewer, reviewer_type=data["reviewer_type"]).exclude(status="returned_to_research_officer").exists():
            return json_error("This reviewer is already assigned to the submission", 409)
        assignment = ReviewAssignment.objects.create(
            submission=submission,
            reviewer=reviewer,
            reviewer_type=data["reviewer_type"],
            assigned_by=request.user,
        )
        submission.current_stage = "assigned_internal_reviewer" if data["reviewer_type"] == "internal" else "external_review"
        submission.status = submission.current_stage
        submission.save()
        create_notification(
            request.user.id,
            "Reviewer assignment created",
            f'{data["reviewer_type"].title()} reviewer assignment is awaiting Editorial Board verification.',
            "review",
            submission.id,
        )
        record_audit(request.user, "Created reviewer assignment", "review_assignment", assignment.id, details=data["reviewer_type"])
        return JsonResponse({
            "message": "Review assignment created",
            "assignment_id": assignment.id,
            "status": assignment.status,
        }, status=201)

    return json_error("Method not allowed", 405)


@csrf_exempt
@token_required(required_roles=["EditorialBoard"])
def verify_assignment(request, assignment_id):
    if request.method != "PUT":
        return json_error("Method not allowed", 405)
    try:
        assignment = ReviewAssignment.objects.select_related("submission").get(id=assignment_id)
    except ReviewAssignment.DoesNotExist:
        return json_error("Review assignment not found", 404)
    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)
    approved = bool(data.get("approved"))
    assignment.status = "verified" if approved else "returned_to_research_officer"
    assignment.verified_by = request.user
    assignment.verify_reason = data.get("reason", "")
    assignment.save()
    record_audit(request.user, "Verified reviewer assignment", "review_assignment", assignment.id, details=assignment.status)
    if approved:
        assignment.submission.current_stage = "internal_review" if assignment.reviewer_type == "internal" else "external_review"
        assignment.submission.status = assignment.submission.current_stage
        assignment.submission.save()
        create_notification(
            assignment.reviewer_id,
            "Paper assigned for review",
            "A paper has been assigned to you for review.",
            "review",
            assignment.submission_id,
        )
    else:
        create_notification(
            assignment.assigned_by_id,
            "Reviewer assignment returned",
            assignment.verify_reason or "The Editorial Board returned the reviewer assignment.",
            "review",
            assignment.submission_id,
        )
    return JsonResponse({"message": "Assignment verification recorded", "status": assignment.status})


@csrf_exempt
@token_required(required_roles=["InternalReviewer", "ExternalReviewer"])
def assignment_comments(request, assignment_id):
    if request.method != "POST":
        return json_error("Method not allowed", 405)
    try:
        assignment = ReviewAssignment.objects.get(id=assignment_id)
    except ReviewAssignment.DoesNotExist:
        return json_error("Review assignment not found", 404)
    if assignment.reviewer_id != request.user.id:
        return json_error("You can only comment on assignments given to you", 403)
    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)
    if not data.get("recommendation") or not data.get("comments"):
        return json_error("recommendation and comments are required", 400)
    comment = ReviewComment.objects.create(
        assignment=assignment,
        recommendation=data["recommendation"],
        comments=data["comments"],
    )
    assignment.status = "comments_submitted"
    assignment.save()
    record_audit(request.user, "Submitted reviewer comments", "review_comment", comment.id, details=comment.recommendation)
    create_notification(
        assignment.assigned_by_id,
        "Reviewer comments submitted",
        "Reviewer comments are ready for Research Officer verification.",
        "review",
        assignment.submission_id,
    )
    return JsonResponse({"message": "Review comments submitted", "comment_id": comment.id}, status=201)


@csrf_exempt
@token_required(required_roles=["ResearchOfficer"])
def verify_comment(request, comment_id):
    if request.method != "PUT":
        return json_error("Method not allowed", 405)
    try:
        comment = ReviewComment.objects.select_related("assignment").get(id=comment_id)
    except ReviewComment.DoesNotExist:
        return json_error("Review comment not found", 404)
    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)
    approved = bool(data.get("approved"))
    comment.verification_status = "approved" if approved else "returned_to_reviewer"
    comment.verification_reason = data.get("reason", "")
    comment.verified_by = request.user
    comment.save()
    record_audit(request.user, "Verified reviewer comments", "review_comment", comment.id, details=comment.verification_status)
    if not approved:
        comment.assignment.status = "verified"
        comment.assignment.save()
        create_notification(
            comment.assignment.reviewer_id,
            "Review comments returned",
            comment.verification_reason or "Please revise your review comments.",
            "review",
            comment.assignment.submission_id,
        )
    else:
        comment.assignment.status = "comments_verified"
        comment.assignment.save()
        submission = comment.assignment.submission
        needs_revision = "revision" in comment.recommendation.lower()
        if needs_revision:
            submission.status = "author_revision"
            submission.current_stage = "author_revision"
            create_notification(
                submission.corresponding_author_id,
                "Revision requested",
                comment.comments,
                "review",
                submission.id,
            )
        elif comment.assignment.reviewer_type == "external":
            submission.status = "editorial_board"
            submission.current_stage = "editorial_board"
        else:
            submission.status = "internal_review_complete"
            submission.current_stage = "internal_review"
        submission.save()
    return JsonResponse({"message": "Review comment verification recorded", "status": comment.verification_status})
