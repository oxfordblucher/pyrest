from dataclasses import dataclass
from typing import Any

from scryapi.errors import ValidationError
from scryapi.formats import FORMATS, Format
from scryapi.models import Deck
from scryapi.models.deck import BOARDS
from scryapi.schemas import Errors, Json, iso
from scryapi.schemas.card import dump_card_summary
from scryapi.services.legality import check_deck

MAX_NAME = 100
MAX_DESCRIPTION = 2000
MAX_ENTRIES = 250
MAX_QUANTITY = 99

_UNSET = object()


@dataclass(frozen=True)
class DeckChanges:
    """Fields to set on a deck: only the ones present in the request body."""

    fields: dict[str, Any]


@dataclass(frozen=True)
class DeckEntry:
    card_id: str  # Scryfall id
    quantity: int
    board: str


def _optional_text(
    body: Json, field: str, max_length: int, errors: Errors, required: bool = False
) -> Any:
    value = body.get(field, _UNSET)
    if value is _UNSET:
        if required:
            errors.add(field, "is required")
        return _UNSET
    if value is None and not required:
        return None
    if not isinstance(value, str):
        errors.add(field, "must be a string")
        return _UNSET
    value = value.strip()
    if required and not value:
        errors.add(field, "must not be blank")
        return _UNSET
    if len(value) > max_length:
        errors.add(field, f"must be at most {max_length} characters")
        return _UNSET
    return value or None


def _parse_format(body: Json, errors: Errors) -> Any:
    value = body.get("format", _UNSET)
    if value is _UNSET or value is None:
        return value
    key = value.strip().lower() if isinstance(value, str) else None
    if key == "":
        return None
    if key not in FORMATS:
        errors.add("format", "must be a format key from GET /api/formats, or null")
        return _UNSET
    return key


def parse_deck_fields(body: Json, partial: bool) -> DeckChanges:
    """Validate deck metadata. `partial=True` for PATCH (every field optional)."""
    errors = Errors()
    values = {
        "name": _optional_text(body, "name", MAX_NAME, errors, required=not partial),
        "description": _optional_text(body, "description", MAX_DESCRIPTION, errors),
        "format": _parse_format(body, errors),
    }
    if values["name"] is None:  # sent as null or blank
        errors.add("name", "must not be blank")
    is_public = body.get("is_public", _UNSET)
    if is_public is not _UNSET and not isinstance(is_public, bool):
        errors.add("is_public", "must be a boolean")
    values["is_public"] = is_public
    unknown = set(body) - set(values)
    for field in sorted(unknown):
        errors.add(field, "is not a recognised field")
    errors.raise_if_any()
    return DeckChanges(fields={k: v for k, v in values.items() if v is not _UNSET})


def parse_deck_cards(body: Json) -> list[DeckEntry]:
    errors = Errors()
    cards = body.get("cards")
    if not isinstance(cards, list):
        raise ValidationError([{"field": "cards", "message": "must be a list"}])
    if len(cards) > MAX_ENTRIES:
        raise ValidationError(
            [{"field": "cards", "message": f"must have at most {MAX_ENTRIES} entries"}]
        )

    entries: list[DeckEntry] = []
    seen: set[tuple[str, str]] = set()
    for i, item in enumerate(cards):
        field = f"cards[{i}]"
        if not isinstance(item, dict):
            errors.add(field, "must be an object")
            continue
        card_id, quantity, board = item.get("card_id"), item.get("quantity"), item.get("board")
        board = "main" if board is None else board
        if not isinstance(card_id, str) or not card_id:
            errors.add(f"{field}.card_id", "must be a card id")
            continue
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            errors.add(f"{field}.quantity", "must be an integer")
            continue
        if not 1 <= quantity <= MAX_QUANTITY:
            errors.add(f"{field}.quantity", f"must be between 1 and {MAX_QUANTITY}")
            continue
        if board not in BOARDS:
            errors.add(f"{field}.board", f"must be one of {', '.join(BOARDS)}")
            continue
        if (card_id, board) in seen:
            errors.add(field, "duplicates an earlier entry for the same card and board")
            continue
        seen.add((card_id, board))
        entries.append(DeckEntry(card_id=card_id, quantity=quantity, board=board))

    errors.raise_if_any()
    return entries


def dump_deck_summary(deck: Deck, card_count: int) -> Json:
    return {
        "id": deck.id,
        "name": deck.name,
        "format": deck.format,
        "is_public": deck.is_public,
        "owner": deck.user.username,
        "card_count": card_count,
        "created_at": iso(deck.created_at),
        "updated_at": iso(deck.updated_at),
    }


def dump_format(fmt: Format) -> Json:
    return {
        "key": fmt.key,
        "name": fmt.name,
        "kind": str(fmt.kind),
        "deck_size": fmt.deck_size,
        "sideboard_size": fmt.sideboard_size,
        "max_copies": fmt.max_copies,
    }


def dump_deck(deck: Deck) -> Json:
    entries = sorted(deck.entries, key=lambda e: (BOARDS.index(e.board), e.card.sort_name))
    return {
        **dump_deck_summary(deck, sum(e.quantity for e in entries)),
        "description": deck.description,
        "legality": check_deck(deck.format, entries),
        "cards": [
            {"card": dump_card_summary(e.card), "quantity": e.quantity, "board": e.board}
            for e in entries
        ],
    }
