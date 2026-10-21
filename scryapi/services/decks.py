from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm import selectinload

from scryapi.errors import ApiError, ValidationError
from scryapi.extensions import db
from scryapi.models import Deck, DeckCard, User
from scryapi.schemas.deck import DeckChanges, DeckEntry
from scryapi.services import paginate
from scryapi.services.cards import get_cards_by_scryfall_ids

type DeckPage = tuple[list[tuple[Deck, int]], int]


def _not_found() -> ApiError:
    return ApiError(404, "not_found", "Deck not found")


def _with_counts(decks: Sequence[Deck]) -> list[tuple[Deck, int]]:
    """Pair each deck with its total card quantity, in one query."""
    if not decks:
        return []
    rows = db.session.execute(
        db.select(DeckCard.deck_id, db.func.sum(DeckCard.quantity))
        .where(DeckCard.deck_id.in_([d.id for d in decks]))
        .group_by(DeckCard.deck_id)
    )
    counts = {deck_id: total for deck_id, total in rows}
    return [(d, counts.get(d.id, 0)) for d in decks]


def _list(stmt: Select[tuple[Deck]], page: int, limit: int) -> DeckPage:
    stmt = stmt.options(selectinload(Deck.user)).order_by(Deck.updated_at.desc(), Deck.id.desc())
    decks, total = paginate(stmt, page, limit)
    return _with_counts(decks), total


def list_public(page: int, limit: int) -> DeckPage:
    return _list(db.select(Deck).where(Deck.is_public), page, limit)


def list_public_for_user(user: User, page: int, limit: int) -> DeckPage:
    return _list(db.select(Deck).where(Deck.is_public, Deck.user_id == user.id), page, limit)


def list_owned(user: User, page: int, limit: int) -> DeckPage:
    return _list(db.select(Deck).where(Deck.user_id == user.id), page, limit)


def _load(deck_id: int) -> Deck | None:
    return db.session.execute(
        db.select(Deck)
        .where(Deck.id == deck_id)
        .options(selectinload(Deck.user), selectinload(Deck.entries).selectinload(DeckCard.card))
    ).scalar_one_or_none()


def _reload(deck_id: int) -> Deck:
    deck = _load(deck_id)
    assert deck is not None  # just written in this session
    return deck


def get_visible(deck_id: int, user: Any) -> Deck:
    """A deck the user may read: their own, or any public deck. Private decks of other
    users are reported as missing so their existence isn't revealed."""
    deck = _load(deck_id)
    if deck is None or not (deck.is_public or _owns(user, deck)):
        raise _not_found()
    return deck


def get_owned(deck_id: int, user: Any) -> Deck:
    """A deck the user may change. Someone else's public deck is 403; private is 404."""
    deck = get_visible(deck_id, user)
    if not _owns(user, deck):
        raise ApiError(403, "forbidden", "Only the deck's owner can change it")
    return deck


def _owns(user: Any, deck: Deck) -> bool:
    return user.is_authenticated and deck.user_id == user.id


def create(user: User, changes: DeckChanges) -> Deck:
    deck = Deck(user=user, **changes.fields)
    db.session.add(deck)
    db.session.commit()
    return _reload(deck.id)


def update(deck: Deck, changes: DeckChanges) -> Deck:
    for field, value in changes.fields.items():
        setattr(deck, field, value)
    db.session.commit()
    return _reload(deck.id)


def replace_cards(deck: Deck, entries: list[DeckEntry]) -> Deck:
    """Replace the deck's whole card list atomically."""
    cards = get_cards_by_scryfall_ids({e.card_id for e in entries})
    unknown = [
        {"field": f"cards[{i}].card_id", "message": "is not a known card"}
        for i, e in enumerate(entries)
        if e.card_id not in cards
    ]
    if unknown:
        raise ValidationError(unknown, "Unknown cards")

    deck.entries = [
        DeckCard(card_id=cards[e.card_id].id, quantity=e.quantity, board=e.board) for e in entries
    ]
    # The deck row itself may be unchanged, so onupdate wouldn't fire.
    deck.updated_at = datetime.now(UTC)
    db.session.commit()
    db.session.expire(deck)
    return _reload(deck.id)


def delete(deck: Deck) -> None:
    db.session.delete(deck)
    db.session.commit()
