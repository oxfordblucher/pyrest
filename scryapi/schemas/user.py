import re
from dataclasses import dataclass

from scryapi.models import User
from scryapi.schemas import Errors, Json, iso

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")
# Deliberately loose: real validation of an address is sending mail to it.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 12
MAX_PASSWORD = 128
MAX_EMAIL = 254


@dataclass(frozen=True)
class Registration:
    username: str
    email: str
    password: str


@dataclass(frozen=True)
class PasswordChange:
    current_password: str
    new_password: str


@dataclass(frozen=True)
class Login:
    login: str
    password: str
    remember: bool


def _string(body: Json, field: str, errors: Errors) -> str:
    value = body.get(field)
    if value is None:
        errors.add(field, "is required")
        return ""
    if not isinstance(value, str):
        errors.add(field, "must be a string")
        return ""
    return value


def parse_registration(body: Json) -> Registration:
    errors = Errors()
    username = _string(body, "username", errors).strip().lower()
    email = _string(body, "email", errors).strip().lower()
    password = _string(body, "password", errors)

    if username and not USERNAME_RE.match(username):
        errors.add("username", "must be 3-30 characters: letters, digits and underscores")
    if email and (len(email) > MAX_EMAIL or not EMAIL_RE.match(email)):
        errors.add("email", "must be a valid email address")
    _check_password_length(body, "password", errors)

    errors.raise_if_any()
    return Registration(username=username, email=email, password=password)


def _check_password_length(body: Json, field: str, errors: Errors) -> None:
    value = body.get(field)
    if isinstance(value, str) and not MIN_PASSWORD <= len(value) <= MAX_PASSWORD:
        errors.add(field, f"must be {MIN_PASSWORD}-{MAX_PASSWORD} characters")


def parse_password_change(body: Json) -> PasswordChange:
    errors = Errors()
    current = _string(body, "current_password", errors)
    new = _string(body, "new_password", errors)
    _check_password_length(body, "new_password", errors)
    errors.raise_if_any()
    return PasswordChange(current_password=current[:MAX_PASSWORD], new_password=new)


def parse_login(body: Json) -> Login:
    errors = Errors()
    login = _string(body, "login", errors).strip().lower()
    password = _string(body, "password", errors)
    remember = body.get("remember", False)
    if not isinstance(remember, bool):
        errors.add("remember", "must be a boolean")
    errors.raise_if_any()
    return Login(login=login, password=password[:MAX_PASSWORD], remember=remember)


def dump_me(user: User, unread_notifications: int = 0) -> Json:
    return {
        "username": user.username,
        "email": user.email,
        "created_at": iso(user.created_at),
        "unread_notifications": unread_notifications,
    }


def dump_public_user(user: User) -> Json:
    return {"username": user.username, "created_at": iso(user.created_at)}
