import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main


def test_health_endpoint_is_cache_only_and_reports_modules(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "health.sqlite3"))
    main.init_db()
    with TestClient(main.app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["version"] == "1.9.3-phishing-reporter-prefill"
    assert set(data["modules"]) == {"platforms", "news", "ransomware", "vulnerabilities"}
    assert data["database"]["engine"] == "SQLite"
    assert data["database"]["persistence"] == "ephemeral"
    assert "never calls vendors" in main.api_health.__doc__.lower()


def test_news_total_failure_preserves_last_success_and_logs_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "news-fail.sqlite3"))
    main.init_db()
    previous = "2026-11-19T12:00:00+00:00"
    with main.db() as conn:
        conn.execute("INSERT INTO threat_news_meta(key,value) VALUES('last_refresh',?)", (previous,))
    with patch.object(main, "_fetch_news_feed", side_effect=RuntimeError("feed offline")):
        result = main.refresh_threat_news()
    assert result["ok"] is False
    assert result["successful_sources"] == 0
    assert result["last_refresh"] == previous
    assert result["last_attempt"] != previous
    with main.db() as conn:
        meta = {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM threat_news_meta")}
        audit = conn.execute("SELECT module,ok FROM refresh_runs ORDER BY id DESC LIMIT 1").fetchone()
    assert meta["last_refresh"] == previous
    assert audit["module"] == "news" and audit["ok"] == 0


def test_nvd_failure_does_not_block_cisa_kev_update(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "vuln-partial.sqlite3"))
    class FakeResponse:
        def __init__(self, payload=None, error=None):
            self.payload, self.error = payload, error
        def raise_for_status(self):
            if self.error:
                raise RuntimeError(self.error)
        def json(self):
            return self.payload

    kev = {"vulnerabilities": [{
        "cveID": "CVE-2026-12345", "vendorProject": "Example", "product": "Agent",
        "vulnerabilityName": "Example RCE", "dateAdded": "2026-11-19",
        "knownRansomwareCampaignUse": "Unknown", "shortDescription": "Test item",
        "requiredAction": "Apply vendor mitigation", "dueDate": "2026-12-01"
    }]}
    def fake_get(url, **kwargs):
        if url == main.CISA_KEV_URL:
            return FakeResponse(kev)
        if url == main.NVD_API_URL:
            return FakeResponse(error="NVD temporarily unavailable")
        if url == main.EPSS_API_URL:
            return FakeResponse({"data": []})
        raise AssertionError(url)

    with patch.object(main.requests, "get", side_effect=fake_get):
        result = main.refresh_vulnerability_intel()
    assert result["ok"] is True
    assert result["partial"] is True
    assert result["kev_count"] == 1
    assert result["nvd_count"] == 0
    assert main.get_vulnerability_intel("all")["items"][0]["cve"] == "CVE-2026-12345"
    source = {item["source"]: item for item in result["sources"]}
    assert source["CISA KEV"]["ok"] is True
    assert source["NVD CVE API"]["ok"] is False
    assert source["FIRST EPSS"]["ok"] is True


def test_refresh_audit_is_bounded_to_latest_100(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "audit.sqlite3"))
    main.init_db()
    for number in range(105):
        main.record_refresh_run("news", True, f"run {number}")
    with main.db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM refresh_runs").fetchone()[0]
        latest = conn.execute("SELECT summary FROM refresh_runs ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert count == 100
    assert latest == "run 104"


def test_platform_source_failure_preserves_last_success_timestamp(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "platform-last-success.sqlite3"))
    main.init_db()
    service = {
        "id": "demo-platform", "name": "Demo Platform", "category": "Testing",
        "portal_label": "Portal", "base_url": "https://example.invalid"
    }
    main.store_result(service, "operational", "Respondió correctamente.", service["base_url"], "operational")
    with main.db() as conn:
        previous = conn.execute("SELECT last_success_at FROM services WHERE id=?", (service["id"],)).fetchone()[0]
    main.store_result(service, "unknown", "No fue posible consultar.", service["base_url"], "", "timeout")
    with main.db() as conn:
        row = conn.execute("SELECT checked_at,last_success_at,error FROM services WHERE id=?", (service["id"],)).fetchone()
    assert row["checked_at"] != previous
    assert row["last_success_at"] == previous
    assert row["error"] == "timeout"
