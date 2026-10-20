from flask import Blueprint, jsonify

from scryapi.extensions import db
from scryapi.models.deck import Deck

decksbp = Blueprint("decks", __name__, url_prefix="/api/decks")


@decksbp.get("/")
def get_decks():
    decks = db.session.execute(db.select(Deck).order_by(Deck.name).limit(20))
    return jsonify(decks)


@decksbp.get("/profile/")
def get_user_decks():
    pass


@decksbp.post("/")
def make_deck():
    pass


@decksbp.put("/<int:id>")
def update_deck():
    pass
