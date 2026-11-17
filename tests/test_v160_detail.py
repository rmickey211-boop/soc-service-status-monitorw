from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")
    def json(self):
        return self.payload

def test_statuspage_detail_returns_components_incidents():
    payload = {
        "status": {"indicator": "minor", "description": "Performance Degraded"},
        "components": [{"name": "Console", "status": "degraded_performance", "description": "Delayed updates"}],
        "incidents": [{"name": "Endpoint console issue", "status": "identified", "impact": "minor",
                       "incident_updates": [{"status": "identified", "body": "Issue identified", "created_at": "2026-11-17T12:00:00Z"}]}],
        "scheduled_maintenances": []
    }
    with patch("app.main.requests.get", return_value=FakeResponse(payload)):
        with TestClient(app) as client:
            response = client.get("/api/services/watchguard/detail")
    assert response.status_code == 200
    body = response.json()
    assert body["live"]["components"][0]["name"] == "Console"
    assert body["live"]["incidents"][0]["updates"][0]["body"] == "Issue identified"

def test_manual_service_detail_explains_manual_validation():
    with TestClient(app) as client:
        response = client.get("/api/services/wazuh/detail")
    assert response.status_code == 200
    assert response.json()["live"]["status"] == "manual"
