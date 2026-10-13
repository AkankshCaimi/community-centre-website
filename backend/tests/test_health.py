"""Smoke test. Expected values come from docs/specs/skeleton.md, "Health endpoint"."""


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {"status": "ok"}
