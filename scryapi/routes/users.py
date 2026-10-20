from flask import Blueprint

from scryapi.schemas.user import dump_public_user
from scryapi.services import users as user_service

usersbp = Blueprint("users", __name__, url_prefix="/api/users")


@usersbp.get("/<username>")
def get_user(username):
    return dump_public_user(user_service.get_by_username(username))
