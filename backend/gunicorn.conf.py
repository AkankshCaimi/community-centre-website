# gunicorn settings for the image. Spec: docs/specs/deploy-free.md (P1 to P4).
import os
import re

# The host injects PORT; without it, 8000 as before (P1, P2).
_port = os.environ.get("PORT") or "8000"

# A bad PORT stops the start rather than binding elsewhere (P3).
if not re.fullmatch(r"[0-9]+", _port) or not 1 <= int(_port) <= 65535:
    raise ValueError(f"PORT must be a whole number from 1 to 65535, not {_port!r}")

bind = f"0.0.0.0:{_port}"
