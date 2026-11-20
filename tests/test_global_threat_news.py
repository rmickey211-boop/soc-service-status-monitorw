from datetime import datetime, timezone
from email.utils import format_datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import main


def _rss_item(title, description, link, published):
    return f"""<item><title>{title}</title><description>{description}</description>
    <link>{link}</link><pubDate>{published}</pubDate></item>"""


def test_news_feed_parser_reads_rss_and_classifies_categories():
    published = format_datetime(datetime.now(timezone.utc))
    xml = f"""<?xml version="1.0"?><rss version="2.0"><channel>
      {_rss_item("SafePay ransomware group claims attack", "A ransomware gang published a claim.", "https://example.org/story", published)}
    </channel></rss>""".encode()
    parsed = main._news_parse_feed(xml)
    assert len(parsed) == 1
    assert parsed[0]["title"] == "SafePay ransomware group claims attack"
    assert "ransomware" in main._news_classify(parsed[0]["title"], parsed[0]["summary"])


def test_news_classifier_supports_requested_categories():
    assert "espionage" in main._news_classify("Nation-state cyber espionage campaign", "")
    assert "leaks" in main._news_classify("Company confirms data breach after records leaked", "")
    assert "ddos" in main._news_classify("DDoS attack disrupts public website", "")
    assert "malware" in main._news_classify("New infostealer malware campaign", "")
    assert main._news_classify("Cyber policy debate worldwide", "") == ["global"]


def test_news_refresh_writes_cache_and_24h_and_7d_filters(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "news.sqlite3"))
    published = datetime.now(timezone.utc).isoformat()
    sample = [{
        "title": "Ransomware group targets public organization",
        "summary": "A public report describes a ransomware claim.",
        "link": "https://example.org/ransomware-report",
        "published_at": published,
    }]

    def fake_fetch(feed):
        return sample

    with patch.object(main, "_fetch_news_feed", side_effect=fake_fetch):
        result = main.refresh_threat_news()

    assert result["successful_sources"] == 9
    assert result["fetched"] == 9  # same URL from each feed; cache deduplicates on upsert
    seven_days = main.get_cached_threat_news("7d")
    one_day = main.get_cached_threat_news("24h")
    assert seven_days["count"] == 1
    assert one_day["count"] == 1
    assert "ransomware" in seven_days["items"][0]["categories"]


def test_news_api_rejects_unknown_period():
    with TestClient(main.app) as client:
        response = client.get("/api/threat-intel/news?period=30d")
    assert response.status_code == 400


def test_news_refresh_api_uses_only_public_feed_functions():
    with patch.object(main, "_fetch_news_feed", return_value=[]):
        with TestClient(main.app) as client:
            response = client.post("/api/threat-intel/news/refresh")
    assert response.status_code == 200
    assert response.json()["successful_sources"] == 9


def test_cybersecurity_news_is_configured_as_public_rss_source():
    feed = next((item for item in main.NEWS_FEEDS if item["id"] == "cybersecuritynews"), None)
    assert feed is not None
    assert feed["name"] == "Cyber Security News"
    assert feed["url"] == "https://cybersecuritynews.com/feed/"


def test_cybersecurity_news_entries_are_ingested_and_attributed():
    published = datetime.now(timezone.utc).isoformat()
    sample = [{
        "title": "Critical malware campaign targets enterprise networks",
        "summary": "Researchers observed a malware campaign.",
        "link": "https://cybersecuritynews.com/example-malware-campaign/",
        "published_at": published,
    }]
    def fake_fetch(feed):
        return sample if feed["id"] == "cybersecuritynews" else []
    with patch.object(main, "_fetch_news_feed", side_effect=fake_fetch):
        result = main.refresh_threat_news()
    assert result["successful_sources"] == 9
    data = main.get_cached_threat_news("7d")
    item = next(item for item in data["items"] if item["source"] == "Cyber Security News")
    assert item["link"].startswith("https://cybersecuritynews.com/")
    assert "malware" in item["categories"]


def test_news_classifier_supports_vulnerability_subcategory():
    cve_tags = main._news_classify(
        "CVE-2026-12345 exploited in the wild",
        "Researchers report a critical remote code execution flaw."
    )
    assert "global" in cve_tags
    assert "vulnerabilities" in cve_tags

    zero_day_tags = main._news_classify(
        "Zero-day vulnerability in enterprise VPN appliances",
        "Vendor releases an emergency security patch."
    )
    assert "vulnerabilities" in zero_day_tags

    general_tags = main._news_classify(
        "New data center expansion announced",
        "Company plans a new facility."
    )
    assert "vulnerabilities" not in general_tags


def test_news_categories_include_vulnerabilities_label():
    assert main.NEWS_CATEGORIES["vulnerabilities"] == "Vulnerabilidades"


def test_additional_public_sources_are_configured():
    feeds = {item["id"]: item for item in main.NEWS_FEEDS}
    assert feeds["securityweek-vuln"]["name"] == "SecurityWeek · Vulnerabilities"
    assert feeds["securityweek-vuln"]["url"] == "https://www.securityweek.com/category/vulnerabilities/feed/"
    assert feeds["thehackernews"]["url"] == "https://thehackernews.com/feeds/posts/default?alt=rss"
    assert feeds["csirt-chile"]["url"] == "https://csirt.gob.cl/rss/alertas"


def test_spanish_csirt_vulnerability_and_threat_terms_are_classified():
    vulnerability = main._news_classify(
        "Alerta de seguridad: vulnerabilidad crítica en producto VPN",
        "Se recomienda instalar el parche de seguridad para evitar ejecución remota de código."
    )
    assert "vulnerabilities" in vulnerability

    malware = main._news_classify(
        "CSIRT advierte campaña de phishing y software malicioso",
        "La campaña busca robar credenciales."
    )
    assert "malware" in malware

    leakage = main._news_classify(
        "Alerta por filtración de datos personales",
        "Se detectó exposición de datos."
    )
    assert "leaks" in leakage
