from flask import Blueprint

from scryapi.routes.decks import pagination_args, summaries
from scryapi.schemas.user import dump_public_user
from scryapi.services import decks as deck_service
from scryapi.services import users as user_service

usersbp = Blueprint("users", __name__, url_prefix="/api/users")


@usersbp.get("/<username>")
def get_user(username):
    return dump_public_user(user_service.get_by_username(username))


@usersbp.get("/<username>/decks")
def list_user_public_decks(username):
    user = user_service.get_by_username(username)
    page, limit = pagination_args()
    return summaries(page, limit, deck_service.list_public_for_user(user, page, limit))
