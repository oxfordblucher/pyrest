from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from scryapi.errors import ApiError, ConflictError, ValidationError
from scryapi.extensions import db
from scryapi.models import User
from scryapi.schemas.user import Login, PasswordChange, Registration

# Checked against when the login doesn't match any user, so a miss costs the same as a
# wrong password and response timing doesn't reveal which accounts exist.
_DUMMY_HASH = generate_password_hash("timing-equaliser-not-a-real-password")


def register(registration: Registration) -> User:
    taken = db.session.execute(
        db.select(User.username, User.email).where(
            (User.username == registration.username) | (User.email == registration.email)
        )
    ).all()
    details = []
    if any(row.username == registration.username for row in taken):
        details.append({"field": "username", "message": "is already taken"})
    if any(row.email == registration.email for row in taken):
        details.append({"field": "email", "message": "is already registered"})
    if details:
        raise ConflictError("Account already exists", details)

    user = User(
        username=registration.username,
        email=registration.email,
        password_hash=generate_password_hash(registration.password),
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:  # lost a race with a concurrent registration
        db.session.rollback()
        raise ConflictError("Account already exists") from None
    return user


def authenticate(login: Login) -> User | None:
    """Return the user for valid credentials, else None. `login` is username or email."""
    field = User.email if "@" in login.login else User.username
    user = db.session.execute(db.select(User).where(field == login.login)).scalar_one_or_none()
    if user is None:
        check_password_hash(_DUMMY_HASH, login.password)
        return None
    return user if check_password_hash(user.password_hash, login.password) else None


def change_password(user: User, change: PasswordChange) -> User:
    """Set a new password and bump the session version, signing out other sessions."""
    if not check_password_hash(user.password_hash, change.current_password):
        raise ValidationError([{"field": "current_password", "message": "is incorrect"}])
    user.password_hash = generate_password_hash(change.new_password)
    user.session_version += 1
    db.session.commit()
    return user


def get_by_username(username: str) -> User:
    user = db.session.execute(
        db.select(User).where(User.username == username.lower())
    ).scalar_one_or_none()
    if user is None:
        raise ApiError(404, "not_found", "User not found")
    return user
