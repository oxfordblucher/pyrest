import re
from dataclasses import dataclass

from scryapi.schemas import Errors, iso

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
class Login:
    login: str
    password: str
    remember: bool


def _string(body, field, errors):
    value = body.get(field)
    if value is None:
        errors.add(field, "is required")
        return ""
    if not isinstance(value, str):
        errors.add(field, "must be a string")
        return ""
    return value


def parse_registration(body):
    errors = Errors()
    username = _string(body, "username", errors).strip().lower()
    email = _string(body, "email", errors).strip().lower()
    password = _string(body, "password", errors)

    if username and not USERNAME_RE.match(username):
        errors.add("username", "must be 3-30 characters: letters, digits and underscores")
    if email and (len(email) > MAX_EMAIL or not EMAIL_RE.match(email)):
        errors.add("email", "must be a valid email address")
    if isinstance(body.get("password"), str) and not (
        MIN_PASSWORD <= len(password) <= MAX_PASSWORD
    ):
        errors.add("password", f"must be {MIN_PASSWORD}-{MAX_PASSWORD} characters")

    errors.raise_if_any()
    return Registration(username=username, email=email, password=password)


def parse_login(body):
    errors = Errors()
    login = _string(body, "login", errors).strip().lower()
    password = _string(body, "password", errors)
    remember = body.get("remember", False)
    if not isinstance(remember, bool):
        errors.add("remember", "must be a boolean")
    errors.raise_if_any()
    return Login(login=login, password=password[:MAX_PASSWORD], remember=remember)


def dump_me(user):
    return {"username": user.username, "email": user.email, "created_at": iso(user.created_at)}


def dump_public_user(user):
    return {"username": user.username, "created_at": iso(user.created_at)}
