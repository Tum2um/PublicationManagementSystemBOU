from django.urls import path

from accounts import views as account_views
from masterdata import views as masterdata_views
from notifications import views as notification_views
from reviews import views as review_views
from submissions import views as submission_views


urlpatterns = [
    path("health", account_views.health),
    path("api/auth/login", account_views.login),
    path("api/auth/logout", account_views.logout),
    path("api/auth/me", account_views.me),
    path("api/users", account_views.users),
    path("api/users/<int:user_id>", account_views.user_detail),
    path("api/audit-logs", account_views.audit_logs),
    path("api/departments", masterdata_views.departments),
    path("api/departments/<int:department_id>", masterdata_views.department_detail),
    path("api/themes", masterdata_views.themes),
    path("api/themes/<int:theme_id>", masterdata_views.theme_detail),
    path("api/templates", masterdata_views.templates),
    path("api/templates/<int:template_id>", masterdata_views.template_detail),
    path("api/templates/<int:template_id>/download", masterdata_views.template_download),
    path("api/calls", submission_views.calls),
    path("api/calls/<int:call_id>/publish", submission_views.publish_call),
    path("api/calls/<int:call_id>", submission_views.call_detail),
    path("api/submissions", submission_views.submissions),
    path("api/submissions/<int:submission_id>", submission_views.submission_detail),
    path("api/submissions/<int:submission_id>/status", submission_views.submission_status),
    path("api/submissions/<int:submission_id>/documents", submission_views.submission_documents),
    path("api/documents/<int:document_id>/download", submission_views.document_download),
    path("api/publications", submission_views.publications),
    path("api/review-assignments", review_views.review_assignments),
    path("api/review-assignments/<int:assignment_id>/verify", review_views.verify_assignment),
    path("api/review-assignments/<int:assignment_id>/comments", review_views.assignment_comments),
    path("api/review-comments/<int:comment_id>/verify", review_views.verify_comment),
    path("notifications", notification_views.notifications),
    path("notifications/user/<int:user_id>", notification_views.user_notifications),
    path("notifications/user/<int:user_id>/unread-count", notification_views.unread_count),
    path("notifications/user/<int:user_id>/read-all", notification_views.read_all),
    path("notifications/<int:notification_id>/read", notification_views.mark_read),
    path("notifications/<int:notification_id>/unread", notification_views.mark_unread),
    path("notifications/<int:notification_id>", notification_views.notification_detail),
]
