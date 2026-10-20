from scryapi.errors import ApiError
from scryapi.extensions import db
from scryapi.models import Card
from scryapi.search import get_backend
from scryapi.services import contains, paginate


def search_cards(query):
    """Return (cards, total) for a CardQuery. Only active cards are listed."""
    stmt = db.select(Card).where(Card.is_active)
    if query.name:
        stmt = stmt.where(contains(Card.name, query.name))
    if query.type:
        stmt = stmt.where(contains(Card.type_line, query.type))
    if query.text:
        stmt = get_backend().apply_text_filter(stmt, query.text)
    stmt = stmt.order_by(Card.name, Card.id)
    return paginate(stmt, query.page, query.limit)


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
