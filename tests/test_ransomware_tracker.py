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
    with patch.object(main, "_fetch_ransomlook_posts", return_value=source_posts), patch.object(main, "_fetch_ransomwarelive_rss", return_value=[]):
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
    with patch.object(main, "_fetch_ransomlook_posts", return_value=sample) as fetch, patch.object(main, "_fetch_ransomwarelive_rss", return_value=[]):
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
    with patch.object(main, "_fetch_ransomlook_posts", return_value=sample), patch.object(main, "_fetch_ransomwarelive_rss", return_value=[]):
        with TestClient(main.app) as client:
            response = client.post("/api/threat-intel/ransomware/refresh")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["successful_sources"] == 2


def test_ransomwarelive_rss_parser_extracts_group_victim_and_date(monkeypatch):
    class FakeResponse:
        content = b"""<?xml version='1.0'?><rss version='2.0'><channel><item>
        <title>Qilin has just published a new victim : Example Corp</title>
        <link>https://www.ransomware.live/group/qilin</link>
        <pubDate>Wed, 19 Nov 2026 10:00:00 GMT</pubDate>
        <description><![CDATA[Example Corp is based in Chile.]]></description>
        </item></channel></rss>"""
        def raise_for_status(self): pass
    with patch.object(main.requests, "get", return_value=FakeResponse()):
        records = main._fetch_ransomwarelive_rss()
    assert len(records) == 1
    assert records[0]["group_name"] == "Qilin"
    assert records[0]["post_title"] == "Example Corp"
    assert records[0]["discovered"].startswith("Wed, 19 Nov")


def test_ransomware_record_keeps_source_and_source_link():
    item = _post("Example Corp", "Qilin", datetime.now(timezone.utc).isoformat(),
                 "Example Corp is a Chilean company.")
    item["link"] = "https://www.ransomware.live/group/qilin"
    record = main._ransom_build_record(item, source="Ransomware.live")
    assert record["source"] == "Ransomware.live"
    assert record["country_code"] == "CL"


def test_ransomwarelive_is_aggregate_only_on_public_api(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "ransomware.sqlite3"))
    now = datetime.now(timezone.utc).isoformat()
    rl = [_post("Named Victim from Ransomware.live", "Qilin", now, "Victim is a Chilean company.",
                "https://www.ransomware.live/group/qilin")]
    with patch.object(main, "_fetch_ransomlook_posts", return_value=[]), patch.object(main, "_fetch_ransomwarelive_rss", return_value=rl):
        result = main.refresh_ransomware_tracker()
    data = main.get_cached_ransomware("7d")
    assert result["ok"] is True
    assert data["count"] == 1
    assert data["items"] == []
    assert data["countries_count"] == 1
    assert data["countries"][0]["code"] == "CL"
    assert data["top_groups"][0]["name"] == "Qilin"
    assert data["sources"][1]["source"] == "Ransomware.live"


def test_ransomware_schema_migrates_source_column(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "legacy.sqlite3"))
    with main.db() as c:
        c.execute("""CREATE TABLE ransomware_posts (
            id TEXT PRIMARY KEY, victim TEXT NOT NULL, group_name TEXT NOT NULL,
            discovered_at TEXT NOT NULL, description TEXT, source_link TEXT NOT NULL,
            country_code TEXT, country_name TEXT, country_lat REAL, country_lon REAL,
            country_basis TEXT, cached_at TEXT NOT NULL)""")
    main.init_db()
    with main.db() as c:
        columns = {row[1] for row in c.execute("PRAGMA table_info(ransomware_posts)")}
    assert "source" in columns
