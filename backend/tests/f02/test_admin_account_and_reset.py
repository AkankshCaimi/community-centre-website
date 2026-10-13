"""F02 admin account rules CL1 to CL5 and password reset rules PR1 to PR5.

Every expected value comes from docs/specs/F02.md; each test names the rule it checks.
"""

import logging
import re
from datetime import timedelta

import pytest
from f02_helpers import ADMIN_EMAIL, ADMIN_PASSWORD, NOW, call, create_admin, login

NEW_PASSWORD = "a brand new password"  # 20 characters
RESET_REQUESTED = {"status": "reset_requested"}
INVALID_TOKEN = {"error": "invalid_token"}


def admin_count(db):
    return db.execute("SELECT count(*) FROM admin_users").fetchone()[0]


def fields(response):
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    return body["fields"]


# --- CL1 to CL4: creating the admin account


def test_cl1_cl3_command_creates_the_account(app, db):
    result = create_admin(app)

    assert result.exit_code == 0
    assert "Admin account created." in result.output
    assert db.execute("SELECT email FROM admin_users").fetchall() == [(ADMIN_EMAIL,)]
    assert login(app.test_client()).status_code == 200


def test_cl1_password_is_typed_at_a_hidden_prompt(app):
    result = create_admin(app)

    assert result.exit_code == 0
    assert ADMIN_PASSWORD not in result.output


def test_cl1_password_cannot_be_given_on_the_command_line(app, db):
    result = app.test_cli_runner().invoke(
        args=["create-admin", "--email", ADMIN_EMAIL, "--password", ADMIN_PASSWORD]
    )

    assert result.exit_code != 0
    assert admin_count(db) == 0


def test_cl2_email_is_stored_trimmed(app, db):
    result = create_admin(app, email="  admin@centre.example  ")

    assert result.exit_code == 0
    assert db.execute("SELECT email FROM admin_users").fetchone()[0] == "admin@centre.example"


@pytest.mark.parametrize(
    "email",
    ["not-an-email", "admin@centre", "ad min@centre.example", "@centre.example", ""],
)
def test_cl2_cl4_bad_email_creates_nothing(app, db, email):
    result = create_admin(app, email=email)

    assert result.exit_code == 1
    assert admin_count(db) == 0


@pytest.mark.parametrize(
    "password, exit_code",
    [
        pytest.param("p" * 11, 1, id="11-characters"),
        pytest.param("p" * 12, 0, id="12-characters"),
        pytest.param("p" * 1024, 0, id="1024-characters"),
        pytest.param("p" * 1025, 1, id="1025-characters"),
    ],
)
def test_cl2_password_must_be_12_to_1024_characters(app, db, password, exit_code):
    result = create_admin(app, password=password)

    assert result.exit_code == exit_code
    assert admin_count(db) == (1 if exit_code == 0 else 0)


def test_cl2_cl4_entries_that_do_not_match_create_nothing(app, db):
    result = create_admin(app, password=ADMIN_PASSWORD, repeat=ADMIN_PASSWORD + "x")

    assert result.exit_code == 1
    assert admin_count(db) == 0


def test_cl4_second_account_is_refused(app, admin, db):
    result = create_admin(app, email="second@centre.example", password="another password 1")

    assert result.exit_code == 1
    assert db.execute("SELECT email FROM admin_users").fetchall() == [(ADMIN_EMAIL,)]
    # The first account is untouched.
    assert login(app.test_client()).status_code == 200


def test_cl4_failed_command_does_not_say_it_created_an_account(app, admin):
    result = create_admin(app, email="second@centre.example", password="another password 1")

    assert result.exit_code == 1
    assert "Admin account created." not in result.output
    assert result.output.strip() != ""


# --- CL5: init-db


def test_cl5_init_db_creates_the_admin_tables(app, db):
    tables = db.execute(
        "SELECT to_regclass('admin_users') IS NOT NULL, to_regclass('admin_sessions') IS NOT NULL"
    ).fetchone()

    assert tables == (True, True)


def test_cl5_init_db_again_leaves_existing_rows_alone(app, admin, db, make_booking):
    make_booking(1, 1)
    login(app.test_client())

    result = app.test_cli_runner().invoke(args=["init-db"])

    assert result.exit_code == 0
    counts = db.execute(
        "SELECT (SELECT count(*) FROM admin_users), (SELECT count(*) FROM admin_sessions),"
        " (SELECT count(*) FROM bookings)"
    ).fetchone()
    assert counts == (1, 1, 1)


# --- PR1: asking for a reset


def request_reset(app, email=ADMIN_EMAIL):
    return call(app.test_client(), "POST", "/password-reset", {"email": email})


def test_pr1_known_and_unknown_email_give_the_same_response(app, admin):
    known = request_reset(app)
    unknown = request_reset(app, "someone.else@centre.example")

    assert known.status_code == unknown.status_code == 200
    assert known.content_type == unknown.content_type == "application/json"
    assert known.get_data() == unknown.get_data()
    assert known.get_json() == RESET_REQUESTED


def test_pr1_response_is_the_same_when_no_admin_account_exists(app):
    response = request_reset(app)

    assert response.status_code == 200
    assert response.get_json() == RESET_REQUESTED


@pytest.mark.parametrize(
    "body, code",
    [
        pytest.param({}, "required", id="missing"),
        pytest.param({"email": ""}, "required", id="empty"),
        pytest.param({"email": 7}, "required", id="not-a-string"),
        pytest.param({"email": "a" * 243 + "@example.com"}, "too_long", id="255-characters"),
    ],
)
def test_pr1_bad_email_field_is_refused(app, admin, body, code):
    response = call(app.test_client(), "POST", "/password-reset", body)

    assert fields(response) == {"email": code}


# --- PR2: the token


def email_log(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "app.email"]


def reset_token(app, caplog, email=ADMIN_EMAIL):
    """Ask for a reset and read the token from the logged email (PR2)."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.email"):
        request_reset(app, email)
    messages = email_log(caplog)
    assert len(messages) == 1
    match = re.search(r"^Token: (\S+)$", messages[0], flags=re.MULTILINE)
    assert match is not None, messages[0]
    return match.group(1)


def test_pr2_reset_email_is_logged_with_recipient_and_token(app, admin, caplog):
    with caplog.at_level(logging.DEBUG, logger="app.email"):
        request_reset(app)

    records = [record for record in caplog.records if record.name == "app.email"]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert ADMIN_EMAIL in records[0].getMessage()
    token = re.search(r"^Token: (\S+)$", records[0].getMessage(), flags=re.MULTILINE).group(1)
    # 32 random bytes need at least 43 characters in any text form.
    assert len(token) >= 43


@pytest.mark.parametrize("email", ["ADMIN@Centre.Example", "  admin@centre.example "])
def test_pr2_email_is_matched_like_login(app, admin, caplog, email):
    assert len(reset_token(app, caplog, email)) >= 43


def test_pr2_nothing_is_logged_or_stored_for_an_unknown_email(app, admin, db, caplog):
    with caplog.at_level(logging.INFO, logger="app.email"):
        request_reset(app, "someone.else@centre.example")

    assert email_log(caplog) == []
    row = db.execute(
        "SELECT password_reset_token_hash, password_reset_created_at FROM admin_users"
    ).fetchone()
    assert row == (None, None)


def test_pr2_token_itself_is_not_stored(app, admin, db, caplog):
    token = reset_token(app, caplog)

    row = db.execute("SELECT * FROM admin_users").fetchone()
    assert all(token not in str(value) for value in row)


def test_pr2_tokens_differ_every_time(app, admin, caplog):
    assert len({reset_token(app, caplog) for _ in range(3)}) == 3


def test_pr2_new_request_replaces_the_earlier_token(app, admin, caplog):
    first = reset_token(app, caplog)
    second = reset_token(app, caplog)

    refused = confirm(app, first)
    accepted = confirm(app, second)

    assert refused.status_code == 400
    assert refused.get_json() == INVALID_TOKEN
    assert accepted.status_code == 200


# --- PR3: setting a new password


def confirm(app, token, password=NEW_PASSWORD):
    return call(
        app.test_client(), "POST", "/password-reset/confirm", {"token": token, "password": password}
    )


def test_pr3_valid_token_replaces_the_password(app, admin, db, caplog):
    token = reset_token(app, caplog)

    response = confirm(app, token)

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {"status": "password_changed"}
    assert login(app.test_client(), password=ADMIN_PASSWORD).status_code == 401
    assert login(app.test_client(), password=NEW_PASSWORD).status_code == 200
    assert (
        db.execute("SELECT password_hash FROM admin_users").fetchone()[0].startswith("$argon2id$")
    )


def test_pr3_token_works_only_once(app, admin, caplog):
    token = reset_token(app, caplog)
    assert confirm(app, token).status_code == 200

    again = confirm(app, token, "yet another password")

    assert again.status_code == 400
    assert again.get_json() == INVALID_TOKEN
    assert login(app.test_client(), password=NEW_PASSWORD).status_code == 200


def test_pr3_reset_ends_every_session(app, admin, caplog):
    first, second = app.test_client(), app.test_client()
    login(first)
    login(second)
    token = reset_token(app, caplog)

    confirm(app, token)

    assert call(first, "GET", "/session").status_code == 401
    assert call(second, "GET", "/session").status_code == 401


def test_pr3_reset_does_not_log_the_new_password(app, admin, caplog):
    token = reset_token(app, caplog)
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        confirm(app, token)

    assert all(NEW_PASSWORD not in record.getMessage() for record in caplog.records)


# --- PR4: when a token is valid


def test_pr4_token_is_valid_just_inside_30_minutes(app, admin, clock, caplog):
    token = reset_token(app, caplog)
    clock.now = NOW + timedelta(minutes=29, seconds=59)

    assert confirm(app, token).status_code == 200


def test_pr4_token_is_refused_at_exactly_30_minutes(app, admin, clock, caplog):
    token = reset_token(app, caplog)
    clock.now = NOW + timedelta(minutes=30)

    response = confirm(app, token)

    assert response.status_code == 400
    assert response.get_json() == INVALID_TOKEN
    assert login(app.test_client(), password=ADMIN_PASSWORD).status_code == 200


@pytest.mark.parametrize("token", ["made-up-token", "x" * 43, "x" * 1024])
def test_pr4_unknown_token_is_refused_and_changes_nothing(app, admin, caplog, token):
    reset_token(app, caplog)

    response = confirm(app, token)

    assert response.status_code == 400
    assert response.content_type == "application/json"
    assert response.get_json() == INVALID_TOKEN
    assert login(app.test_client(), password=ADMIN_PASSWORD).status_code == 200
    assert login(app.test_client(), password=NEW_PASSWORD).status_code == 401


def test_pr4_token_is_refused_when_no_reset_was_requested(app, admin):
    assert confirm(app, "x" * 43).get_json() == INVALID_TOKEN


def test_pr4_refused_token_leaves_sessions_alone(admin_client, app):
    confirm(app, "made-up-token")

    assert call(admin_client, "GET", "/session").status_code == 200


# --- PR5: the fields


@pytest.mark.parametrize(
    "body, expected",
    [
        pytest.param({}, {"token": "required", "password": "required"}, id="both-missing"),
        pytest.param(
            {"token": "", "password": ""},
            {"token": "required", "password": "required"},
            id="both-empty",
        ),
        pytest.param(
            {"token": 5, "password": 5},
            {"token": "required", "password": "required"},
            id="not-strings",
        ),
        pytest.param(
            {"token": "t" * 1025, "password": NEW_PASSWORD}, {"token": "too_long"}, id="long-token"
        ),
        pytest.param(
            {"token": "t" * 43, "password": "p" * 11}, {"password": "too_short"}, id="11-characters"
        ),
        pytest.param(
            {"token": "t" * 43, "password": "p" * 1025},
            {"password": "too_long"},
            id="1025-characters",
        ),
    ],
)
def test_pr5_bad_confirm_fields_are_refused(app, admin, body, expected):
    response = call(app.test_client(), "POST", "/password-reset/confirm", body)

    assert fields(response) == expected


def test_pr5_fields_are_checked_before_the_token(app, admin, caplog):
    """O1: a valid token is not used up by a request whose password is refused."""
    token = reset_token(app, caplog)

    too_short = confirm(app, token, "p" * 11)

    assert fields(too_short) == {"password": "too_short"}
    assert confirm(app, token).status_code == 200


@pytest.mark.parametrize("password", ["p" * 12, "p" * 1024])
def test_pr5_password_of_12_to_1024_characters_is_accepted(app, admin, caplog, password):
    token = reset_token(app, caplog)

    assert confirm(app, token, password).status_code == 200
    assert login(app.test_client(), password=password).status_code == 200
