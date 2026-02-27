from flask import Blueprint, jsonify
from extensions import db
from models.card import Card

cardsbp = Blueprint('cards', __name__, url_prefix='/api/cards')

@cardsbp.get('/')
def get_cards():
    cards = db.session.execute(db.select(Card).order_by(Card.name).limit(20)).scalars().all()
    res = [row.to_dict() for row in cards]
    return jsonify(res)

@cardsbp.get('/id/<id>')
def get_card_by_id(id):
    card = db.get_or_404(Card, id)
    res = card.to_dict()
    return jsonify(res)

@cardsbp.get('/name/<name>')
def get_cards_by_name(name):
    cards = db.session.execute(db.select(Card).where(Card.name.like(f"%{name}%")).limit(20)).scalars().all()
    res = [row.to_dict() for row in cards]
    return jsonify(res)

@cardsbp.get('/type/<type_line>')
def get_cards_by_type(type_line):
    cards = db.session.execute(db.select(Card).where(Card.type_line.like(f"%{type_line}%")).limit(20)).scalars().all()
    res = [row.to_dict() for row in cards]
    return jsonify(res)