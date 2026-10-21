"""Request parsing and response serialisation. Never serialise models wholesale."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from flask import request

from scryapi.errors import ValidationError

MAX_PARAM_LENGTH = 100
DEFAULT_LIMIT = 20
MAX_LIMIT = 50

type Json = dict[str, Any]
type Args = Mapping[str, str]  # query string (request.args) or similar


class Errors:
    """Collects field errors so a request reports every problem at once."""

    def __init__(self) -> None:
        self.details: list[dict[str, str]] = []

    def add(self, field: str, message: str) -> None:
        self.details.append({"field": field, "message": message})

    def raise_if_any(self, message: str = "Invalid request") -> None:
        if self.details:
            raise ValidationError(self.details, message)


def parse_int(
    args: Args,
    field: str,
    default: int,
    errors: Errors,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    raw = args.get(field)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        errors.add(field, "must be an integer")
        return default
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        if maximum is None:
            errors.add(field, f"must be at least {minimum}")
        else:
            errors.add(field, f"must be between {minimum} and {maximum}")
        return default
    return value


def parse_text(
    args: Args, field: str, errors: Errors, max_length: int = MAX_PARAM_LENGTH
) -> str | None:
    value = args.get(field)
    if value is None:
        return None
    value = value.strip()
    if len(value) > max_length:
        errors.add(field, f"must be at most {max_length} characters")
        return None
    return value or None


def parse_pagination(args: Args, errors: Errors) -> tuple[int, int]:
    page = parse_int(args, "page", 1, errors, minimum=1)
    limit = parse_int(args, "limit", DEFAULT_LIMIT, errors, minimum=1, maximum=MAX_LIMIT)
    return page, limit


def paginated(page: int, limit: int, total: int, results: list[Json]) -> Json:
    return {"page": page, "limit": limit, "total": total, "results": results}


def json_body() -> Json:
    """The request's JSON object body, or a 400 if it is missing or not an object."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValidationError(
            [{"field": "body", "message": "must be a JSON object"}], "Expected a JSON body"
        )
    return body


def iso(dt: datetime | None) -> str | None:
    """ISO 8601 in UTC. SQLite hands back naive datetimes; they were stored as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
