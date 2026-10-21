from scryapi.errors import ApiError
from scryapi.extensions import db
from scryapi.models import Card
from scryapi.models.card import name_key
from scryapi.search import get_backend
from scryapi.services import contains, paginate, starts_with


def search_cards(query):
    """Return (cards, total) for a CardQuery. Only active cards are listed."""
    stmt = db.select(Card).where(Card.is_active)
    if query.name:
        key = name_key(query.name)
        stmt = stmt.where(contains(Card.sort_name, key)).order_by(name_rank(key))
    if query.type:
        stmt = stmt.where(contains(Card.type_line, query.type))
    if query.text:
        stmt = get_backend().apply_text_filter(stmt, query.text)
    stmt = stmt.order_by(Card.sort_name, Card.id)
    return paginate(stmt, query.page, query.limit)


def name_rank(key):
    """Exact name matches first, then names starting with the term, then the rest."""
    return db.case(
        (Card.sort_name == key, 0),
        (starts_with(Card.sort_name, key), 1),
        else_=2,
    )


def get_card(scryfall_id):
    """Fetch by public id. Inactive cards are still returned: decks may reference them."""
    card = db.session.execute(
        db.select(Card).where(Card.scryfall_id == scryfall_id)
    ).scalar_one_or_none()
    if card is None:
        raise ApiError(404, "not_found", "Card not found")
    return card


def get_cards_by_scryfall_ids(scryfall_ids):
    if not scryfall_ids:
        return {}
    cards = db.session.execute(db.select(Card).where(Card.scryfall_id.in_(scryfall_ids))).scalars()
    return {c.scryfall_id: c for c in cards}
