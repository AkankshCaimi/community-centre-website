"""Smoke test. Expected values come from docs/specs/skeleton.md, "Health endpoint",
and docs/specs/F03.md, R6."""


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.content_type == "application/json"
    body = response.get_json()
    assert body["status"] == "ok"
    # Since F03 the body also says when the auto-decline job last ran (F03 R6).
    # Its value depends on the database this test happens to run against, so
    # only its presence is checked here; the F03 tests check the values.
    assert set(body) == {"status", "auto_decline_last_run"}
