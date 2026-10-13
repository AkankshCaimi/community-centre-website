from flask import Blueprint, jsonify

from app.services import auto_decline

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return jsonify(status="ok", auto_decline_last_run=auto_decline.last_run_text())
