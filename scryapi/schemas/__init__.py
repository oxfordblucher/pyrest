"""Request parsing and response serialisation. Never serialise models wholesale."""

from scryapi.errors import ValidationError

MAX_PARAM_LENGTH = 100
DEFAULT_LIMIT = 20
MAX_LIMIT = 50


class Errors:
    """Collects field errors so a request reports every problem at once."""

    def __init__(self):
        self.details = []

    def add(self, field, message):
        self.details.append({"field": field, "message": message})

    def raise_if_any(self, message="Invalid request"):
        if self.details:
            raise ValidationError(self.details, message)


def parse_int(args, field, default, errors, minimum=None, maximum=None):
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


def parse_text(args, field, errors, max_length=MAX_PARAM_LENGTH):
    value = args.get(field)
    if value is None:
        return None
    value = value.strip()
    if len(value) > max_length:
        errors.add(field, f"must be at most {max_length} characters")
        return None
    return value or None


def parse_pagination(args, errors):
    page = parse_int(args, "page", 1, errors, minimum=1)
    limit = parse_int(args, "limit", DEFAULT_LIMIT, errors, minimum=1, maximum=MAX_LIMIT)
    return page, limit


def paginated(page, limit, total, results):
    return {"page": page, "limit": limit, "total": total, "results": results}
