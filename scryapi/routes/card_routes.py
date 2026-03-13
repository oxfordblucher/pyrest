from flask import Blueprint, jsonify, request
from extensions import db
from models.card import Card
from data_access.card_access import get_card_data

cardsbp = Blueprint('cards', __name__, url_prefix='/api/cards')

@cardsbp.get('/')
def get_cards():
    try:
        limit = min(int(request.args.get("limit", 20)), 50)
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        limit = 20
        page = 1

    cards = get_card_data(limit, page)

    res = [row.to_dict() for row in cards]
    return jsonify({
        "page": page,
        "limit": limit,
        "results": res
    })

@cardsbp.get('/<int:id>')
def get_card_by_id(id):
    card = db.get_or_404(Card, id)
    res = card.to_dict()
    return jsonify(res)