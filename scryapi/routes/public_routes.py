from flask import Blueprint, jsonify
from extensions import db
from models import User, Deck

publicbp = Blueprint("", __name__, url_prefix="/api/public")

publicbp.before_request()

@publicbp.get('/decks')
def get_public_decks():
    pass

@publicbp.get('/users')
def get_public_users():
    pass

@publicbp.get('/')