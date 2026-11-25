from pathlib import Path


def test_phishing_reporter_is_in_sidebar_and_has_all_eight_vendors():
    base = Path(__file__).resolve().parents[1]
    html = (base / "app/static/index.html").read_text(encoding="utf-8")
    js = (base / "app/static/app.js").read_text(encoding="utf-8")
    assert 'data-nav="phishing"' in html
    assert 'id="view-phishing"' in html
    for vendor in ("virustotal", "fortiguard", "google", "netcraft", "eset", "cloudflare", "urlabuse", "watchguard"):
        assert f'data-vendor="{vendor}"' in html
    assert 'phishing:"Phishing URL Reporter"' in js


def test_reporter_is_browser_only_and_does_not_add_backend_routes_or_dependencies():
    base = Path(__file__).resolve().parents[1]
    js = (base / "app/static/app.js").read_text(encoding="utf-8")
    main = (base / "app/main.py").read_text(encoding="utf-8")
    requirements = (base / "requirements.txt").read_text(encoding="utf-8")
    assert "navigator.clipboard" in js
    assert "window.open(target" in js
    assert "fetch(" not in js[js.index("// v1.9.1 — Phishing URL Reporter"):]
    assert "@app.post(\"/api/phishing" not in main
    assert "playwright" not in requirements.lower()
    assert "selenium" not in requirements.lower()


def test_reporter_requires_manual_confirmation_after_portal_open():
    base = Path(__file__).resolve().parents[1]
    html = (base / "app/static/index.html").read_text(encoding="utf-8")
    js = (base / "app/static/app.js").read_text(encoding="utf-8")
    assert 'class="phishing-confirm" disabled' in html
    assert "window.confirm(`¿Confirmas que completaste y enviaste" in js
    assert "Confirmado por analista" in js
