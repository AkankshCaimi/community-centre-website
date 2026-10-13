"""The admin API: docs/specs/F02.md."""

from functools import wraps

from flask import Blueprint, jsonify, request

from app.api.request_body import UnreadableBody, read_json_object
from app.services import admin_auth, admin_bookings

bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")

SESSION_COOKIE = "admin_session"
# What the cookie is set and cleared with (SE1).
COOKIE_ATTRIBUTES = {"httponly": True, "secure": True, "samesite": "Strict", "path": "/"}


class _Refused(Exception):
    """Stops a request with a ready-made response."""

    def __init__(self, response):
        super().__init__()
        self.response = response


@bp.errorhandler(_Refused)
def _refused(error: _Refused):
    return error.response


@bp.after_request
def _never_stored(response):
    """Browsers and proxies keep no copy of an admin response (HD1)."""
    response.headers["Cache-Control"] = "no-store"
    return response


def session_value() -> str | None:
    """The first admin_session cookie of the request; any others are ignored (SE8)."""
    for part in request.headers.get("Cookie", "").split(";"):
        name, separator, value = part.strip().partition("=")
        if separator and name == SESSION_COOKIE:
            return value
    return None


def route(rule: str, method: str):
    """Register a view for one method only; every other method is a 405 (F01 A10)."""
    return bp.route(rule, methods=[method], provide_automatic_options=False)


def needs_session(view):
    """Refuse the request with R3 unless it carries a valid session (SE4, O1)."""

    @wraps(view)
    def checked(*args, **kwargs):
        email = admin_auth.session_email(session_value())
        if email is None:
            return jsonify(error="not_authenticated"), 401
        return view(*args, admin_email=email, **kwargs)

    return checked


def json_body() -> dict:
    """The request body as one JSON object, or a refusal (B1, R14)."""
    if request.mimetype != "application/json":
        raise _Refused((jsonify(error="unsupported_media_type"), 415))
    try:
        # Reading the body raises 413 if it is larger than MAX_CONTENT_LENGTH.
        return read_json_object(request.get_data())
    except UnreadableBody as error:
        raise _Refused((jsonify(error="invalid_request"), 400)) from error


def _validation_failed(failure):
    return jsonify(error="validation_failed", fields=failure.fields), 400


@route("/login", "POST")
def login():
    body = json_body()
    try:
        email, session_value = admin_auth.log_in(body)
    except admin_auth.ValidationFailed as failure:
        return _validation_failed(failure)
    except admin_auth.InvalidCredentials:
        return jsonify(error="invalid_credentials"), 401

    response = jsonify(email=email)
    response.set_cookie(SESSION_COOKIE, session_value, **COOKIE_ATTRIBUTES)
    return response


@route("/logout", "POST")
@needs_session
def logout(admin_email):
    json_body()
    admin_auth.log_out(session_value())
    response = jsonify(status="logged_out")
    response.delete_cookie(SESSION_COOKIE, **COOKIE_ATTRIBUTES)
    return response


@route("/session", "GET")
@needs_session
def session(admin_email):
    return jsonify(email=admin_email)


@route("/bookings", "GET")
@needs_session
def list_bookings(admin_email):
    try:
        return jsonify(admin_bookings.list_bookings(request.args.to_dict()))
    except admin_bookings.ValidationFailed as failure:
        return _validation_failed(failure)


@route("/bookings/<booking_id>/state", "PATCH")
@needs_session
def change_state(booking_id, admin_email):
    body = json_body()
    try:
        return jsonify(admin_bookings.change_state(booking_id, body))
    except admin_bookings.ValidationFailed as failure:
        return _validation_failed(failure)
    except admin_bookings.NotFound:
        return jsonify(error="not_found"), 404
    except admin_bookings.DeclinedIsFinal:
        return jsonify(error="declined_is_final"), 409


@route("/password-reset", "POST")
def request_password_reset():
    body = json_body()
    try:
        admin_auth.request_password_reset(body)
    except admin_auth.ValidationFailed as failure:
        return _validation_failed(failure)
    return jsonify(status="reset_requested")


@route("/password-reset/confirm", "POST")
def confirm_password_reset():
    body = json_body()
    try:
        admin_auth.confirm_password_reset(body)
    except admin_auth.ValidationFailed as failure:
        return _validation_failed(failure)
    except admin_auth.InvalidToken:
        return jsonify(error="invalid_token"), 400
    return jsonify(status="password_changed")
