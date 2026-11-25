from pathlib import Path


def _sources():
    base = Path(__file__).resolve().parents[1]
    return base, (base / "app/static/index.html").read_text(encoding="utf-8"), (base / "app/static/app.js").read_text(encoding="utf-8")


def test_phishing_reporter_is_in_sidebar_and_has_all_eight_vendors():
    _, html, js = _sources()
    assert 'data-nav="phishing"' in html
    assert 'id="view-phishing"' in html
    for vendor in ("virustotal", "fortiguard", "google", "netcraft", "eset", "cloudflare", "urlabuse", "watchguard"):
        assert f'data-vendor="{vendor}"' in html
    assert 'phishing:"Phishing URL Reporter"' in js


def test_reporter_is_browser_only_and_does_not_add_backend_routes_or_dependencies():
    base, _, js = _sources()
    main = (base / "app/main.py").read_text(encoding="utf-8")
    requirements = (base / "requirements.txt").read_text(encoding="utf-8")
    marker = "// v1.9.2 — Phishing URL Reporter"
    assert marker in js
    assert "localStorage" in js[js.index(marker):]
    assert "fetch(" not in js[js.index(marker):]
    assert '@app.post("/api/phishing"' not in main
    assert "playwright" not in requirements.lower()
    assert "selenium" not in requirements.lower()


def test_phase2_history_backup_import_and_filters_are_present():
    _, html, js = _sources()
    for element_id in (
        "phishingHistoryRows", "phishingHistorySearch", "phishingHistoryVendor",
        "phishingHistoryStatus", "phishingExportJson", "phishingExportCsv",
        "phishingImportButton", "phishingImportFile", "phishingClearHistory",
        "phishingStorageStatus", "phishingHistoryTotal", "phishingHistoryPending",
        "phishingHistoryConfirmed"
    ):
        assert f'id="{element_id}"' in html
    for feature in ("exportJson", "exportCsv", "importHistory", "parseCsv", "saveHistory", "renderHistory"):
        assert feature in js


def test_phase2_duplicate_detection_can_be_overridden_explicitly():
    _, html, js = _sources()
    assert 'id="phishingAllowDuplicates"' in html
    assert "findPrevious(vendor, item.url)" in js
    assert "if (!allowDuplicates) return" in js
    assert "coincidencia(s) URL/vendor" in js


def test_phase2_has_vendor_specific_templates_and_manual_status_control():
    _, html, js = _sources()
    assert 'id="phishingTemplateDialog"' in html
    assert 'class="phishing-btn secondary vendor-preview"' in html
    for vendor in ("virustotal", "fortiguard", "google", "netcraft", "eset", "cloudflare", "urlabuse", "watchguard"):
        assert f'    {vendor}: {{' in js
    assert 'data-history-status' in js
    assert 'Confirmado por analista' in js
    assert 'window.confirm("¿Confirmas que completaste el reporte, análisis o solicitud' in js


def test_report_requires_manual_confirmation_and_opening_portal_is_not_submission():
    _, html, js = _sources()
    assert 'class="phishing-confirm" disabled' in html
    assert 'Abrir el portal o copiar este texto no confirma un reporte.' in js
    assert 'status:"portal_opened"' in js
    assert 'status:"confirmed"' in js
