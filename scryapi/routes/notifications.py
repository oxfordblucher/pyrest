from flask import Blueprint, request
from flask_login import current_user, login_required

from scryapi.schemas import Errors, paginated, parse_pagination
from scryapi.schemas.notification import dump_notification
from scryapi.services import notifications as notification_service

notificationsbp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notificationsbp.get("")
@login_required
def list_notifications():
    errors = Errors()
    page, limit = parse_pagination(request.args, errors)
    unread = request.args.get("unread", "false").lower()
    if unread not in ("true", "false"):
        errors.add("unread", "must be true or false")
    errors.raise_if_any("Invalid query parameters")
    items, total = notification_service.list_for(current_user, page, limit, unread == "true")
    return paginated(page, limit, total, [dump_notification(n) for n in items])


@notificationsbp.post("/<int:notification_id>/read")
@login_required
def mark_read(notification_id):
    return dump_notification(notification_service.mark_read(current_user, notification_id))


@notificationsbp.post("/read-all")
@login_required
def mark_all_read():
    notification_service.mark_all_read(current_user)
    return "", 204
