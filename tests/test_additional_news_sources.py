from pathlib import Path
from app import main


def test_three_additional_news_feeds_are_configured():
    feeds = {feed["id"]: feed for feed in main.NEWS_FEEDS}
    assert feeds["securityweek-vuln"]["url"] == "https://www.securityweek.com/category/vulnerabilities/feed/"
    assert feeds["thehackernews"]["url"] == "https://thehackernews.com/feeds/posts/default?alt=rss"
    assert feeds["csirt-chile"]["url"] == "https://csirt.gob.cl/rss/alertas"
    assert len(feeds) == 9


def test_spanish_vulnerability_terms_are_tagged():
    tags = main._news_classify(
        "CSIRT publica alerta por vulnerabilidad crítica",
        "Se recomienda aplicar el parche de seguridad para evitar ejecución remota de código."
    )
    assert "vulnerabilities" in tags


def test_news_ui_has_source_filter_and_new_vulnerability_category():
    base = Path(__file__).resolve().parents[1]
    html = (base / "app/static/index.html").read_text(encoding="utf-8")
    js = (base / "app/static/app.js").read_text(encoding="utf-8")
    assert 'id="intelSourceFilter"' in html
    assert 'data-intel-category="vulnerabilities"' in html
    assert 'vulnerabilities: "Vulnerabilidades"' in js
    assert "1.8.10-nvdmodified" in html
