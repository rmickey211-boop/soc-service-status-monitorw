from fastapi.testclient import TestClient
from app.main import app

def test_catalog_is_available_before_first_refresh():
    with TestClient(app) as client:
        response = client.get("/api/status")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["services"]) >= 30
        assert payload["counts"]["manual"] > 0

def test_manual_refresh_route_exists():
    # Network requests are not mocked here; this checks only route registration.
    assert any(route.path == "/api/poll" and "POST" in route.methods for route in app.routes)
