from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main

class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")
    def json(self):
        return self.payload

def sample_watchguard_payload():
    # This reproduces the exact mismatch from the user's screenshot:
    # global rollup green, but a current minor incident remains in monitoring.
    return {
        "status": {"indicator": "none", "description": "All Systems Operational"},
        "components": [
            {"name": "RADIUS:::AMER", "status": "operational"},
            {"name": "Account Administration:::AMER", "status": "operational"}
        ],
        "incidents": [
            {
                "name": "2026-11-16 - EMEA - WatchGuard Cloud Visibility Dashboards and Reports issues",
                "status": "monitoring",
                "impact": "minor",
                "created_at": "2026-11-16T09:30:00Z",
                "updated_at": "2026-11-18T12:20:00Z",
                "incident_updates": [
                    {"status": "monitoring", "body": "We have implemented changes and continue to monitor.", "created_at": "2026-11-18T12:20:00Z"}
                ]
            }
        ],
        "scheduled_maintenances": []
    }

def test_rollup_green_with_active_minor_incident_is_degraded():
    status, evidence, maintenance = main.statuspage_effective_status(sample_watchguard_payload())
    assert status == "degraded"
    assert evidence and "WatchGuard Cloud Visibility" in evidence[0][1]

def test_card_and_live_detail_use_same_watchguard_status():
    service = {"id":"watchguard","name":"WatchGuard","base_url":"https://status.watchguard.com"}
    payload = sample_watchguard_payload()
    response = FakeResponse(payload)
    with patch.object(main.requests, "get", return_value=response):
        card_status, _, _, _ = main.fetch_statuspage(service)
    with patch.object(main.requests, "get", return_value=response):
        live_detail = main._statuspage_detail(service)
    assert card_status == live_detail["status"] == "degraded"
    assert live_detail["rollup_status"] == "operational"

def test_resolved_incident_does_not_override_green_rollup():
    payload = sample_watchguard_payload()
    payload["incidents"][0]["status"] = "resolved"
    status, _, _ = main.statuspage_effective_status(payload)
    assert status == "operational"
