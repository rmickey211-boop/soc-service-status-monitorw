from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
HTML = (BASE / "app/static/index.html").read_text(encoding="utf-8")
JS = (BASE / "app/static/app.js").read_text(encoding="utf-8")
MAIN = (BASE / "app/main.py").read_text(encoding="utf-8")
CSS = (BASE / "app/static/style.css").read_text(encoding="utf-8")


def test_each_module_has_an_accessible_active_filter_region():
    for element_id in ("platformDrillFilter", "intelDrillFilter", "rwDrillFilter", "vulnDrillFilter"):
        assert f'id="{element_id}"' in HTML
        assert "aria-live=\"polite\"" in HTML


def test_charts_expose_drilldown_actions_for_each_module():
    for action in (
        "platform-status", "platform-category", "platform-event-date",
        "intel-category", "intel-source", "intel-date",
        "rw-group", "rw-date", "vuln-severity", "vuln-epss", "vuln-kev",
    ):
        assert action in JS
    assert 'data-chart-filter' in JS
    assert 'data-clear-drill' in JS


def test_vulnerability_chart_filters_table_without_reloading_data():
    assert "function getFilteredVulnerabilities()" in JS
    assert "function renderVulnerabilityTable()" in JS
    assert "renderVulnerabilityTable();renderVulnerabilityAnalytics(vulnRowsCache)" in JS


def test_ransomware_timeline_provides_utc_bucket_ranges_for_filtering():
    assert '"key": bucket.strftime("%Y-%m-%dT%H:%M:%SZ")' in MAIN
    assert '"start": int(bucket.timestamp() * 1000)' in MAIN
    assert '"end": int((bucket + timedelta(seconds=bucket_seconds)).timestamp() * 1000)' in MAIN
    assert '"start": int(datetime.combine(bucket_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)' in MAIN


def test_chart_controls_are_keyboard_accessible_and_have_mobile_styles():
    assert 'type="button"' in JS
    assert '.module-chart-drilldown:focus-visible' in CSS
    assert '.drill-filter' in CSS
    assert '@media(max-width:650px)' in CSS


def test_ransomware_timeline_uses_only_aggregates_with_bucket_boundaries(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from app import main

    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "phase3-test.sqlite3"))
    main.init_db()
    now = datetime.now(timezone.utc)
    stamp = now.isoformat()
    with main.db() as conn:
        conn.execute(
            """INSERT INTO ransomware_posts
            (id, victim, group_name, discovered_at, description, source_link,
             country_code, country_name, country_lat, country_lon, country_basis,
             cached_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("rl-phase3", "Example RansomLook", "AlphaGroup", stamp, "claim", "https://example.com/rl",
             "CL", "Chile", -33.4, -70.7, "explicit", stamp, "RansomLook"),
        )
        conn.execute(
            """INSERT INTO ransomware_posts
            (id, victim, group_name, discovered_at, description, source_link,
             country_code, country_name, country_lat, country_lon, country_basis,
             cached_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("rwl-phase3", "Private RWL claim", "BetaGroup", stamp, "aggregate-only", "https://example.com/rwl",
             "PE", "Peru", -12.0, -77.0, "explicit", stamp, "Ransomware.live"),
        )

    daily = main.get_cached_ransomware("7d")
    active_daily = next(bucket for bucket in daily["timeline"] if bucket["total"] > 0)
    assert daily["count"] == 2
    assert len(daily["items"]) == 1
    assert active_daily["end"] - active_daily["start"] == 86_400_000
    assert active_daily["key"]
    assert "victim" not in active_daily and "description" not in active_daily

    hourly = main.get_cached_ransomware("24h")
    active_hourly = next(bucket for bucket in hourly["timeline"] if bucket["total"] > 0)
    assert active_hourly["end"] - active_hourly["start"] == 14_400_000
    assert active_hourly["key"]
    assert "victim" not in active_hourly
