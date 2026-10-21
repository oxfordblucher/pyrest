from typing import Any

from sqlalchemy import ColumnElement, Select

from scryapi.extensions import db


def escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input matches literally (use with escape="\\")."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains(column: Any, value: str) -> ColumnElement[bool]:
    return column.ilike(f"%{escape_like(value)}%", escape="\\")


def starts_with(column: Any, value: str) -> ColumnElement[bool]:
    return column.ilike(f"{escape_like(value)}%", escape="\\")


def paginate[T](stmt: Select[tuple[T]], page: int, limit: int) -> tuple[list[T], int]:
    """Return (items, total) for a select of ORM entities."""
    total = db.session.execute(
        db.select(db.func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    items = db.session.execute(stmt.offset((page - 1) * limit).limit(limit)).scalars().all()
    return list(items), total
