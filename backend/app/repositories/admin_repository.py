"""Database access for the admin account and its sessions (docs/specs/F02.md)."""

from datetime import datetime

import psycopg

from app.models.admin import AdminUser


def _admin(row) -> AdminUser | None:
    if row is None:
        return None
    return AdminUser(id=row[0], email=row[1], password_hash=row[2])


def count_admins(connection: psycopg.Connection) -> int:
    return connection.execute("SELECT count(*) FROM admin_users").fetchone()[0]


def insert_admin(connection: psycopg.Connection, email: str, password_hash: str) -> None:
    connection.execute(
        "INSERT INTO admin_users (email, password_hash) VALUES (%s, %s)", (email, password_hash)
    )


def find_admin_by_email(connection: psycopg.Connection, email: str) -> AdminUser | None:
    """The admin whose email matches, ignoring letter case."""
    row = connection.execute(
        "SELECT id, email, password_hash FROM admin_users WHERE lower(email) = lower(%s)",
        (email,),
    ).fetchone()
    return _admin(row)


# --- sessions


def insert_session(
    connection: psycopg.Connection, admin_id: int, token_hash: str, now: datetime
) -> None:
    connection.execute(
        """
        INSERT INTO admin_sessions (admin_user_id, token_hash, created_at, last_used_at)
        VALUES (%s, %s, %s, %s)
        """,
        (admin_id, token_hash, now, now),
    )


def use_session(
    connection: psycopg.Connection, token_hash: str, used_after: datetime, now: datetime
) -> str | None:
    """Mark a session as used now, if it was last used later than `used_after`.

    Returns the admin's email, or None if there is no such session or it has expired.
    """
    row = connection.execute(
        """
        UPDATE admin_sessions AS session
        SET last_used_at = %s
        FROM admin_users AS admin
        WHERE admin.id = session.admin_user_id
          AND session.token_hash = %s
          AND session.last_used_at > %s
        RETURNING admin.email
        """,
        (now, token_hash, used_after),
    ).fetchone()
    return None if row is None else row[0]


def delete_session(connection: psycopg.Connection, token_hash: str) -> None:
    connection.execute("DELETE FROM admin_sessions WHERE token_hash = %s", (token_hash,))


def delete_sessions_of(connection: psycopg.Connection, admin_id: int) -> None:
    connection.execute("DELETE FROM admin_sessions WHERE admin_user_id = %s", (admin_id,))


# --- password reset


def issue_reset_token(
    connection: psycopg.Connection, email: str, token_hash: str, now: datetime
) -> str | None:
    """Store a reset token for the admin with this email, replacing any earlier one.

    Returns the admin's stored email, or None if the email is not an admin's.
    The statement rewrites every admin row whether or not the email matches, so
    it does the same work, and takes the same time, either way (F02 PR8).
    """
    rows = connection.execute(
        """
        UPDATE admin_users
        SET password_reset_token_hash = CASE
                WHEN lower(email) = lower(%(email)s) THEN %(token_hash)s
                ELSE password_reset_token_hash
            END,
            password_reset_created_at = CASE
                WHEN lower(email) = lower(%(email)s) THEN %(now)s
                ELSE password_reset_created_at
            END
        RETURNING email, lower(email) = lower(%(email)s)
        """,
        {"email": email, "token_hash": token_hash, "now": now},
    ).fetchall()
    for stored_email, matched in rows:
        if matched:
            return stored_email
    return None


def find_admin_by_reset_token(
    connection: psycopg.Connection, token_hash: str, created_after: datetime
) -> AdminUser | None:
    """The admin holding this reset token, if it was created later than `created_after`."""
    row = connection.execute(
        """
        SELECT id, email, password_hash FROM admin_users
        WHERE password_reset_token_hash = %s AND password_reset_created_at > %s
        FOR UPDATE
        """,
        (token_hash, created_after),
    ).fetchone()
    return _admin(row)


def replace_password(connection: psycopg.Connection, admin_id: int, password_hash: str) -> None:
    """Set a new password hash and clear the reset token, so the token works only once."""
    connection.execute(
        """
        UPDATE admin_users
        SET password_hash = %s, password_reset_token_hash = NULL, password_reset_created_at = NULL
        WHERE id = %s
        """,
        (password_hash, admin_id),
    )
