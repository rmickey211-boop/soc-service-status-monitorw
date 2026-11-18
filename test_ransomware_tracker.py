from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import main


def _post(victim, group, discovered, description="", link=None):
    return {
        "post_title": victim,
        "group_name": group,
        "discovered": discovered,
        "description": description,
        "link": link,
    }


def test_ransomlook_country_detection_requires_one_unambiguous_country():
    dutch = main._ransom_detect_country(
        "Techmar is a Dutch company headquartered in Hengelo, Netherlands."
    )
    assert dutch and dutch["code"] == "NL"

    ivorian = main._ransom_detect_country(
        "Mayelia Automotive is an Ivorian automotive company specializing in inspections."
    )
    assert ivorian and ivorian["code"] == "CI"

    ambiguous = main._ransom_detect_country(
        "A Canadian company with headquarters in the United States."
    )
    assert ambiguous is None

    unknown = main._ransom_detect_country("Global organization operating in many markets.")
    assert unknown is None
    assert main._ransom_detect_country("", victim="Jordan Capital Group") is None


def test_ransomware_refresh_caches_posts_country_and_group_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "ransomware.sqlite3"))
    now = datetime.now(timezone.utc)
    source_posts = [
        _post("Techmar", "The Gentlemen", now.isoformat(),
              "Techmar is a Dutch company headquartered in Hengelo, Netherlands."),
        _post("Mayelia Automotive", "Qilin", now.isoformat(),
              "Mayelia is an Ivorian automotive company."),
        _post("Unknown Ltd", "Qilin", (now - timedelta(days=5)).isoformat(),
              "A global organization without a clear country."),
    ]
    with patch.object(main, "_fetch_ransomlook_posts", return_value=source_posts):
        result = main.refresh_ransomware_tracker()

    assert result["ok"] is True
    assert result["fetched"] == 3
    data = main.get_cached_ransomware("7d")
    assert data["count"] == 3
    assert data["groups_count"] == 2
    assert data["countries_count"] == 2
    assert data["unmapped_count"] == 1
    assert {item["code"] for item in data["countries"]} == {"NL", "CI"}
    assert data["top_groups"][0]["name"] == "Qilin"

    day = main.get_cached_ransomware("24h")
    assert day["count"] == 2


def test_ransomware_refresh_reuses_cache_within_15_minutes(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "ransomware.sqlite3"))
    sample = [_post("Example Victim", "Example Group", datetime.now(timezone.utc).isoformat(), "A Dutch business.")]
    with patch.object(main, "_fetch_ransomlook_posts", return_value=sample) as fetch:
        first = main.refresh_ransomware_tracker()
        second = main.refresh_ransomware_tracker()
    assert first["ok"] is True
    assert second["skipped"] is True
    assert fetch.call_count == 1


def test_ransomware_api_period_validation_and_cache_read(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "ransomware.sqlite3"))
    main.init_db()
    with TestClient(main.app) as client:
        bad = client.get("/api/threat-intel/ransomware?period=30d")
        good = client.get("/api/threat-intel/ransomware?period=7d")
    assert bad.status_code == 400
    assert good.status_code == 200
    assert good.json()["count"] == 0


def test_ransomware_refresh_api_uses_public_source_adapter(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "ransomware.sqlite3"))
    sample = [_post("Example Victim", "Example Group", datetime.now(timezone.utc).isoformat(), "A Dutch business.")]
    with patch.object(main, "_fetch_ransomlook_posts", return_value=sample):
        with TestClient(main.app) as client:
            response = client.post("/api/threat-intel/ransomware/refresh")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["successful_sources"] == 1
