from fastapi.testclient import TestClient
from app import main
import json


def test_executive_summary_returns_all_four_modules_with_empty_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "executive-empty.sqlite3"))
    with TestClient(main.app) as client:
        response = client.get("/api/executive-summary")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"generated_at", "windows", "platforms", "news", "ransomware", "vulnerabilities"}
    assert data["windows"] == {"news": "7d", "ransomware": "7d", "vulnerabilities": "30d + KEV"}
    assert data["platforms"]["total"] > 0
    assert data["news"]["count"] == 0
    assert data["ransomware"]["processed"] == 0
    assert data["vulnerabilities"]["visible"] == 0


def test_executive_summary_aggregates_real_cache_records(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "executive-filled.sqlite3"))
    main.init_db()
    stamp = main.now()
    with main.db() as c:
        c.execute("""INSERT INTO threat_news
            (id,title,summary,link,source,published_at,categories,cached_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            ("news-1","CVE vulnerability exploited","Critical security flaw",
             "https://example.org/cve","Test Source",stamp,
             json.dumps(["global","vulnerabilities","malware"]),stamp))
        c.execute("""INSERT INTO ransomware_posts
            (id,victim,group_name,discovered_at,description,source_link,country_code,
             country_name,country_lat,country_lon,country_basis,cached_at,source)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("ransom-1","Example Victim","Test Group",stamp,"A public claim",
             "https://www.ransomlook.io/recent","CL","Chile",-30.0,-71.0,
             "Explicit country mention",stamp,"RansomLook"))
        c.execute("""INSERT INTO vulnerability_items
            (cve,title,vendor,product,description,published,modified,cvss,severity,kev,kev_date,
             ransomware_use,epss,epss_percentile,source_url,cached_at,details_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("CVE-2026-99999","Test critical CVE","Vendor","Product","Description",
             stamp,stamp,9.8,"CRITICAL",1,"2026-11-20","Unknown",0.75,0.98,
             "https://nvd.nist.gov/vuln/detail/CVE-2026-99999",stamp,"{}"))
        c.execute("INSERT INTO threat_news_meta(key,value) VALUES(?,?)",
                  ("last_refresh",stamp))
        c.execute("INSERT INTO threat_news_meta(key,value) VALUES(?,?)",
                  ("source_results",json.dumps([{"source":"Test Source","ok":True,"items":1}])))
        c.execute("INSERT INTO ransomware_meta(key,value) VALUES(?,?)",
                  ("last_refresh",stamp))
        c.execute("INSERT INTO ransomware_meta(key,value) VALUES(?,?)",
                  ("source_results",json.dumps([{"source":"RansomLook","ok":True,"items":1}])))
    main._vuln_meta("last_refresh",stamp)
    main._vuln_meta("kev_count","1")
    main._vuln_meta("nvd_count","1")
    with TestClient(main.app) as client:
        response = client.get("/api/executive-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["news"]["count"] == 1
    assert data["news"]["categories"]["vulnerabilities"] == 1
    assert data["news"]["categories"]["malware"] == 1
    assert data["ransomware"]["processed"] == 1
    assert data["ransomware"]["groups_count"] == 1
    assert data["ransomware"]["countries_count"] == 1
    assert data["vulnerabilities"]["visible"] == 1
    assert data["vulnerabilities"]["severity"]["CRITICAL"] == 1
    assert data["vulnerabilities"]["epss_50_plus"] == 1


def test_executive_dashboard_uses_cache_endpoint_and_visual_containers():
    from pathlib import Path
    base = Path(__file__).resolve().parents[1]
    html = (base / "app/static/index.html").read_text(encoding="utf-8")
    js = (base / "app/static/app.js").read_text(encoding="utf-8")
    assert 'id="executiveDashboard"' in html
    assert 'id="execPlatformDonut"' in html
    assert 'id="execThreatBars"' in html
    assert 'id="execTopGroups"' in html
    assert 'id="execVulnBars"' in html
    assert 'fetch("/api/executive-summary"' in js
    assert "loadExecutiveDashboard();" in js
