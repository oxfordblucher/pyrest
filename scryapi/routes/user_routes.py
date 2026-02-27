from flask import Blueprint, jsonify
from extensions import db
from models.user import User

usersbp = Blueprint('users', __name__, url_prefix='/api/users')

@usersbp.get("/")
def get_users():
    users = db.session.execute(db.select(User).order_by(User.name).limit(20))
    return jsonify(users)