from pathlib import Path
from app import main


def test_global_refresh_button_calls_all_four_module_refresh_routes():
    base = Path(__file__).resolve().parents[1]
    js = (base / "app/static/app.js").read_text(encoding="utf-8")
    html = (base / "app/static/index.html").read_text(encoding="utf-8")
    assert 'id="homeRefresh"' in html
    assert 'id="homeRefreshSummary"' in html
    for endpoint in (
        "/api/poll",
        "/api/threat-intel/news/refresh",
        "/api/threat-intel/ransomware/refresh",
        "/api/threat-intel/vulnerabilities/refresh",
    ):
        assert endpoint in js
    for loader in ("load()", "loadIntelNews()", "loadRansomware()", "loadVulnerabilities()"):
        assert loader in js
    assert "Promise.all(jobs.map" in js


def test_global_refresh_preserves_ransomware_refresh_individual_rate_limit():
    # The global dashboard invokes the same public ransomware refresh route
    # as the module button, retaining its existing server-side cache guard.
    assert "RANSOMLOOK_REFRESH_FLOOR_MINUTES = 15" in Path(main.__file__).read_text(encoding="utf-8")
