from flask import Blueprint, current_app, request, session
from flask_login import current_user, login_required, login_user, logout_user
from flask_login.config import COOKIE_NAME
from flask_wtf.csrf import generate_csrf

from scryapi.errors import ApiError
from scryapi.extensions import limiter
from scryapi.schemas import json_body
from scryapi.schemas.user import (
    dump_me,
    parse_login,
    parse_password_change,
    parse_registration,
)
from scryapi.services import notifications as notification_service
from scryapi.services import users as user_service

authbp = Blueprint("auth", __name__, url_prefix="/api/auth")

CSRF_HEADER = "X-CSRFToken"

# Shared bucket: credential stuffing across login and register counts together.
auth_limit = limiter.shared_limit(
    lambda: current_app.config["SCRYAPI_RATELIMIT_AUTH"], scope="auth"
)


def _start_session(user, remember=False):
    """Log in on a fresh session (prevents session fixation).

    Clearing the session also drops the old CSRF token, so the new one is returned in
    the X-CSRFToken response header for the client's next mutating request.
    """
    session.clear()
    login_user(user, remember=remember)
    return {CSRF_HEADER: generate_csrf()}


@authbp.get("/csrf")
def get_csrf_token():
    token = generate_csrf()
    return {"csrf_token": token}, 200, {CSRF_HEADER: token}


@authbp.post("/register")
@auth_limit
def register():
    user = user_service.register(parse_registration(json_body()))
    return dump_me(user), 201, _start_session(user)


@authbp.post("/login")
@auth_limit
def login():
    credentials = parse_login(json_body())
    user = user_service.authenticate(credentials)
    if user is None:
        raise ApiError(401, "unauthorized", "Invalid username/email or password")
    unread = notification_service.unread_count(user)
    return dump_me(user, unread), 200, _start_session(user, remember=credentials.remember)


@authbp.post("/password")
@login_required
@auth_limit
def change_password():
    user = user_service.change_password(current_user, parse_password_change(json_body()))
    # Old cookies now carry a stale session version; issue fresh ones on this device.
    remembered = current_app.config.get("REMEMBER_COOKIE_NAME", COOKIE_NAME) in request.cookies
    unread = notification_service.unread_count(user)
    return dump_me(user, unread), 200, _start_session(user, remember=remembered)


@authbp.post("/logout")
def logout():
    logout_user()
    session.clear()
    return "", 204


@authbp.get("/me")
@login_required
def me():
    return dump_me(current_user, notification_service.unread_count(current_user))
