from flask import Blueprint, request

from scryapi.schemas import paginated
from scryapi.schemas.card import dump_card, parse_card_query
from scryapi.services import cards as card_service

cardsbp = Blueprint("cards", __name__, url_prefix="/api/cards")


@cardsbp.get("")
def list_cards():
    query = parse_card_query(request.args)
    cards, total = card_service.search_cards(query)
    return paginated(query.page, query.limit, total, [dump_card(c) for c in cards])


@cardsbp.get("/<scryfall_id>")
def get_card(scryfall_id):
    return dump_card(card_service.get_card(scryfall_id))
