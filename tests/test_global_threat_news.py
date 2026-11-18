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


def test_news_refresh_writes_cache_and_24h_and_7d_filters():
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

    assert result["successful_sources"] == 5
    assert result["fetched"] == 5  # same URL from each feed; cache deduplicates on upsert
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
    assert response.json()["successful_sources"] == 5
