"""JSON error envelope for every error response. See docs/TDD.md §9."""

import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

# HTTP status -> stable machine-readable error code.
ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
    501: "not_implemented",
}


class ApiError(Exception):
    """Raise from anywhere in request handling to return a JSON error."""

    def __init__(self, status, error, message, details=None):
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message
        self.details = details


class ValidationError(ApiError):
    def __init__(self, details, message="Invalid request"):
        super().__init__(400, "validation_error", message, details)


class ConflictError(ApiError):
    def __init__(self, message, details=None):
        super().__init__(409, "conflict", message, details)


def error_response(status, error, message, details=None):
    body = {"error": error, "message": message}
    if details:
        body["details"] = details
    return jsonify(body), status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(e):
        return error_response(e.status, e.error, e.message, e.details)

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        code = ERROR_CODES.get(e.code, "http_error")
        return error_response(e.code, code, e.description)

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        logger.exception("Unhandled exception")
        return error_response(500, "internal_error", "An unexpected error occurred.")
