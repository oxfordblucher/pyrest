from dataclasses import dataclass

from scryapi.schemas import Errors, parse_pagination, parse_text


@dataclass(frozen=True)
class CardQuery:
    page: int = 1
    limit: int = 20
    name: str | None = None
    type: str | None = None
    text: str | None = None


def parse_card_query(args):
    errors = Errors()
    page, limit = parse_pagination(args, errors)
    query = CardQuery(
        page=page,
        limit=limit,
        name=parse_text(args, "name", errors),
        type=parse_text(args, "type", errors),
        text=parse_text(args, "text", errors),
    )
    errors.raise_if_any("Invalid query parameters")
    return query


def dump_card(card):
    return {
        "id": card.scryfall_id,
        "name": card.name,
        "mana_cost": card.mana_cost,
        "cmc": card.cmc,
        "type_line": card.type_line,
        "oracle_text": card.oracle_text,
        "power": card.power,
        "toughness": card.toughness,
        "loyalty": card.loyalty,
        "colors": card.colors,
        "color_identity": card.color_identity,
        "layout": card.layout,
        "card_faces": card.card_faces,
        "image_uri": card.image_uri,
        "scryfall_uri": card.scryfall_uri,
    }


def dump_card_summary(card):
    return {
        "id": card.scryfall_id,
        "name": card.name,
        "mana_cost": card.mana_cost,
        "type_line": card.type_line,
    }
