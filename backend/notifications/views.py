from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from bou_pms.api import json_error, parse_json, token_required
from notifications.models import Notification, create_notification


def serialize_notification(notification):
    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "title": notification.title,
        "message": notification.message,
        "notification_type": notification.notification_type,
        "related_submission_id": notification.related_submission_id,
        "channel": notification.channel,
        "email_sent": notification.email_sent,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
    }


@csrf_exempt
@token_required(required_roles=["Admin"])
def notifications(request):
    if request.method != "POST":
        return json_error("Method not allowed", 405)
    data = parse_json(request)
    if data is None:
        return json_error("Invalid JSON", 400)
    required = ["user_id", "title", "message"]
    if not all(data.get(field) for field in required):
        return json_error("user_id, title and message are required", 400)
    notification = create_notification(
        data["user_id"],
        data["title"],
        data["message"],
        data.get("notification_type", "info"),
        data.get("related_submission_id"),
    )
    return JsonResponse({"message": "Notification created successfully", "notification_id": notification.id}, status=201)


@token_required()
def user_notifications(request, user_id):
    if request.user.id != user_id and "Admin" not in request.user_roles:
        return json_error("Permission denied", 403)
    unread_only = request.GET.get("unread_only") == "true"
    query = Notification.objects.filter(user_id=user_id)
    if unread_only:
        query = query.filter(is_read=False)
    return JsonResponse({
        "user_id": user_id,
        "notifications": [serialize_notification(item) for item in query],
    })


@token_required()
def unread_count(request, user_id):
    if request.user.id != user_id and "Admin" not in request.user_roles:
        return json_error("Permission denied", 403)
    return JsonResponse({
        "user_id": user_id,
        "unread_count": Notification.objects.filter(user_id=user_id, is_read=False).count(),
    })


@csrf_exempt
@token_required()
def mark_read(request, notification_id):
    return update_read_state(request, notification_id, True)


@csrf_exempt
@token_required()
def mark_unread(request, notification_id):
    return update_read_state(request, notification_id, False)


def update_read_state(request, notification_id, is_read):
    if request.method != "PUT":
        return json_error("Method not allowed", 405)
    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        return json_error("Notification not found", 404)
    if notification.user_id != request.user.id and "Admin" not in request.user_roles:
        return json_error("Permission denied", 403)
    notification.is_read = is_read
    notification.save()
    return JsonResponse({"message": "Notification updated", "notification_id": notification.id})


@csrf_exempt
@token_required()
def read_all(request, user_id):
    if request.method != "PUT":
        return json_error("Method not allowed", 405)
    if request.user.id != user_id and "Admin" not in request.user_roles:
        return json_error("Permission denied", 403)
    Notification.objects.filter(user_id=user_id).update(is_read=True)
    return JsonResponse({"message": "All notifications marked as read", "user_id": user_id})


@csrf_exempt
@token_required()
def notification_detail(request, notification_id):
    if request.method != "DELETE":
        return json_error("Method not allowed", 405)
    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        return json_error("Notification not found", 404)
    if notification.user_id != request.user.id and "Admin" not in request.user_roles:
        return json_error("Permission denied", 403)
    notification.delete()
    return JsonResponse({"message": "Notification deleted", "notification_id": notification_id})
