from flask import Blueprint, jsonify

from app.services import auto_decline, purge

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    last_runs = auto_decline.last_run_texts((auto_decline.JOB_NAME, purge.JOB_NAME))
    return jsonify(
        status="ok",
        auto_decline_last_run=last_runs[auto_decline.JOB_NAME],
        purge_last_run=last_runs[purge.JOB_NAME],
    )
