from scryapi.extensions import db


def escape_like(value):
    """Escape LIKE wildcards so user input matches literally (use with escape="\\")."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains(column, value):
    return column.ilike(f"%{escape_like(value)}%", escape="\\")


def starts_with(column, value):
    return column.ilike(f"{escape_like(value)}%", escape="\\")


def paginate(stmt, page, limit):
    """Return (items, total) for a select of ORM entities."""
    total = db.session.execute(
        db.select(db.func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    items = db.session.execute(stmt.offset((page - 1) * limit).limit(limit)).scalars().all()
    return items, total
