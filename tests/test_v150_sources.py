from unittest.mock import patch
from app import main

class FakeResponse:
    def __init__(self, payload=None, content=b"", status=200):
        self._payload = payload
        self.content = content
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")
    def json(self):
        return self._payload

def test_catalog_automatic_sources():
    cfg = main.load_config()
    by_id = {s["id"]: s for s in cfg["services"]}
    assert by_id["watchguard"]["type"] == "watchguard"
    assert by_id["fortinet"]["type"] == "statuspage"
    assert by_id["zoom"]["type"] == "statuspage"
    assert "webex" not in by_id
    assert by_id["microsoft-azure"]["type"] == "microsoft_public"
    assert by_id["power-platform"]["type"] == "microsoft_public"
    assert by_id["microsoft-365-public"]["type"] == "microsoft_public"

def test_microsoft_available_mapping():
    svc = {"name":"Microsoft Azure","base_url":"https://status.cloud.microsoft/","api_url":"https://status.cloud.microsoft/api/posts/azure"}
    response = FakeResponse({"Status":"Available","Message":"No Azure issues detected at this time.","LastUpdatedTime":"2026-11-17T18:01:00Z"})
    with patch.object(main.requests, "get", return_value=response):
        status, description, url, raw = main.fetch_microsoft_public(svc)
    assert status == "operational"
    assert "No Azure issues" in description

def test_watchguard_statuspage_summary_mapping():
    svc = {"name":"WatchGuard","base_url":"https://status.watchguard.com"}
    payload = {
        "status":{"indicator":"minor","description":"Performance Degraded"},
        "components":[{"name":"Endpoint Security Administration","status":"degraded_performance"}],
        "incidents":[{"name":"Endpoint Security Console issues","impact":"minor"}],
        "scheduled_maintenances":[]
    }
    with patch.object(main.requests, "get", return_value=FakeResponse(payload)):
        status, description, url, raw = main.fetch_watchguard(svc)
    assert status == "degraded"
    assert "Endpoint Security" in description


def test_microsoft_degraded_mapping():
    svc = {"name":"Microsoft 365","base_url":"https://status.cloud.microsoft/","api_url":"https://status.cloud.microsoft/api/posts/mac"}
    response = FakeResponse({"Status":"ServiceDegradation","Title":"Exchange Online","Message":"Some users may experience delayed mail delivery.","LastUpdatedTime":"2026-11-17T12:00:00Z"})
    with patch.object(main.requests, "get", return_value=response):
        status, description, url, raw = main.fetch_microsoft_public(svc)
    assert status == "degraded"
    assert "delayed mail delivery" in description

def test_watchguard_atom_fallback_when_summary_fails():
    svc = {"name":"WatchGuard","base_url":"https://status.watchguard.com","feed_url":"https://status.watchguard.com/history.atom"}
    atom = b"""<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'><entry><title>Endpoint Security Administration and Console</title><content>Identified - We continue to experience service degradation affecting the WatchGuard Endpoint Security Administration and Console.</content></entry></feed>"""
    def fake_get(url, timeout=None, headers=None):
        if url.endswith("/api/v2/summary.json"):
            return FakeResponse({}, status=503)
        return FakeResponse(content=atom)
    with patch.object(main.requests, "get", side_effect=fake_get):
        status, description, url, raw = main.fetch_watchguard(svc)
    assert status == "degraded"
    assert "Endpoint Security" in description
