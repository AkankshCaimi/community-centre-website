"""POST /api/v1/bookings: responses A1 to A8 of docs/specs/F01.md."""

import ipaddress

from flask import Blueprint, current_app, jsonify, request

from app.api.request_body import UnreadableBody, read_json_object
from app.services import booking_service
from app.services.booking_validation import utc_to_london_text

bp = Blueprint("bookings", __name__, url_prefix="/api/v1")

RATE_LIMIT_MESSAGE = "Too many responses submitted. Try again later."


def client_address() -> str:
    """The client's network address (spec L6)."""
    hops = current_app.config.get("TRUSTED_PROXY_HOPS", 0)
    if hops > 0:
        forwarded = ",".join(request.headers.getlist("X-Forwarded-For"))
        entries = [entry.strip() for entry in forwarded.split(",")]
        if len(entries) >= hops:
            try:
                return str(ipaddress.ip_address(entries[-hops]))
            except ValueError:
                pass
    return request.remote_addr


# No automatic OPTIONS answer: every method other than POST is a 405 (A10).
@bp.route("/bookings", methods=["POST"], provide_automatic_options=False)
def create_booking():
    if request.mimetype != "application/json":
        return jsonify(error="unsupported_media_type"), 415

    try:
        # Reading the body raises 413 if it is larger than MAX_CONTENT_LENGTH.
        body = read_json_object(request.get_data())
    except UnreadableBody:
        return jsonify(error="invalid_request"), 400

    try:
        booking = booking_service.submit_booking(body, client_address())
    except booking_service.ValidationFailed as failure:
        return jsonify(error="validation_failed", fields=failure.fields), 400
    except booking_service.CaptchaFailed:
        return jsonify(error="captcha_failed"), 403
    except booking_service.RateLimited:
        return jsonify(error="rate_limited", message=RATE_LIMIT_MESSAGE), 429
    except booking_service.NotAccepted:
        return jsonify(error="not_accepted"), 409

    return (
        jsonify(
            id=booking.id,
            state=booking.state,
            starts_at=utc_to_london_text(booking.starts_at),
            ends_at=utc_to_london_text(booking.ends_at),
        ),
        201,
    )
