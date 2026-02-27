from flask import Blueprint, jsonify
from extensions import db
from models.deck import Deck

decksbp = Blueprint('decks', __name__, url_prefix='/api/decks')

@decksbp.get("/")
def get_decks():
    decks = db.session.execute(db.select(Deck).order_by(Deck.name).limit(20))
    return jsonify(decks)