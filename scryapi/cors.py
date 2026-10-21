"""Opt-in CORS for a frontend served from another origin (docs/TDD.md §8).

Off unless SCRYAPI_CORS_ORIGINS lists origins. Credentials (cookies) are allowed for
exactly those origins, and X-CSRFToken is exposed so the client can read rotated tokens.
"""

from urllib.parse import urlsplit

from flask import request

from scryapi.errors import error_response

ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE"
ALLOWED_HEADERS = "Content-Type, X-CSRFToken"
EXPOSED_HEADERS = "X-CSRFToken"
PREFLIGHT_MAX_AGE = "600"
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _origin(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None


def parse_origins(value):
    """`"https://a.example, http://localhost:5173"` -> frozenset of exact origins."""
    origins = set()
    for item in filter(None, (part.strip() for part in value.split(","))):
        origin = _origin(item)
        if (
            origin is None
            or origin != item.rstrip("/")
            or urlsplit(item).scheme
            not in (
                "http",
                "https",
            )
        ):
            raise RuntimeError(
                f"SCRYAPI_CORS_ORIGINS entry {item!r} must be a bare origin such as "
                "https://app.example.com (no wildcard, path or trailing data)"
            )
        origins.add(origin.lower())
    return frozenset(origins)


def init_app(app):
    origins = parse_origins(app.config["SCRYAPI_CORS_ORIGINS"])
    if not origins:
        return

    # Flask-WTF's HTTPS check only accepts a Referer from this host, which would reject
    # every request from the allowed frontend. check_request_origin replaces it.
    app.config["WTF_CSRF_SSL_STRICT"] = False

    @app.before_request
    def check_request_origin():
        if request.method not in MUTATING_METHODS or not request.is_secure:
            return None
        source = request.headers.get("Origin") or _origin(request.referrer or "")
        if source is None:
            return error_response(400, "csrf_failed", "The Origin and Referer headers are missing.")
        if source.lower() not in origins | {request.host_url.rstrip("/").lower()}:
            return error_response(400, "csrf_failed", "The request origin is not allowed.")
        return None

    @app.after_request
    def add_cors_headers(response):
        response.vary.add("Origin")
        origin = request.headers.get("Origin")
        if origin is None or origin.lower() not in origins:
            return response
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Expose-Headers"] = EXPOSED_HEADERS
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Methods"] = ALLOWED_METHODS
            response.headers["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
            response.headers["Access-Control-Max-Age"] = PREFLIGHT_MAX_AGE
        return response
