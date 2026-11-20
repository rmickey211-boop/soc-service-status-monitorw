from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
HTML = (BASE / "app/static/index.html").read_text(encoding="utf-8")
JS = (BASE / "app/static/app.js").read_text(encoding="utf-8")
CSS = (BASE / "app/static/style.css").read_text(encoding="utf-8")


def test_platform_module_has_status_category_and_transition_charts():
    for element_id in ("platformStateDonut", "platformCategoryBars", "platformEventTrend"):
        assert f'id="{element_id}"' in HTML
    assert "renderPlatformAnalytics(cache,events)" in JS


def test_news_module_has_timeline_category_and_source_charts():
    for element_id in ("intelTrendChart", "intelCategoryChart", "intelSourceChart"):
        assert f'id="{element_id}"' in HTML
    assert "renderNewsAnalytics(visible)" in JS


def test_ransomware_module_has_timeline_and_group_chart():
    for element_id in ("rwTimelineChart", "rwGroupChart"):
        assert f'id="{element_id}"' in HTML
    assert "renderRansomwareAnalytics(data)" in JS


def test_vulnerability_module_has_severity_epss_and_kev_charts():
    for element_id in ("vulnSeverityChart", "vulnEpssChart", "vulnKevChart"):
        assert f'id="{element_id}"' in HTML
    assert "renderVulnerabilityAnalytics(vulnRowsCache)" in JS


def test_phase_two_charts_are_responsive_and_do_not_require_external_chart_libraries():
    assert ".module-chart-grid" in CSS
    assert "@media(max-width:650px)" in CSS
    assert "chart.js" not in HTML.lower()


def test_phase_two_script_has_no_standalone_async_expression():
    # A bare `async` is syntactically valid JavaScript but throws at runtime,
    # aborting the entire app before any handlers or fetches are initialized.
    import re
    assert not re.search(r"(?m)^\s*async\s*$", JS)
