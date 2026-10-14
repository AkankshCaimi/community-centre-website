"""Serving the built React application: rules G1 to G10 of docs/specs/deploy.md."""

import os

from flask import Response, current_app, request, send_file
from werkzeug.security import safe_join

INDEX = "index.html"
NOT_CACHED = "no-cache"
# Files under assets/ change their names whenever their contents change (G7).
ASSETS = "assets/"
CACHED_FOR_GOOD = "public, max-age=31536000, immutable"


def _file_in(folder: str, name: str) -> str | None:
    """The path of the file `name` inside `folder`, or None if there is no such file (G6)."""
    path = safe_join(folder, name)
    if path is None or not os.path.isfile(path):
        return None
    return path


def answer() -> Response | None:
    """The frontend's answer to a request that no route answers, or None to leave it a 404."""
    folder = current_app.config.get("FRONTEND_DIST")
    if not folder or request.method not in ("GET", "HEAD"):
        return None
    if request.path == "/api" or request.path.startswith("/api/"):
        return None

    name = request.path.lstrip("/")
    path = _file_in(folder, name) if name else None
    if path is None:
        name = INDEX
        path = _file_in(folder, INDEX)
        if path is None:
            return None

    response = send_file(path)
    response.headers["Cache-Control"] = CACHED_FOR_GOOD if name.startswith(ASSETS) else NOT_CACHED
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
