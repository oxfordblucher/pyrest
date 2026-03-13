from extensions import db
from models import Card
from flask import request
from sanitation.req_sani import PageSanitizer

FILTER_MAP = {
    "name": lambda v: Card.name.ilike(f"%{v}%"),
    "type": lambda v: Card.type_line.ilike(f"%{v}%"),
}

cards_fts = db.Table(
    "cards_fts",
    db.metadata,
    db.Column("rowid", db.String),
    db.Column("oracle_text", db.Text)
)

def get_card_data(limit, page):
    sani = PageSanitizer(req=request)
    sani.check_pagination()
    sani.throw_errors()

    stmt = db.select(Card)

    for param, filter_fn in FILTER_MAP.items():
        if value := request.args.get(param):
            stmt = stmt.where(filter_fn(value))

    if search := request.args.get("text"):
        stmt = stmt.join(cards_fts, Card.id == cards_fts.c.rowid).where(cards_fts.c.oracle_text.match(search))

    stmt = stmt.offset((page - 1) * limit).limit(limit).order_by(Card.name)
    cards = db.session.execute(stmt).scalars().all()
    return cards