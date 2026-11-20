from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def test_news_source_filter_is_present_and_combines_with_category():
    html = (BASE / "app" / "static" / "index.html").read_text(encoding="utf-8")
    js = (BASE / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="intelSourceFilter"' in html
    assert "let intelSource = \"all\"" in js
    assert "intelSourceResults.map" in js
    assert "const chartItems = intelItems.filter" in js
    assert 'intelCategory === "all" || (item.categories || []).includes(intelCategory)' in js
    assert 'intelSource === "all" || item.source === intelSource' in js
    assert 'value="all">Todas las fuentes' in js


def test_vulnerability_news_category_is_visible_in_news_filters():
    html = (BASE / "app" / "static" / "index.html").read_text(encoding="utf-8")
    js = (BASE / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'data-intel-category="vulnerabilities"' in html
    assert 'vulnerabilities: "Vulnerabilidades"' in js
