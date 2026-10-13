"""F02 login rules AU1 to AU6, session rules SE1 to SE7, and the order of checks O1.

Every expected value comes from docs/specs/F02.md; each test names the rule it checks.
"""

import logging
from datetime import timedelta

import pytest
from f02_helpers import ADMIN_EMAIL, ADMIN_PASSWORD, NOT_AUTHENTICATED, NOW, call, login
from f02_helpers import session_cookie as cookie_of

INVALID_CREDENTIALS = {"error": "invalid_credentials"}


def fields(response):
    assert response.status_code == 400
    assert response.content_type == "application/json"
    body = response.get_json()
    assert body["error"] == "validation_failed"
    return body["fields"]


# --- AU1 and R1: logging in


def test_au1_right_email_and_password_log_in(app, admin):
    response = login(app.test_client())

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {"email": ADMIN_EMAIL}
    assert cookie_of(response) is not None


@pytest.mark.parametrize(
    "email",
    ["ADMIN@Centre.Example", "  admin@centre.example  ", "\tAdmin@CENTRE.example\n"],
)
def test_au1_email_is_trimmed_and_ignores_letter_case(app, admin, email):
    response = login(app.test_client(), email=email)

    assert response.status_code == 200
    assert response.get_json() == {"email": ADMIN_EMAIL}


@pytest.mark.parametrize(
    "password",
    [
        pytest.param(ADMIN_PASSWORD.upper(), id="different-case"),
        pytest.param(ADMIN_PASSWORD + " ", id="trailing-space"),
        pytest.param(" " + ADMIN_PASSWORD, id="leading-space"),
        pytest.param(ADMIN_PASSWORD[:-1], id="one-character-short"),
        pytest.param(ADMIN_PASSWORD + "x", id="one-character-extra"),
    ],
)
def test_au1_password_is_compared_exactly(app, admin, password):
    response = login(app.test_client(), password=password)

    assert response.status_code == 401
    assert response.get_json() == INVALID_CREDENTIALS


# --- AU2: one generic error


def test_au2_wrong_email_and_wrong_password_give_the_same_response(app, admin):
    wrong_email = login(app.test_client(), email="someone.else@centre.example")
    wrong_password = login(app.test_client(), password="not the right password")

    assert wrong_email.status_code == wrong_password.status_code == 401
    assert wrong_email.content_type == wrong_password.content_type == "application/json"
    assert wrong_email.get_data() == wrong_password.get_data()
    assert wrong_email.get_json() == INVALID_CREDENTIALS


def test_au2_failed_login_sets_no_cookie(app, admin):
    wrong_email = login(app.test_client(), email="someone.else@centre.example")
    wrong_password = login(app.test_client(), password="not the right password")

    assert wrong_email.status_code == wrong_password.status_code == 401
    assert cookie_of(wrong_email) is None
    assert cookie_of(wrong_password) is None


def test_au2_login_fails_the_same_way_when_no_admin_account_exists(app):
    response = login(app.test_client())

    assert response.status_code == 401
    assert response.get_json() == INVALID_CREDENTIALS


# --- AU3: nothing happens on repeated failures


def test_au3_right_password_still_works_after_many_failures(app, admin):
    client = app.test_client()
    for attempt in range(12):
        assert login(client, password=f"wrong password {attempt}").status_code == 401

    assert login(client).status_code == 200


# --- AU4: the password is stored only as an Argon2id hash


def test_au4_password_is_stored_as_an_argon2id_hash(app, admin, db):
    row = db.execute("SELECT * FROM admin_users").fetchone()
    password_hash = db.execute("SELECT password_hash FROM admin_users").fetchone()[0]

    assert password_hash.startswith("$argon2id$")
    assert all(ADMIN_PASSWORD not in str(value) for value in row)


# --- AU5: the fields


@pytest.mark.parametrize(
    "body, expected",
    [
        pytest.param({}, {"email": "required", "password": "required"}, id="both-missing"),
        pytest.param({"email": ADMIN_EMAIL}, {"password": "required"}, id="password-missing"),
        pytest.param({"password": ADMIN_PASSWORD}, {"email": "required"}, id="email-missing"),
        pytest.param(
            {"email": "", "password": ""},
            {"email": "required", "password": "required"},
            id="both-empty",
        ),
        pytest.param(
            {"email": 5, "password": ["x"]},
            {"email": "required", "password": "required"},
            id="not-strings",
        ),
        pytest.param(
            {"email": None, "password": None},
            {"email": "required", "password": "required"},
            id="nulls",
        ),
        pytest.param(
            {"email": "a" * 243 + "@example.com", "password": ADMIN_PASSWORD},
            {"email": "too_long"},
            id="email-255-chars",
        ),
        pytest.param(
            {"email": ADMIN_EMAIL, "password": "p" * 1025},
            {"password": "too_long"},
            id="password-1025-chars",
        ),
    ],
)
def test_au5_bad_login_fields_are_refused(app, admin, body, expected):
    response = call(app.test_client(), "POST", "/login", body)

    assert fields(response) == expected
    assert cookie_of(response) is None


def test_au5_longest_allowed_fields_reach_the_password_check(app, admin):
    body = {"email": "a" * 242 + "@example.com", "password": "p" * 1024}

    response = call(app.test_client(), "POST", "/login", body)

    assert response.status_code == 401
    assert response.get_json() == INVALID_CREDENTIALS


# --- AU6: what a login attempt logs


def auth_log(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "app.auth"]


def test_au6_successful_login_logs_one_line(app, admin, caplog):
    with caplog.at_level(logging.DEBUG):
        login(app.test_client())

    assert auth_log(caplog) == ["Admin login succeeded."]
    assert [r.levelno for r in caplog.records if r.name == "app.auth"] == [logging.INFO]


@pytest.mark.parametrize(
    "email, password",
    [
        pytest.param(ADMIN_EMAIL, "not the right password", id="wrong-password"),
        pytest.param("someone.else@centre.example", ADMIN_PASSWORD, id="wrong-email"),
    ],
)
def test_au6_failed_login_logs_one_line(app, admin, caplog, email, password):
    with caplog.at_level(logging.DEBUG):
        login(app.test_client(), email=email, password=password)

    assert auth_log(caplog) == ["Admin login failed."]


def test_au6_neither_email_nor_password_is_logged(app, admin, caplog):
    with caplog.at_level(logging.DEBUG):
        login(app.test_client())
        login(app.test_client(), email="someone.else@centre.example", password="secret guess 123")

    assert auth_log(caplog) == ["Admin login succeeded.", "Admin login failed."]
    logged = "\n".join(record.getMessage() for record in caplog.records)
    for private in (ADMIN_EMAIL, ADMIN_PASSWORD, "someone.else@centre.example", "secret guess 123"):
        assert private not in logged


# --- B1: the login body


def test_b1_login_accepts_only_json(app, admin):
    response = app.test_client().post(
        "/api/v1/admin/login",
        data=f"email={ADMIN_EMAIL}&password={ADMIN_PASSWORD}",
        content_type="application/x-www-form-urlencoded",
        base_url="https://localhost",
    )

    assert response.status_code == 415
    assert response.get_json() == {"error": "unsupported_media_type"}
    assert cookie_of(response) is None


@pytest.mark.parametrize("data", ["not json", "[]", '{"email": "a", "email": "b"}'])
def test_b1_login_refuses_an_unreadable_body(app, admin, data):
    response = app.test_client().post(
        "/api/v1/admin/login",
        data=data,
        content_type="application/json",
        base_url="https://localhost",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_request"}


def test_b1_unknown_login_fields_are_ignored(app, admin):
    body = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "remember": True, "role": "owner"}

    assert call(app.test_client(), "POST", "/login", body).status_code == 200


# --- SE1 and SE2: the cookie


def test_se1_cookie_has_the_required_attributes(app, admin):
    value, attributes = cookie_of(login(app.test_client()))

    assert "httponly" in attributes
    assert "secure" in attributes
    assert "samesite=strict" in attributes
    assert "path=/" in attributes
    assert not any(a.startswith(("expires=", "max-age=")) for a in attributes)


def test_se1_cookie_value_is_long_and_different_every_time(app, admin):
    values = {cookie_of(login(app.test_client()))[0] for _ in range(3)}

    assert len(values) == 3
    # 32 random bytes need at least 43 characters in any text form.
    assert all(len(value) >= 43 for value in values)


def test_se2_cookie_value_is_not_stored(app, admin, db):
    value, _ = cookie_of(login(app.test_client()))

    rows = db.execute("SELECT * FROM admin_sessions").fetchall()
    assert len(rows) == 1
    assert all(value not in str(column) for column in rows[0])


# --- R5: who is logged in


def test_r5_session_endpoint_names_the_admin(admin_client):
    response = call(admin_client, "GET", "/session")

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {"email": ADMIN_EMAIL}


# --- SE3: 30 minutes of inactivity


def test_se3_session_is_valid_just_inside_30_minutes(admin_client, clock):
    clock.now = NOW + timedelta(minutes=29, seconds=59)

    assert call(admin_client, "GET", "/session").status_code == 200


def test_se3_session_is_refused_at_exactly_30_minutes(admin_client, clock):
    clock.now = NOW + timedelta(minutes=30)

    response = call(admin_client, "GET", "/session")

    assert response.status_code == 401
    assert response.get_json() == NOT_AUTHENTICATED


def test_se3_each_use_restarts_the_30_minutes(admin_client, clock):
    clock.now = NOW + timedelta(minutes=20)
    assert call(admin_client, "GET", "/session").status_code == 200

    clock.now = NOW + timedelta(minutes=45)  # 25 minutes after the last use
    assert call(admin_client, "GET", "/session").status_code == 200

    clock.now = NOW + timedelta(minutes=75)  # 30 minutes after the last use
    assert call(admin_client, "GET", "/session").status_code == 401


def test_se3_a_refused_request_does_not_revive_an_expired_session(admin_client, clock):
    clock.now = NOW + timedelta(minutes=31)
    assert call(admin_client, "GET", "/session").status_code == 401

    clock.now = NOW + timedelta(minutes=32)
    assert call(admin_client, "GET", "/session").status_code == 401


def test_se3_any_endpoint_that_passes_the_check_counts_as_use(admin_client, clock):
    clock.now = NOW + timedelta(minutes=20)
    assert call(admin_client, "GET", "/bookings").status_code == 200

    clock.now = NOW + timedelta(minutes=45)
    assert call(admin_client, "GET", "/session").status_code == 200


def test_se7_session_in_constant_use_does_not_end(admin_client, clock):
    for step in range(1, 31):  # ten hours, used every 20 minutes
        clock.now = NOW + timedelta(minutes=20 * step)
        assert call(admin_client, "GET", "/session").status_code == 200


# --- SE4: every protected endpoint needs a session

PROTECTED = [
    pytest.param("GET", "/session", None, id="session"),
    pytest.param("POST", "/logout", {}, id="logout"),
    pytest.param("GET", "/bookings", None, id="bookings"),
    pytest.param("PATCH", "/bookings/1/state", {"state": "contacted"}, id="state"),
]


@pytest.mark.parametrize("method, path, body", PROTECTED)
def test_se4_no_cookie_is_refused(app, admin, method, path, body):
    response = call(app.test_client(), method, path, body)

    assert response.status_code == 401
    assert response.content_type == "application/json"
    assert response.get_json() == NOT_AUTHENTICATED


@pytest.mark.parametrize("method, path, body", PROTECTED)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("made-up-value", id="made-up"),
        pytest.param("", id="empty"),
        pytest.param("x" * 3000, id="3000-characters"),
    ],
)
def test_se4_unknown_cookie_is_refused(app, admin, method, path, body, value):
    client = app.test_client()
    client.set_cookie("admin_session", value, domain="localhost")

    response = call(client, method, path, body)

    assert response.status_code == 401
    assert response.get_json() == NOT_AUTHENTICATED


@pytest.mark.parametrize("method, path, body", PROTECTED)
def test_se4_expired_session_is_refused_everywhere(admin_client, clock, method, path, body):
    clock.now = NOW + timedelta(minutes=30)

    response = call(admin_client, method, path, body)

    assert response.status_code == 401
    assert response.get_json() == NOT_AUTHENTICATED


def test_se4_endpoints_that_need_no_session_are_not_refused(app, admin):
    client = app.test_client()

    assert login(client).status_code == 200
    assert (
        call(app.test_client(), "POST", "/password-reset", {"email": "x@example.com"}).status_code
        == 200
    )


# --- O1: the session is checked before anything else


def test_o1_session_comes_before_content_type(app, admin):
    response = app.test_client().patch(
        "/api/v1/admin/bookings/1/state",
        data="state=declined",
        content_type="text/plain",
        base_url="https://localhost",
    )

    assert response.status_code == 401


def test_o1_session_comes_before_validation_and_existence(app, admin):
    response = call(app.test_client(), "PATCH", "/bookings/999999/state", {"state": "nonsense"})

    assert response.status_code == 401
    assert response.get_json() == NOT_AUTHENTICATED


def test_o1_session_comes_before_query_validation(app, admin):
    response = call(app.test_client(), "GET", "/bookings?state=nonsense&page=0")

    assert response.status_code == 401


# --- SE5: logging out


def test_se5_logout_ends_the_session(app, admin, db):
    client = app.test_client()
    value, _ = cookie_of(login(client))

    response = call(client, "POST", "/logout", {})

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {"status": "logged_out"}
    assert db.execute("SELECT count(*) FROM admin_sessions").fetchone()[0] == 0

    # The same cookie value never works again, even if a client keeps sending it.
    stale = app.test_client()
    stale.set_cookie("admin_session", value, domain="localhost", secure=True)
    assert call(stale, "GET", "/session").status_code == 401


def test_se5_logout_clears_the_cookie(admin_client):
    response = call(admin_client, "POST", "/logout", {})

    value, _ = cookie_of(response)
    assert value == ""
    assert call(admin_client, "GET", "/session").status_code == 401


def test_se5_logout_accepts_only_json(admin_client):
    response = admin_client.post(
        "/api/v1/admin/logout", data="", content_type="text/plain", base_url="https://localhost"
    )

    assert response.status_code == 415
    assert call(admin_client, "GET", "/session").status_code == 200


# --- SE6: several sessions


def test_se6_each_login_is_a_separate_session(app, admin):
    first, second = app.test_client(), app.test_client()
    first_value, _ = cookie_of(login(first))
    second_value, _ = cookie_of(login(second))

    assert first_value != second_value
    assert call(first, "GET", "/session").status_code == 200
    assert call(second, "GET", "/session").status_code == 200

    call(first, "POST", "/logout", {})

    assert call(first, "GET", "/session").status_code == 401
    assert call(second, "GET", "/session").status_code == 200


# --- R15: other errors stay JSON


def test_r15_unknown_admin_address_is_a_json_404(admin_client):
    response = call(admin_client, "GET", "/no-such-thing")

    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}


@pytest.mark.parametrize(
    "method, path",
    [("GET", "/login"), ("GET", "/logout"), ("POST", "/session"), ("DELETE", "/bookings")],
)
def test_r15_wrong_method_is_a_json_405(admin_client, method, path):
    response = call(admin_client, method, path)

    assert response.status_code == 405
    assert response.content_type == "application/json"
    assert response.get_json() == {"error": "method_not_allowed"}
