from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")

def test_sidebar_navigation_has_matching_module_views():
    for name in ("platforms", "news", "ransomware", "vulns"):
        assert f'data-nav="{name}"' in HTML
        assert f'id="view-{name}"' in HTML
        assert f'{name}:"' in JS

def test_removed_checklist_has_no_live_dom_bindings():
    assert "Checklist MDR" not in HTML
    for obsolete_id in ("selectAll", "clearAll", "saveChecklist", "analyst", "checkMsg"):
        assert f'$({chr(34)}{obsolete_id}{chr(34)})' not in JS

def test_all_literal_dom_references_exist():
    ids = set(re.findall(r'id=["\']([^"\']+)', HTML))
    refs = set(re.findall(r'\$\(["\']([^"\']+)["\']\)', JS))
    assert refs - ids == set()

def test_official_portal_screenshot_removed():
    assert "portalScreenshot" not in HTML + JS
    assert "screenshotLoading" not in HTML + JS
