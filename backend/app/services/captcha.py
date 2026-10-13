"""CAPTCHA check: rules C1 and C2 of docs/specs/F01.md.

In F01 the verifier is a stand-in. No CAPTCHA provider is contacted.
"""

import logging

from flask import current_app

logger = logging.getLogger("app.captcha")


def stand_in_verify(token: str, ip: str) -> bool:
    """Pass every token, and say so in the log without the token or the address (C2)."""
    logger.info("CAPTCHA stand-in passed a token.")
    return True


def verify(token: str, ip: str) -> bool:
    """Run the configured CAPTCHA check (spec: Replaceable parts)."""
    verifier = current_app.config.get("CAPTCHA_VERIFIER", stand_in_verify)
    return verifier(token, ip)
