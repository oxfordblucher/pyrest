from flask import Blueprint, jsonify, request
from extensions import db
from models.card import Card

cardsbp = Blueprint('cards', __name__, url_prefix='/api/cards')

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

@cardsbp.get('/')
def get_cards():
    stmt = db.select(Card)

    for param, filter_fn in FILTER_MAP.items():
        if value := request.args.get(param):
            stmt = stmt.where(filter_fn(value))

    if search := request.args.get("text"):
        stmt = stmt.join(cards_fts, Card.id == cards_fts.c.rowid).where(cards_fts.c.oracle_text.match(search))

    try:
        limit = min(int(request.args.get("limit", 20)), 50)
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        limit = 20
        page = 1

    stmt = stmt.offset((page - 1) * limit).limit(limit).order_by(Card.name)

    cards = db.session.execute(stmt).scalars().all()
    res = [row.to_dict() for row in cards]
    return jsonify({
        "page": page,
        "limit": limit,
        "results": res
    })

@cardsbp.get('/<id>')
def get_card_by_id(id):
    card = db.get_or_404(Card, id)
    res = card.to_dict()
    return jsonify(res)
