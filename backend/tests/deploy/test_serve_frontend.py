"""Serving the built frontend: rules G1 to G10 of docs/specs/deploy.md.

Every expected value comes from that spec; each test names the rule it checks.
"""

import logging

import pytest

INDEX = b"<!doctype html><title>Community Centre</title><div id=root></div>"
SCRIPT = b"console.log('app');"
ICON = b"\x00\x00\x01\x00icon"
SECRET = b"not for visitors"

NOT_FOUND = {"error": "not_found"}
FOREVER = "public, max-age=31536000, immutable"


@pytest.fixture
def dist(tmp_path):
    """A made-up built frontend, with a file next to it that must never be served."""
    folder = tmp_path / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_bytes(INDEX)
    (folder / "assets" / "app-abc123.js").write_bytes(SCRIPT)
    (folder / "favicon.ico").write_bytes(ICON)
    (tmp_path / "secret.txt").write_bytes(SECRET)
    return folder


@pytest.fixture
def site(app, dist):
    """A client of the application with the frontend switched on."""
    app.config["FRONTEND_DIST"] = str(dist)
    return app.test_client()


def is_index(response):
    return (
        response.status_code == 200
        and response.mimetype == "text/html"
        and response.get_data() == INDEX
    )


def is_json_404(response):
    return (
        response.status_code == 404
        and response.mimetype == "application/json"
        and response.get_json() == NOT_FOUND
    )


# --- G1: without the setting, nothing changes


@pytest.mark.parametrize("setting", [None, ""])
@pytest.mark.parametrize("path", ["/", "/facilities", "/assets/app-abc123.js", "/index.html"])
def test_g1_without_the_setting_every_address_is_a_json_404(app, dist, setting, path):
    app.config["FRONTEND_DIST"] = setting

    assert is_json_404(app.test_client().get(path))


# --- G2: files of the folder


def test_g2_a_script_is_served_with_its_content_type(site):
    response = site.get("/assets/app-abc123.js")

    assert response.status_code == 200
    assert response.get_data() == SCRIPT
    assert response.mimetype in ("text/javascript", "application/javascript")


def test_g2_a_file_in_the_top_of_the_folder_is_served(site):
    response = site.get("/favicon.ico")

    assert response.status_code == 200
    assert response.get_data() == ICON


def test_g2_index_html_can_be_asked_for_by_name(site):
    assert is_index(site.get("/index.html"))


# --- G3: every other address gets index.html


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/facilities",
        "/gallery",
        "/events",
        "/faq",
        "/terms",
        "/privacy",
        "/admin",
        "/no-such-page",
        "/facilities/x",
        "/assets/no-such-file.js",
        "/healthy",
    ],
)
def test_g3_an_address_without_a_file_gets_index_html(site, path):
    assert is_index(site.get(path))


def test_g3_the_query_string_makes_no_difference(site):
    assert is_index(site.get("/facilities?from=home"))


# --- G4: the API and /health are never answered with the frontend


@pytest.mark.parametrize(
    "path",
    ["/api", "/api/", "/api/v1", "/api/v1/no-such-thing", "/api/v1/bookings/", "/api/index.html"],
)
def test_g4_unknown_api_addresses_stay_json_404(site, path):
    assert is_json_404(site.get(path))


def test_g4_health_is_unchanged(site):
    response = site.get("/health")

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.get_json()["status"] == "ok"


def test_g4_the_booking_address_still_refuses_get(site):
    response = site.get("/api/v1/bookings")

    assert response.status_code == 405
    assert response.mimetype == "application/json"


# --- G5: only GET and HEAD


def test_g5_head_is_answered_like_get_without_a_body(site):
    response = site.head("/facilities")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.get_data() == b""


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("path", ["/", "/facilities", "/assets/app-abc123.js"])
def test_g5_other_methods_stay_json_404(site, method, path):
    assert is_json_404(site.open(path, method=method))


# --- G6: nothing outside the folder


@pytest.mark.parametrize(
    "path",
    [
        "/../secret.txt",
        "/assets/../../secret.txt",
        "/%2e%2e/secret.txt",
        "/assets/%2e%2e/%2e%2e/secret.txt",
        "/..%2fsecret.txt",
        "//secret.txt",
    ],
)
def test_g6_an_address_that_leaves_the_folder_never_gets_the_file(site, path):
    response = site.get(path)

    assert SECRET not in response.get_data()
    assert is_index(response)


def test_g6_an_absolute_path_is_not_served(site, dist):
    outside = dist.parent / "secret.txt"

    response = site.get(f"/{outside}")

    assert SECRET not in response.get_data()
    assert is_index(response)


@pytest.mark.parametrize("path", ["/assets", "/assets/"])
def test_g6_a_folder_is_not_a_file(site, path):
    assert is_index(site.get(path))


# --- G7: caching


@pytest.mark.parametrize("path", ["/", "/facilities", "/index.html", "/no-such-page"])
def test_g7_index_html_is_not_cached(site, path):
    assert site.get(path).headers["Cache-Control"] == "no-cache"


def test_g7_files_under_assets_are_cached_for_good(site):
    assert site.get("/assets/app-abc123.js").headers["Cache-Control"] == FOREVER


def test_g7_other_files_are_not_cached(site):
    assert site.get("/favicon.ico").headers["Cache-Control"] == "no-cache"


def test_g7_a_missing_file_under_assets_is_not_cached_for_good(site):
    assert site.get("/assets/no-such-file.js").headers["Cache-Control"] == "no-cache"


# --- G8: nosniff


@pytest.mark.parametrize("path", ["/", "/facilities", "/assets/app-abc123.js", "/favicon.ico"])
def test_g8_every_answer_carries_nosniff(site, path):
    assert site.get(path).headers["X-Content-Type-Options"] == "nosniff"


# --- G9: a folder without index.html


def test_g9_without_index_html_the_answer_is_a_json_404(site, dist):
    (dist / "index.html").unlink()

    assert is_json_404(site.get("/"))
    assert is_json_404(site.get("/facilities"))
    assert site.get("/assets/app-abc123.js").get_data() == SCRIPT


def test_g9_a_folder_that_does_not_exist_is_a_json_404(app, tmp_path):
    app.config["FRONTEND_DIST"] = str(tmp_path / "nowhere")

    assert is_json_404(app.test_client().get("/"))


# --- G10: no database, no log line


def test_g10_serving_reads_no_database_and_logs_nothing(app, site, caplog):
    app.config["DATABASE_URL"] = "postgresql://nobody:nothing@127.0.0.1:1/nowhere"
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        assert is_index(site.get("/"))
        assert site.get("/assets/app-abc123.js").status_code == 200

    assert [record for record in caplog.records if record.name.startswith("app")] == []
