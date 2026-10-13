"""F02 rules found untested by the branch review: AU2, PR1, PR4 and ST10 with
text the database or the hashing cannot hold.

Every expected value comes from docs/specs/F02.md; each test names the rule it checks.
"""

import logging

import pytest
from f02_helpers import ADMIN_EMAIL, ADMIN_PASSWORD, call, login

INVALID_CREDENTIALS = {"error": "invalid_credentials"}

# A NUL character, and an unpaired surrogate: valid in JSON, but not storable text.
NUL = "\x00"
SURROGATE = "\ud800"


# --- AU2: a wrong email or password is always R2, whatever it contains


@pytest.mark.parametrize(
    "email, password",
    [
        pytest.param(f"admin{NUL}@centre.example", ADMIN_PASSWORD, id="nul-in-email"),
        pytest.param(f"admin{SURROGATE}@centre.example", ADMIN_PASSWORD, id="surrogate-in-email"),
        pytest.param(ADMIN_EMAIL, f"{ADMIN_PASSWORD}{NUL}", id="nul-in-password"),
        pytest.param(ADMIN_EMAIL, f"{ADMIN_PASSWORD}{SURROGATE}", id="surrogate-in-password"),
        pytest.param(NUL, NUL, id="only-nuls"),
        pytest.param(SURROGATE, SURROGATE, id="only-surrogates"),
    ],
)
def test_au2_unstorable_text_is_just_a_wrong_email_or_password(app, admin, email, password):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    response = login(app.test_client(), email=email, password=password)

    assert response.status_code == 401
    assert response.content_type == "application/json"
    assert response.get_json() == INVALID_CREDENTIALS
    # The account is unharmed.
    assert login(app.test_client()).status_code == 200


# --- PR1: the reset response is always R10


@pytest.mark.parametrize(
    "email",
    [
        pytest.param(f"admin{NUL}@centre.example", id="nul"),
        pytest.param(f"admin{SURROGATE}@centre.example", id="surrogate"),
    ],
)
def test_pr1_unstorable_email_gets_the_same_response_and_no_email(app, admin, caplog, email):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    with caplog.at_level(logging.INFO, logger="app.email"):
        response = call(app.test_client(), "POST", "/password-reset", {"email": email})

    assert response.status_code == 200
    assert response.get_json() == {"status": "reset_requested"}
    assert [record for record in caplog.records if record.name == "app.email"] == []


# --- PR4: a token that is not the stored one is R12, whatever it contains


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(f"token{NUL}token", id="nul"),
        pytest.param(f"token{SURROGATE}token", id="surrogate"),
    ],
)
def test_pr4_unstorable_token_is_just_an_invalid_token(app, admin, token):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    call(app.test_client(), "POST", "/password-reset", {"email": ADMIN_EMAIL})

    response = call(
        app.test_client(),
        "POST",
        "/password-reset/confirm",
        {"token": token, "password": "a brand new password"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid_token"}
    assert login(app.test_client()).status_code == 200


# --- ST10: an ID that matches no booking is R9, however long it is


@pytest.mark.parametrize("digits", [4301, 5000])
def test_st10_very_long_booking_id_is_not_found(app, admin_client, digits):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    response = call(
        admin_client, "PATCH", "/bookings/" + "9" * digits + "/state", {"state": "contacted"}
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}
