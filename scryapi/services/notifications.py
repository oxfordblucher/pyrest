from datetime import UTC, datetime

from scryapi.errors import ApiError
from scryapi.extensions import db
from scryapi.models import Notification, User
from scryapi.services import paginate


def list_for(
    user: User, page: int, limit: int, unread_only: bool
) -> tuple[list[Notification], int]:
    stmt = db.select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
    return paginate(stmt, page, limit)


def unread_count(user: User) -> int:
    return db.session.execute(
        db.select(db.func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ).scalar_one()


def mark_read(user: User, notification_id: int) -> Notification:
    notification = db.session.get(Notification, notification_id)
    # Someone else's notification looks the same as a missing one.
    if notification is None or notification.user_id != user.id:
        raise ApiError(404, "not_found", "Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        db.session.commit()
    return notification


def mark_all_read(user: User) -> None:
    db.session.execute(
        db.update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.session.commit()
