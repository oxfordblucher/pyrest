from flask import Blueprint, request
from flask_login import current_user, login_required

from scryapi.schemas import Errors, json_body, paginated, parse_pagination
from scryapi.schemas.deck import (
    dump_deck,
    dump_deck_summary,
    parse_deck_cards,
    parse_deck_fields,
)
from scryapi.services import decks as deck_service

decksbp = Blueprint("decks", __name__, url_prefix="/api/decks")


def pagination_args():
    errors = Errors()
    page, limit = parse_pagination(request.args, errors)
    errors.raise_if_any("Invalid query parameters")
    return page, limit


def summaries(page, limit, results):
    pairs, total = results
    return paginated(page, limit, total, [dump_deck_summary(d, n) for d, n in pairs])


@decksbp.get("/public")
def list_public_decks():
    page, limit = pagination_args()
    return summaries(page, limit, deck_service.list_public(page, limit))


@decksbp.get("/mine")
@login_required
def list_my_decks():
    page, limit = pagination_args()
    return summaries(page, limit, deck_service.list_owned(current_user, page, limit))


@decksbp.post("")
@login_required
def create_deck():
    changes = parse_deck_fields(json_body(), partial=False)
    return dump_deck(deck_service.create(current_user, changes)), 201


@decksbp.get("/<int:deck_id>")
def get_deck(deck_id):
    return dump_deck(deck_service.get_visible(deck_id, current_user))


@decksbp.patch("/<int:deck_id>")
@login_required
def update_deck(deck_id):
    deck = deck_service.get_owned(deck_id, current_user)
    changes = parse_deck_fields(json_body(), partial=True)
    return dump_deck(deck_service.update(deck, changes))


@decksbp.delete("/<int:deck_id>")
@login_required
def delete_deck(deck_id):
    deck_service.delete(deck_service.get_owned(deck_id, current_user))
    return "", 204


@decksbp.put("/<int:deck_id>/cards")
@login_required
def replace_deck_cards(deck_id):
    deck = deck_service.get_owned(deck_id, current_user)
    entries = parse_deck_cards(json_body())
    return dump_deck(deck_service.replace_cards(deck, entries))
