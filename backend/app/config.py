import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]

# Variables already set in the environment take precedence over the file.
load_dotenv(REPO_ROOT / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    TEAM_EMAIL = os.environ.get("TEAM_EMAIL")
    # Number of trusted proxies in front of the application (spec F01, L6).
    TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))
    # Largest request body accepted, in bytes (spec F01, B2).
    MAX_CONTENT_LENGTH = 64 * 1024
