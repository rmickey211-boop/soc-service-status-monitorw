from pathlib import Path


def test_sidebar_has_direct_links_to_home_and_all_four_modules():
    base = Path(__file__).resolve().parents[1]
    html = (base / "app/static/index.html").read_text(encoding="utf-8")
    for module in ("home", "platforms", "news", "ransomware", "vulns"):
        assert f'data-nav="{module}"' in html
    assert 'id="socSidebar"' in html
    assert 'id="sidebarCollapse"' in html
    assert 'id="mobileMenuToggle"' in html
    assert 'id="sidebarScrim"' in html


def test_old_large_module_cards_and_back_home_navigation_are_removed():
    base = Path(__file__).resolve().parents[1]
    html = (base / "app/static/index.html").read_text(encoding="utf-8")
    js = (base / "app/static/app.js").read_text(encoding="utf-8")
    assert 'class="module-card"' not in html
    assert 'id="backHome"' not in html
    assert 'data-open-module' not in html
    assert '$("backHome")' not in js


def test_sidebar_navigation_has_desktop_collapse_and_mobile_drawer_behaviour():
    base = Path(__file__).resolve().parents[1]
    js = (base / "app/static/app.js").read_text(encoding="utf-8")
    css = (base / "app/static/style.css").read_text(encoding="utf-8")
    assert 'item.addEventListener("click"' in js
    assert 'function showHome()' in js
    assert 'function showModule(name)' in js
    assert 'mobile-sidebar-open' in js
    assert '.sidebar-collapsed' in css
    assert '.sidebar-scrim' in css
