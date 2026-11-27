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
    marker = "// v1.9.4 — Phishing URL Reporter"
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


def test_google_portal_url_is_prefilled_and_details_are_copied():
    _, html, js = _sources()
    assert 'id="phishingUrlFeedback"' in html
    assert 'class="vendor-url-select"' in html
    assert 'target.searchParams.set("url", selectedUrl)' in js
    assert 'target.searchParams.set("hl", "es")' in js
    assert 'copyPrimaryVendorField(key, selectedUrl)' in js
    assert 'El formulario es de una URL por envío' in html or 'Google admite una URL por envío' in html


def test_google_report_text_is_short_and_vendor_specific():
    _, _, js = _sources()
    assert '.slice(0,800)' in js
    assert 'La URL va en el enlace' in js
    assert 'el botón de envío siguen siendo manuales' not in js  # documented in README


def test_vendor_assistant_copies_fields_separately_and_opens_single_url_vendors_individually():
    _, html, js = _sources()
    assert 'id="phishingTemplateFields"' in html
    assert 'data-template-field-copy' in js
    for vendor in ("virustotal", "fortiguard", "google", "eset", "cloudflare", "urlabuse"):
        assert vendor in js[js.index("const singleUrlVendors"):js.index("function workflowType")]
        assert f'data-vendor="{vendor}"' in html
    assert 'Portal preparado para ${openedUrls.length}/${urls.length} URL(s)' in js


def test_fortiguard_and_watchguard_have_vendor_supported_prefill_workflows():
    _, html, js = _sources()
    assert 'target.searchParams.set("q", selectedUrl)' in js
    assert 'Security Risk → Phishing' in js
    assert 'Phishing and Other Frauds' in js
    assert 'class="phishing-vendor-url-picker"' in html


def test_cloudflare_eset_netcraft_and_urlabuse_fields_follow_their_official_forms():
    _, html, js = _sources()
    assert 'Phishing & Malware' in js
    assert 'Domain in question' in js and 'Specific phishing link' in js
    assert 'Organización simulada por la página fraudulenta' in js
    assert 'Report in bulk' in js
    assert 'Your name or nickname' in js
    assert 'se muestra públicamente' in js


def test_v194_fortiguard_link_is_prefilled_and_google_choices_remain_explicitly_manual():
    _, _, js = _sources()
    assert 'target.searchParams.set("q", selectedUrl)' in js
    assert 'target.searchParams.set("url", selectedUrl)' in js
    assert 'Ingeniería social' in js
    assert 'Phishing bancario o financiero' in js
    assert 'Seleccionar manualmente en el formulario de Google' in js


def test_v194_confirmation_requires_the_vendor_portal_to_have_been_opened():
    _, _, js = _sources()
    assert 'if (!vendorStates[key]?.opened || vendorStates[key]?.confirmed) return;' in js
    assert 'confirm.disabled = needsOneByOne ? (!allSelectedUrlsOpened || !!state.confirmed)' in js


def test_v194_watchguard_batch_and_cloudflare_domain_specific_link_are_both_prepared():
    _, _, js = _sources()
    assert 'urls.map(url => `${url}, Phishing and Other Frauds`).join("\\n")' in js
    assert 'new URL(urls[0]).hostname' in js
    assert 'Specific phishing link' in js
