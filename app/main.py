from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import hashlib
import html as html_lib
import sqlite3, json, os, re, unicodedata
from urllib.parse import quote, urlparse
from functools import lru_cache
import xml.etree.ElementTree as ET
import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")
CONFIG_PATH = BASE / "config.json"
DB_PATH = os.getenv("DATABASE_PATH", str(BASE / "data" / "status_monitor.db"))
TIMEOUT = 12
HEADERS = {"User-Agent": "SOC-Service-Status-Monitor/1.9 (+public status and threat intelligence)"}
APP_VERSION = "1.9.4-phishing-vendor-assistant"
APP_STARTED_AT = datetime.now(timezone.utc).isoformat()
app = FastAPI(title="SOC Service Status Monitor", version=APP_VERSION)
app.mount("/static", StaticFiles(directory=str(BASE / "app" / "static")), name="static")


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY, name TEXT, category TEXT, portal_label TEXT, status TEXT, description TEXT,
            source_url TEXT, checked_at TEXT, source_status TEXT, error TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, service_id TEXT, service_name TEXT,
            old_status TEXT, new_status TEXT, description TEXT, occurred_at TEXT,
            source_url TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS checklist_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, analyst TEXT NOT NULL, shift_name TEXT NOT NULL,
            checkpoint TEXT NOT NULL, checked_services TEXT NOT NULL, total_services INTEGER NOT NULL,
            notes TEXT, created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS refresh_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, module TEXT NOT NULL, attempted_at TEXT NOT NULL,
            ok INTEGER NOT NULL, summary TEXT NOT NULL, details_json TEXT NOT NULL DEFAULT '{}')""")
        c.execute("""CREATE TABLE IF NOT EXISTS threat_news (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT, link TEXT NOT NULL,
            source TEXT NOT NULL, published_at TEXT NOT NULL, categories TEXT NOT NULL,
            cached_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS threat_news_meta (
            key TEXT PRIMARY KEY, value TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS ransomware_posts (
            id TEXT PRIMARY KEY, victim TEXT NOT NULL, group_name TEXT NOT NULL,
            discovered_at TEXT NOT NULL, description TEXT, source_link TEXT NOT NULL,
            country_code TEXT, country_name TEXT, country_lat REAL, country_lon REAL,
            country_basis TEXT, cached_at TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'RansomLook')""")
        ransomware_cols = {r[1] for r in c.execute("PRAGMA table_info(ransomware_posts)").fetchall()}
        if "source" not in ransomware_cols:
            c.execute("ALTER TABLE ransomware_posts ADD COLUMN source TEXT NOT NULL DEFAULT 'RansomLook'")
        c.execute("""CREATE TABLE IF NOT EXISTS ransomware_meta (
            key TEXT PRIMARY KEY, value TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS vulnerability_items (
            cve TEXT PRIMARY KEY, title TEXT, vendor TEXT, product TEXT, description TEXT,
            published TEXT, modified TEXT, cvss REAL, severity TEXT, kev INTEGER,
            kev_date TEXT, ransomware_use TEXT, epss REAL, epss_percentile REAL,
            source_url TEXT, cached_at TEXT, details_json TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS vulnerability_meta (
            key TEXT PRIMARY KEY, value TEXT)""")
        cols = {r[1] for r in c.execute("PRAGMA table_info(services)").fetchall()}
        for name, typ in [("category", "TEXT"), ("portal_label", "TEXT"), ("source_status", "TEXT"), ("error", "TEXT"), ("last_success_at", "TEXT")]:
            if name not in cols:
                c.execute(f"ALTER TABLE services ADD COLUMN {name} {typ}")
        vuln_cols = {r[1] for r in c.execute("PRAGMA table_info(vulnerability_items)").fetchall()}
        if "details_json" not in vuln_cols:
            c.execute("ALTER TABLE vulnerability_items ADD COLUMN details_json TEXT")


def record_refresh_run(module, ok, summary, details=None):
    """Store a compact audit row for each manually triggered module refresh."""
    try:
        init_db()
        with db() as c:
            c.execute(
                "INSERT INTO refresh_runs(module,attempted_at,ok,summary,details_json) VALUES(?,?,?,?,?)",
                (str(module)[:40], now(), int(bool(ok)), str(summary)[:300],
                 json.dumps(details or {}, ensure_ascii=False)[:6000])
            )
            c.execute("DELETE FROM refresh_runs WHERE id NOT IN (SELECT id FROM refresh_runs ORDER BY id DESC LIMIT 100)")
    except Exception:
        # Audit logging must never turn a successful source refresh into a failure.
        pass


def _read_meta_table(table):
    if table not in {"threat_news_meta", "ransomware_meta", "vulnerability_meta"}:
        raise ValueError("Tabla de metadatos no permitida")
    with db() as c:
        rows = c.execute(f"SELECT key,value FROM {table}").fetchall()
    return {row["key"]: row["value"] for row in rows}


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def normalize_statuspage(value):
    s = (value or "").strip().lower().replace("_", " ")
    if s in {"none", "operational", "ok", "resolved"}:
        return "operational"
    if s in {"minor", "degraded performance", "degraded", "partial outage", "service disruption"}:
        return "degraded"
    if s in {"major", "critical", "major outage", "outage", "service outage"}:
        return "outage"
    if "maintenance" in s:
        return "maintenance"
    return "unknown"


def statuspage_effective_status(payload):
    """
    Shared classifier for the summary card and live detail.
    A green rollup does not hide active minor incidents or degraded components.
    """
    rollup = payload.get("status") or {}
    status = normalize_statuspage(rollup.get("indicator"))
    rank = {"operational": 0, "info": 1, "maintenance": 2, "degraded": 3, "outage": 4}
    evidence = []

    for component in payload.get("components") or []:
        component_status = normalize_statuspage(component.get("status"))
        if component_status not in {"operational", "unknown"}:
            evidence.append((component_status, f"Componente {component.get('name', 'sin nombre')}: {component_status}"))

    for incident in payload.get("incidents") or []:
        incident_state = str(incident.get("status") or "").strip().lower().replace("_", " ")
        if incident_state in {"resolved", "postmortem", "closed"}:
            continue
        impact = normalize_statuspage(incident.get("impact"))
        if impact != "unknown":
            evidence.append((impact, f"Incidente activo {incident.get('name', 'sin nombre')} ({incident.get('impact', 'impacto no informado')}; {incident_state or 'estado no informado'})"))

    maintenances = payload.get("scheduled_maintenances") or []
    active_maintenances = [
        item for item in maintenances
        if str(item.get("status") or "").strip().lower().replace("_", " ") in {"in progress", "verifying"}
    ]
    if active_maintenances:
        evidence.append(("maintenance", f"{len(active_maintenances)} mantenimiento(s) en curso"))

    for item_status, _ in evidence:
        if rank.get(item_status, -1) > rank.get(status, -1):
            status = item_status

    return status, evidence, active_maintenances


def fetch_statuspage(service):
    base = service["base_url"].rstrip("/")
    endpoint = base + "/api/v2/summary.json"
    response = requests.get(endpoint, timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    rollup = payload.get("status") or {}
    status, evidence, active_maint = statuspage_effective_status(payload)
    description = rollup.get("description") or "El proveedor no publicó una descripción."
    if evidence:
        description += " | " + " | ".join(text for _, text in evidence[:6])
    active = payload.get("incidents") or []
    active_items = []
    for incident in active[:5]:
        state = str(incident.get("status") or "").strip().lower()
        if state in {"resolved", "postmortem", "closed"}:
            continue
        active_items.append(f"{incident.get('name') or 'Incidente activo'} ({incident.get('impact') or 'impacto no informado'})")
    if active_items:
        description = "Incidentes activos: " + " | ".join(active_items)
    if active_maint:
        description += " | Mantenimientos en curso: " + ", ".join(m.get("name", "Mantenimiento") for m in active_maint[:3])
    upcoming = [
        m for m in (payload.get("scheduled_maintenances") or [])
        if str(m.get("status") or "").lower().replace("_", " ") in {"scheduled", "not started"}
    ]
    if upcoming:
        description += f" | Mantenimientos programados: {len(upcoming)}"
    return status, description[:1200], base + "/", rollup.get("indicator", "")


def fetch_google_workspace(service, payload):
    wanted = {x.casefold() for x in service.get("product_names", [])}
    active = []
    for incident in payload:
        products = incident.get("affected_products") or []
        names = {str(p.get("current_title") or p.get("title") or "").casefold() for p in products}
        if not names:
            names = {str(incident.get("service_name") or "").casefold()}
        if not wanted.intersection(names):
            continue
        update = incident.get("most_recent_update") or {}
        update_status = (update.get("status") or "").upper()
        if incident.get("end") or update_status == "AVAILABLE":
            continue
        impact = (incident.get("status_impact") or "").upper()
        status = {"SERVICE_OUTAGE": "outage", "SERVICE_DISRUPTION": "degraded", "SERVICE_INFORMATION": "info"}.get(impact, "unknown")
        active.append((status, incident.get("external_desc") or "Incidente publicado por Google."))
    rank = {"operational": 0, "info": 1, "degraded": 2, "outage": 3, "unknown": -1}
    if not active:
        return "operational", "No hay incidentes activos publicados para este servicio.", service["base_url"], "AVAILABLE"
    worst = max((x[0] for x in active), key=lambda x: rank.get(x, -1))
    details = [re.sub(r"\s+", " ", desc).strip()[:420] for _, desc in active[:4]]
    return worst, " | ".join(details), service["base_url"], ",".join(x[0] for x in active)


def fetch_slack(service):
    endpoint = "https://slack-status.com/api/v2.0.0/current"
    response = requests.get(endpoint, timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") == "ok":
        return "operational", "Slack informa que no hay incidentes activos.", service["base_url"], "ok"
    incidents = payload.get("active_incidents") or []
    if not incidents:
        return "unknown", "La API de Slack devolvió un estado no reconocido.", service["base_url"], str(payload.get("status", "unknown"))
    titles = [x.get("title", "Incidente activo") for x in incidents[:5]]
    types = {str(x.get("type", "incident")).lower() for x in incidents}
    incident_states = {str(x.get("status", "active")).lower() for x in incidents}
    if "scheduled" in incident_states or "maintenance" in types:
        status = "maintenance"
    else:
        status = "outage" if "outage" in types else "degraded"
    return status, "Incidentes activos: " + " | ".join(titles), service["base_url"], str(payload.get("status", "active"))


def fetch_google_cloud(service):
    # Google documents this public JSON history feed as a supported way to consume Service Health.
    endpoint = "https://status.cloud.google.com/incidents.json"
    response = requests.get(endpoint, timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Formato del feed JSON de Google Cloud no reconocido")
    active = []
    for incident in payload:
        if incident.get("end"):
            continue
        update = incident.get("most_recent_update") or {}
        state = (update.get("status") or "").upper()
        if state in {"AVAILABLE", "RESOLVED", "CLOSED"}:
            continue
        severity = (incident.get("severity") or "").lower()
        if state in {"SERVICE_OUTAGE", "OUTAGE"} or severity in {"high", "critical"}:
            status = "outage"
        elif state in {"SERVICE_DISRUPTION", "DISRUPTION"} or severity in {"medium", "moderate"}:
            status = "degraded"
        elif state in {"SERVICE_INFORMATION", "INFORMATIONAL"} or severity == "low":
            status = "info"
        else:
            status = "unknown"
        title = incident.get("external_desc") or incident.get("service_name") or "Incidente Google Cloud"
        locations = incident.get("currently_affected_locations") or []
        location_text = ", ".join(str(x.get("title") or x.get("id") or x) for x in locations[:4] if isinstance(x, dict))
        active.append((status, title[:350] + (f" | Ubicaciones: {location_text}" if location_text else "")))
    rank = {"operational": 0, "info": 1, "degraded": 2, "outage": 3, "unknown": -1}
    if not active:
        return "operational", "Google Cloud Service Health no publica incidentes activos en el feed general.", service["base_url"], "no_active_incidents"
    worst = max((x[0] for x in active), key=lambda x: rank.get(x, -1))
    return worst, " | ".join(desc for _, desc in active[:4]), service["base_url"], f"{len(active)} incidentes activos"


def fetch_microsoft_public(service):
    """
    Reads Microsoft's public, unauthenticated status-post JSON endpoints.
    This is public/global information only; it is NOT tenant-specific Service Health.
    """
    endpoint = service.get("api_url")
    if not endpoint:
        raise ValueError("Falta api_url para la fuente pública de Microsoft.")
    response = requests.get(endpoint, timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    posts = payload if isinstance(payload, list) else [payload]
    if not posts:
        return "operational", "Microsoft no publica avisos activos en esta fuente.", service["base_url"], "empty"
    # Endpoint usually returns a current status object; if it returns a list, inspect newest first.
    post = posts[0]
    raw_status = str(post.get("Status") or post.get("status") or "").strip()
    title = str(post.get("Title") or post.get("title") or service["name"]).strip()
    message = re.sub(r"<[^>]+>", " ", str(post.get("Message") or post.get("message") or ""))
    message = re.sub(r"\s+", " ", message).strip()
    token = raw_status.casefold().replace("_", " ")
    if token in {"available", "operational", "resolved", "none", "healthy"}:
        status = "operational"
    elif any(x in token for x in ("interruption", "outage", "critical", "unavailable")):
        status = "outage"
    elif any(x in token for x in ("degrad", "disruption", "investigat", "identified", "monitoring", "service issue")):
        status = "degraded"
    elif any(x in token for x in ("maintenance", "scheduled")):
        status = "maintenance"
    elif any(x in token for x in ("information", "advisory", "notice")):
        status = "info"
    else:
        # Do not infer an outage from unknown Microsoft status strings.
        status = "unknown"
    timestamp = post.get("LastUpdatedTime") or post.get("AuthoredDateTime") or ""
    description = (f"{title}: " if title else "") + (message or raw_status or "Estado público recibido de Microsoft.")
    if timestamp:
        description += f" | Actualización del fabricante: {timestamp}"
    return status, description[:900], service["base_url"], raw_status or "unknown"


def fetch_watchguard(service):
    """
    WatchGuard publishes a public Statuspage and official Atom/RSS incident feeds.
    Prefer the structured Statuspage summary (components + incidents); fall back to
    its official Atom feed if the summary endpoint is unavailable.
    """
    base = service["base_url"].rstrip("/")
    try:
        return fetch_statuspage(service)
    except Exception as summary_error:
        feed_url = service.get("feed_url") or (base + "/history.atom")
        response = requests.get(feed_url, timeout=TIMEOUT, headers=HEADERS)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        entries = []
        for node in root.iter():
            tag = node.tag.rsplit("}", 1)[-1].lower()
            if tag in {"entry", "item"}:
                title = ""
                body = ""
                for child in node.iter():
                    ctag = child.tag.rsplit("}", 1)[-1].lower()
                    if ctag == "title" and not title:
                        title = "".join(child.itertext()).strip()
                    elif ctag in {"content", "summary", "description", "encoded"}:
                        body += " " + " ".join(child.itertext())
                entries.append((title, re.sub(r"\s+", " ", body).strip()))
        active = []
        for title, body in entries[:30]:
            text = (title + " " + body).casefold()
            if any(x in text for x in ("resolved", "fully restored", "operating normally", "returned to normal", "no longer impacted")):
                continue
            if any(x in text for x in ("investigating", "identified", "monitoring", "degraded", "service disruption", "service outage", "experiencing issues")):
                status = "outage" if any(x in text for x in ("major outage", "service outage", "unavailable to all")) else "degraded"
                active.append((status, title or "Incidente WatchGuard", body[:420]))
        if not active:
            return "operational", "El feed público de WatchGuard no muestra actualizaciones activas de incidentes.", base + "/", "feed_no_active_incidents"
        rank = {"operational": 0, "info": 1, "maintenance": 2, "degraded": 3, "outage": 4}
        worst = max((x[0] for x in active), key=lambda x: rank.get(x, 0))
        detail = " | ".join(f"{title}: {body}" for _, title, body in active[:4])
        return worst, detail[:900], base + "/", f"atom_fallback (summary error: {str(summary_error)[:100]})"


def fetch_service(service, google_payload=None):
    kind = service.get("type")
    if kind == "statuspage": return fetch_statuspage(service)
    if kind == "slack": return fetch_slack(service)
    if kind == "google_workspace":
        if google_payload is None: raise RuntimeError("No se pudo obtener el feed oficial de Google Workspace.")
        return fetch_google_workspace(service, google_payload)
    if kind == "google_cloud": return fetch_google_cloud(service)
    if kind == "microsoft_public": return fetch_microsoft_public(service)
    if kind == "watchguard": return fetch_watchguard(service)
    if kind == "manual": return "manual", service.get("notes") or "Revisión manual en el portal oficial.", service["base_url"], "manual"
    raise RuntimeError(f"Tipo de fuente no soportado: {kind}")


def store_result(service, status, description, source_url, raw, error=None):
    checked = None if status == "manual" else now()
    success_at = checked if status not in {"unknown", "manual"} and not error else None
    with db() as c:
        previous = c.execute("SELECT status FROM services WHERE id=?", (service["id"],)).fetchone()
        old = previous["status"] if previous else None
        c.execute("""INSERT INTO services(id,name,category,portal_label,status,description,source_url,checked_at,last_success_at,source_status,error)
            VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,category=excluded.category,portal_label=excluded.portal_label,status=excluded.status,
            description=excluded.description,source_url=excluded.source_url,checked_at=excluded.checked_at,
            last_success_at=COALESCE(excluded.last_success_at,services.last_success_at),
            source_status=excluded.source_status,error=excluded.error""",
            (service["id"], service["name"], service.get("category", "General"), service.get("portal_label", "Abrir portal oficial"),
             status, description, source_url, checked, success_at, raw, error))
        if old is not None and status not in {"unknown", "manual"} and old not in {"unknown", "manual"} and old != status:
            c.execute("INSERT INTO events(service_id,service_name,old_status,new_status,description,occurred_at,source_url) VALUES(?,?,?,?,?,?,?)",
                      (service["id"], service["name"], old, status, description, checked, source_url))
    return {"id": service["id"], "status": status, "error": error}


def poll_once():
    enabled = [s for s in load_config().get("services", []) if s.get("enabled", True)]
    google_payload = None
    if any(s.get("type") == "google_workspace" for s in enabled):
        try:
            r = requests.get("https://www.google.com/appsstatus/dashboard/incidents.json", timeout=TIMEOUT, headers=HEADERS)
            r.raise_for_status()
            google_payload = r.json()
            if not isinstance(google_payload, list): raise ValueError("Formato JSON de Google Workspace no reconocido")
        except Exception:
            google_payload = None
    results = []
    def run_one(service):
        try:
            status, description, source_url, raw = fetch_service(service, google_payload)
            return store_result(service, status, description, source_url, raw)
        except Exception as exc:
            return store_result(service, "unknown", "No fue posible confirmar el estado desde la fuente pública.",
                                service.get("base_url", ""), "", str(exc)[:280])
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(run_one, service) for service in enabled]
        for future in as_completed(futures): results.append(future.result())
    success_count = sum(1 for r in results if r["status"] not in {"unknown", "manual"})
    error_count = sum(1 for r in results if r["status"] == "unknown")
    response = {"ok": success_count > 0, "partial": success_count > 0 and error_count > 0,
            "checked": len(results),
            "automated": sum(1 for s in enabled if s.get("type") != "manual"),
            "manual": sum(1 for s in enabled if s.get("type") == "manual"),
            "success": success_count, "errors": error_count,
            "results": results, "completed_at": now()}
    record_refresh_run("platforms", response["ok"],
        f"{success_count} fuentes con respuesta; {error_count} errores; {response['manual']} manuales",
        {"checked": len(results), "success": success_count, "errors": error_count, "manual": response["manual"]})
    return response


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "app" / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def get_status():
    # Always return the complete catalog, even before the first manual refresh.
    # Database rows enrich the catalog with the latest result from each source.
    with db() as c:
        rows = c.execute("SELECT * FROM services").fetchall()
    saved = {row["id"]: dict(row) for row in rows}
    result = []
    for item in load_config().get("services", []):
        if not item.get("enabled", True):
            continue
        current = saved.get(item["id"], {})
        source_type = item.get("type", "manual")
        default_status = "manual" if source_type == "manual" else "unknown"
        result.append({
            "id": item["id"],
            "name": item["name"],
            "category": item.get("category", "General"),
            "portal_label": item.get("portal_label", "Abrir portal oficial"),
            "status": current.get("status") or default_status,
            "description": current.get("description") or (
                item.get("notes") if default_status == "manual"
                else "Aún no consultado. Presiona «Actualizar ahora»."
            ),
            "source_url": current.get("source_url") or item.get("base_url", ""),
            "checked_at": current.get("checked_at"),
            "last_success_at": current.get("last_success_at"),
            "source_status": current.get("source_status"),
            "error": current.get("error"),
            "type": source_type
        })
    result.sort(key=lambda x: (x["category"], x["name"]))
    keys = ["operational", "info", "degraded", "outage", "maintenance", "manual", "unknown"]
    counts = {k: sum(1 for x in result if x["status"] == k) for k in keys}
    return {"services": result, "counts": counts, "server_time": now(), "mode": "manual"}


@app.post("/api/poll")
def manual_poll():
    # Manual, operator-triggered refresh. No background polling is started.
    try:
        return poll_once()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo completar la consulta: {str(exc)[:300]}")




# ---------------------------------------------------------------------------
# SOC Global Threat Intelligence — Part 1: Public cyber news feeds
# Fixed public feeds only; no customer data, credentials or internal APIs.
# ---------------------------------------------------------------------------
NEWS_FEEDS = [
    {"id": "therecord", "name": "The Record", "url": "https://therecord.media/feed/"},
    {"id": "bleepingcomputer", "name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/"},
    {"id": "cisa", "name": "CISA", "url": "https://www.cisa.gov/rss.xml"},
    {"id": "talos", "name": "Cisco Talos", "url": "https://blog.talosintelligence.com/rss/"},
    {"id": "google-ti", "name": "Google Threat Intelligence", "url": "https://feeds.feedburner.com/threatintelligence/pvexyqv7v0v"},
    {"id": "cybersecuritynews", "name": "Cyber Security News", "url": "https://cybersecuritynews.com/feed/"},
    {"id": "securityweek-vuln", "name": "SecurityWeek · Vulnerabilities", "url": "https://www.securityweek.com/category/vulnerabilities/feed/"},
    {"id": "thehackernews", "name": "The Hacker News", "url": "https://thehackernews.com/feeds/posts/default?alt=rss"},
    {"id": "csirt-chile", "name": "CSIRT Chile", "url": "https://csirt.gob.cl/rss/alertas"},

]

NEWS_CATEGORIES = {
    "global": "Noticias mundiales",
    "ransomware": "Ransomware",
    "espionage": "Espionaje",
    "leaks": "Filtraciones",
    "ddos": "DDoS",
    "malware": "Malware",
    "vulnerabilities": "Vulnerabilidades",
}


def _news_clean(value):
    value = html_lib.unescape(str(value or ""))
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _news_parse_date(value):
    if not value:
        return None
    value = str(value).strip()
    try:
        parsed = parsedate_to_datetime(value)
    except Exception:
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _news_parse_feed(xml_bytes):
    """Parse RSS 2.0 or Atom. Return safe, short article metadata only."""
    root = ET.fromstring(xml_bytes)
    results = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() not in {"item", "entry"}:
            continue
        item = {"title": "", "summary": "", "link": "", "published": ""}
        for child in node:
            ctag = child.tag.rsplit("}", 1)[-1].lower()
            content = " ".join(child.itertext()).strip()
            if ctag == "title" and not item["title"]:
                item["title"] = _news_clean(content)
            elif ctag in {"description", "summary", "content", "encoded"} and not item["summary"]:
                item["summary"] = _news_clean(content)
            elif ctag == "link" and not item["link"]:
                item["link"] = child.attrib.get("href") or content
            elif ctag in {"pubdate", "published", "updated", "date"} and not item["published"]:
                item["published"] = content
        if not item["link"]:
            for child in node:
                if child.tag.rsplit("}", 1)[-1].lower() == "guid":
                    candidate = (child.text or "").strip()
                    if candidate.startswith("https://"):
                        item["link"] = candidate
                        break
        published = _news_parse_date(item["published"])
        if not item["title"] or not item["link"].startswith("https://") or not published:
            continue
        item["published_at"] = published.isoformat()
        item["summary"] = item["summary"][:420]
        results.append(item)
    return results


def _news_classify(title, summary):
    text = f"{title} {summary}".casefold()
    patterns = {
        "ransomware": [
            "ransomware", "ransomware gang", "ransom group", "double extortion",
            "lockbit", "cl0p", "clop", "akira", "alphv", "blackcat",
            "play ransomware", "safepay", "medusa ransomware",
        ],
        "espionage": [
            "cyber espionage", "cyberespionage", "espionage", "state-sponsored",
            "nation-state", "nation state", "advanced persistent threat",
            "government-linked hackers", "spying campaign",
            "ciberespionaje", "espionaje cibernético", "amenaza persistente avanzada",
        ],
        "leaks": [
            "data breach", "data leak", "leaked data", "stolen data", "exposed data",
            "data stolen", "breach exposes", "records exposed", "database leak",
            "filtración de datos", "datos filtrados", "datos expuestos", "robo de información",
            "fuga de información", "exposición de datos",
        ],
        "ddos": [
            "ddos", "denial-of-service", "denial of service", "distributed denial",
            "botnet attack", "traffic-flooding", "denegación de servicio",
            "ataque de denegación de servicio",
        ],
        "malware": [
            "malware", "trojan", "infostealer", "infostealing", "botnet", "wiper",
            "spyware", "rootkit", "backdoor", "loader", "malicious", "phishing campaign",
            "software malicioso", "troyano", "gusano informático", "código malicioso",
            "campaña de phishing", "suplantación de identidad",
        ],
        "vulnerabilities": [
            "vulnerability", "vulnerabilities", "security flaw", "software flaw",
            "zero-day", "zero day", "zero-click", "zero click", "security patch",
            "security update", "remote code execution", "arbitrary code execution",
            "privilege escalation", "authentication bypass", "buffer overflow",
            "sql injection", "command injection", "memory corruption",
            "improper access control", "improper input validation",
            "actively exploited vulnerability", "actively exploited flaw",
            "vulnerabilidad", "vulnerabilidades", "falla de seguridad", "fallo de seguridad",
            "parche de seguridad", "actualización de seguridad", "ejecución remota de código",
            "escalada de privilegios", "omisión de autenticación", "inyección sql",
            "inyección de comandos", "día cero", "vulnerabilidad de día cero",
            "vulnerabilidad crítica", "explotación de vulnerabilidad",
        ],
    }
    matched = [category for category, terms in patterns.items() if any(term in text for term in terms)]
    if re.search(r"\\bcve-\\d{4}-\\d{4,}\\b", text) or re.search(r"\\b(exploit|exploited|exploitation)\\b", text):
        matched.append("vulnerabilities")
    matched = list(dict.fromkeys(matched))
    # "Noticias mundiales" is the global view; topical tags remain additive.
    return ["global"] + matched


def _fetch_news_feed(feed):
    response = requests.get(feed["url"], timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    return _news_parse_feed(response.content)


def refresh_threat_news():
    init_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=8)
    fetched, source_results = [], []
    prior_meta = _read_meta_table("threat_news_meta")
    try:
        prior_results = json.loads(prior_meta.get("source_results", "[]"))
    except Exception:
        prior_results = []
    prior_by_name = {item.get("source"): item for item in prior_results if isinstance(item, dict)}

    with ThreadPoolExecutor(max_workers=max(1, len(NEWS_FEEDS))) as pool:
        futures = {pool.submit(_fetch_news_feed, feed): feed for feed in NEWS_FEEDS}
        for future in as_completed(futures):
            feed = futures[future]
            checked_at = now()
            previous = prior_by_name.get(feed["name"], {})
            try:
                items = future.result()
                count = 0
                for item in items[:60]:
                    published = _news_parse_date(item["published_at"])
                    if not published or published < cutoff:
                        continue
                    stable_link = item["link"].split("#", 1)[0].rstrip("/")
                    item_id = hashlib.sha256(stable_link.encode("utf-8")).hexdigest()
                    categories = _news_classify(item["title"], item["summary"])
                    fetched.append((
                        item_id, item["title"][:300], item["summary"][:420],
                        stable_link, feed["name"], item["published_at"],
                        json.dumps(categories), checked_at
                    ))
                    count += 1
                source_results.append({"source": feed["name"], "ok": True, "items": count,
                    "checked_at": checked_at, "last_success": checked_at})
            except Exception as exc:
                source_results.append({"source": feed["name"], "ok": False,
                    "error": str(exc)[:180], "checked_at": checked_at,
                    "last_success": previous.get("last_success") or (prior_meta.get("last_refresh") if previous.get("ok") else None)})

    attempted_at = now()
    successful_sources = sum(1 for item in source_results if item["ok"])
    failed_sources = len(source_results) - successful_sources
    with db() as c:
        if fetched:
            c.executemany("""INSERT INTO threat_news
                (id,title,summary,link,source,published_at,categories,cached_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, summary=excluded.summary, link=excluded.link,
                source=excluded.source, published_at=excluded.published_at,
                categories=excluded.categories, cached_at=excluded.cached_at""", fetched)
        c.execute("DELETE FROM threat_news WHERE published_at < ?",
            ((datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),))
        c.execute("INSERT INTO threat_news_meta(key,value) VALUES('last_attempt',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (attempted_at,))
        if successful_sources:
            c.execute("INSERT INTO threat_news_meta(key,value) VALUES('last_refresh',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (attempted_at,))
        c.execute("INSERT INTO threat_news_meta(key,value) VALUES('source_results',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (json.dumps(source_results, ensure_ascii=False),))
        total = c.execute("SELECT COUNT(*) FROM threat_news").fetchone()[0]

    response = {
        "ok": successful_sources > 0, "partial": successful_sources > 0 and failed_sources > 0,
        "fetched": len(fetched), "cache_total": total,
        "last_refresh": attempted_at if successful_sources else prior_meta.get("last_refresh"),
        "last_attempt": attempted_at, "sources": source_results,
        "successful_sources": successful_sources, "failed_sources": failed_sources
    }
    record_refresh_run("news", response["ok"],
        f"{successful_sources}/{len(source_results)} fuentes RSS respondieron; {len(fetched)} registros procesados",
        {"successful_sources": successful_sources, "failed_sources": failed_sources, "fetched": len(fetched)})
    return response

def get_cached_threat_news(period="7d"):
    init_db()
    hours = 24 if period == "24h" else 24 * 7
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with db() as c:
        rows = c.execute("SELECT * FROM threat_news ORDER BY published_at DESC LIMIT 500").fetchall()
        meta = {row["key"]: row["value"] for row in c.execute("SELECT key,value FROM threat_news_meta")}
    items = []
    for row in rows:
        published = _news_parse_date(row["published_at"])
        if not published or published < cutoff:
            continue
        try:
            categories = json.loads(row["categories"])
        except Exception:
            categories = ["global"]
        items.append({
            "id": row["id"], "title": row["title"], "summary": row["summary"],
            "link": row["link"], "source": row["source"],
            "published_at": row["published_at"], "categories": categories,
            "cached_at": row["cached_at"]
        })
    try:
        source_results = json.loads(meta.get("source_results", "[]"))
    except Exception:
        source_results = []
    return {
        "period": period, "items": items, "count": len(items),
        "last_refresh": meta.get("last_refresh"), "last_attempt": meta.get("last_attempt"),
        "sources": source_results, "available_categories": NEWS_CATEGORIES
    }


# ---------------------------------------------------------------------------
# SOC Global Threat Intelligence — Part 2: ransomware claims and country map
# Public RansomLook read API. Only claim metadata is stored; no leaked content.
# ---------------------------------------------------------------------------
RANSOMLOOK_API = "https://www.ransomlook.io/api/posts"
RANSOMLOOK_HOME = "https://www.ransomlook.io"
RANSOMWARELIVE_RSS = "https://ransomware.live/rss.xml"
RANSOMWARELIVE_HOME = "https://www.ransomware.live"
RANSOMLOOK_REFRESH_FLOOR_MINUTES = 15


@lru_cache(maxsize=1)
def _country_catalog():
    path = BASE / "app" / "data" / "country_catalog.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _ransom_normalize_text(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value).strip().casefold()


def _ransom_detect_country(description, victim=""):
    """Return a country only when one unambiguous country is named in text.

    RansomLook records usually contain an organization description, not a
    structured country field. We deliberately avoid guessing from a company
    name, domain TLD, attacker group or IP address. Multiple-country text is
    left unassigned rather than plotting a misleading location.
    """
    text = _ransom_normalize_text(description or "")
    if not text:
        return None
    matches = {}
    for country in _country_catalog():
        code = country.get("code")
        if not code:
            continue
        for alias in country.get("aliases") or [country.get("name", "")]:
            alias_n = _ransom_normalize_text(alias)
            if len(alias_n) < 4:
                continue
            pattern = r"(?<![a-z0-9])" + re.escape(alias_n) + r"(?![a-z0-9])"
            if re.search(pattern, text):
                # Country names / official variants outweigh a demonym only
                # when both point to different countries; otherwise stay safe.
                matches.setdefault(code, {
                    "code": code, "name": country.get("name"),
                    "lat": country.get("lat"), "lon": country.get("lon"),
                    "matched_term": alias,
                })
                break
    if len(matches) != 1:
        return None
    return next(iter(matches.values()))


def _ransomlook_safe_source_link(item):
    raw = str(item.get("link") or "").strip()
    if raw.startswith("/") and not raw.startswith("//"):
        return RANSOMLOOK_HOME + raw
    if raw.startswith("https://"):
        host = (urlparse(raw).hostname or "").lower()
        if host == "ransomlook.io" or host.endswith(".ransomlook.io"):
            return raw
    group = str(item.get("group_name") or item.get("group") or "").strip()
    if group:
        return RANSOMLOOK_HOME + "/group/" + quote(group, safe="")
    return RANSOMLOOK_HOME + "/recent"


def _fetch_ransomlook_posts():
    response = requests.get(
        RANSOMLOOK_API, params={"days": 7}, timeout=TIMEOUT,
        headers={**HEADERS, "Accept": "application/json"}
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        payload = payload.get("posts") or payload.get("items") or payload.get("results") or []
    if not isinstance(payload, list):
        raise ValueError("RansomLook devolvió un formato JSON no reconocido.")
    return payload


def _ransom_build_record(item, source="RansomLook"):
    if not isinstance(item, dict):
        return None
    victim = _news_clean(item.get("post_title") or item.get("victim") or item.get("title"))[:260]
    group = _news_clean(item.get("group_name") or item.get("group"))[:120]
    discovered = _news_parse_date(item.get("discovered") or item.get("published") or item.get("date"))
    if not victim or not group or not discovered:
        return None
    description = _news_clean(item.get("description") or item.get("summary") or "")[:1600]
    country = _ransom_detect_country(description, victim + " " + str(item.get("title") or ""))
    stable = "|".join((source.casefold(), group.casefold(), victim.casefold(), discovered.date().isoformat()))
    record_id = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    return {
        "id": record_id, "victim": victim, "group_name": group,
        "discovered_at": discovered.isoformat(), "description": description,
         "source_link": (item.get("link") if source == "Ransomware.live" and str(item.get("link") or "").startswith("https://www.ransomware.live/") else _ransomlook_safe_source_link(item)),
        "country_code": country["code"] if country else None,
        "country_name": country["name"] if country else None,
        "country_lat": country["lat"] if country else None,
        "country_lon": country["lon"] if country else None,
        "country_basis": f"Mención textual: {country['matched_term']}" if country else None,
        "source": source, "cached_at": now(),
    }



def _fetch_ransomwarelive_rss():
    """Read public RSS metadata only; never retrieve leak-site files."""
    response = requests.get(RANSOMWARELIVE_RSS, timeout=TIMEOUT,
        headers={**HEADERS, "Accept": "application/rss+xml, application/xml, text/xml"})
    response.raise_for_status()
    root = ET.fromstring(response.content)
    entries = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        pub = (node.findtext("pubDate") or "").strip()
        description = node.findtext("description") or ""
        description = _news_clean(re.sub(r"<[^>]+>", " ", html_lib.unescape(description)))[:1200]
        match = re.match(r"^(.+?)\s+has just published (?:a new )?victim\s*:?\s*(.+)$", title, re.I)
        if not match:
            match = re.match(r"^(.+?)\s*[-:]\s*(?:new victim|victim)\s*[-:]?\s*(.+)$", title, re.I)
        if not match:
            continue
        group, victim = _news_clean(match.group(1)), _news_clean(match.group(2))
        if not group or not victim or not link.startswith("https://www.ransomware.live/"):
            continue
        entries.append({"group_name": group, "post_title": victim, "discovered": pub,
                        "description": description, "link": link})
    return entries


def _get_ransom_meta():
    with db() as c:
        rows = c.execute("SELECT key,value FROM ransomware_meta").fetchall()
    return {row["key"]: row["value"] for row in rows}


def refresh_ransomware_tracker(force=False):
    """Fetch public metadata from RansomLook and Ransomware.live RSS."""
    init_db()
    meta = _get_ransom_meta()
    previous = _news_parse_date(meta.get("last_refresh"))
    if not force and previous and (datetime.now(timezone.utc) - previous) < timedelta(minutes=RANSOMLOOK_REFRESH_FLOOR_MINUTES):
        cached = get_cached_ransomware("7d")
        sources = cached.get("sources", [])
        return {"ok": True, "skipped": True,
                "message": f"Se reutiliza la caché durante {RANSOMLOOK_REFRESH_FLOOR_MINUTES} minutos.",
                "fetched": 0, "cache_total": cached["count"], "last_refresh": meta.get("last_refresh"),
                "sources": sources,
                "successful_sources": sum(1 for x in sources if x.get("ok")),
                "failed_sources": sum(1 for x in sources if not x.get("ok"))}
    try:
        prior_results = json.loads(meta.get("source_results", "[]"))
    except Exception:
        prior_results = []
    prior_by_name = {item.get("source"): item for item in prior_results if isinstance(item, dict)}
    source_results, total_fetched = [], 0
    for source_name, fetcher in (("RansomLook", _fetch_ransomlook_posts),
                                  ("Ransomware.live", _fetch_ransomwarelive_rss)):
        checked_at = now()
        previous = prior_by_name.get(source_name, {})
        try:
            source_items = fetcher()
            rows, cutoff = [], datetime.now(timezone.utc) - timedelta(days=8)
            for item in source_items[:1200]:
                record = _ransom_build_record(item, source=source_name)
                if not record:
                    continue
                discovered = _news_parse_date(record["discovered_at"])
                if discovered and discovered >= cutoff:
                    rows.append(record)
            with db() as c:
                if rows:
                    c.executemany("""INSERT INTO ransomware_posts
                        (id,victim,group_name,discovered_at,description,source_link,country_code,
                         country_name,country_lat,country_lon,country_basis,cached_at,source)
                        VALUES(:id,:victim,:group_name,:discovered_at,:description,:source_link,
                               :country_code,:country_name,:country_lat,:country_lon,:country_basis,:cached_at,:source)
                        ON CONFLICT(id) DO UPDATE SET victim=excluded.victim,group_name=excluded.group_name,
                        description=excluded.description,source_link=excluded.source_link,
                        country_code=excluded.country_code,country_name=excluded.country_name,
                        country_lat=excluded.country_lat,country_lon=excluded.country_lon,
                        country_basis=excluded.country_basis,cached_at=excluded.cached_at,source=excluded.source""", rows)
            total_fetched += len(rows)
            source_results.append({"source": source_name, "ok": True, "items": len(rows),
                                   "checked_at": checked_at, "last_success": checked_at})
        except Exception as exc:
            source_results.append({"source": source_name, "ok": False, "error": str(exc)[:220],
                                   "checked_at": checked_at,
                                   "last_success": previous.get("last_success") or (meta.get("last_refresh") if previous.get("ok") else None)})
    with db() as c:
        c.execute("DELETE FROM ransomware_posts WHERE discovered_at < ?",
                  ((datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),))
    refreshed_at = now()
    with db() as c:
        if any(x["ok"] for x in source_results):
            c.execute("""INSERT INTO ransomware_meta(key,value) VALUES('last_refresh',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (refreshed_at,))
        c.execute("""INSERT INTO ransomware_meta(key,value) VALUES('last_attempt',?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (refreshed_at,))
        c.execute("""INSERT INTO ransomware_meta(key,value) VALUES('source_results',?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (json.dumps(source_results, ensure_ascii=False),))
        total = c.execute("SELECT COUNT(*) FROM ransomware_posts").fetchone()[0]
    success_count = sum(1 for x in source_results if x["ok"])
    failure_count = len(source_results) - success_count
    response = {"ok": success_count > 0, "partial": success_count > 0 and failure_count > 0,
            "fetched": total_fetched, "cache_total": total,
            "last_refresh": refreshed_at if success_count else meta.get("last_refresh"),
            "last_attempt": refreshed_at, "sources": source_results,
            "successful_sources": success_count, "failed_sources": failure_count}
    record_refresh_run("ransomware", response["ok"],
        f"{success_count}/{len(source_results)} fuentes respondieron; {total_fetched} observaciones procesadas",
        {"successful_sources": success_count, "failed_sources": failure_count, "fetched": total_fetched})
    return response


def get_cached_ransomware(period="7d"):
    init_db()
    hours = 24 if period == "24h" else 24 * 7
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with db() as c:
        rows = c.execute("SELECT * FROM ransomware_posts ORDER BY discovered_at DESC LIMIT 1200").fetchall()
    meta = _get_ransom_meta()
    posts = []
    country_counts = {}
    group_counts = {}
    source_stats = {
        "RansomLook": {"source": "RansomLook", "processed": 0, "rows_visible": 0, "groups": set(), "countries": set()},
        "Ransomware.live": {"source": "Ransomware.live", "processed": 0, "rows_visible": 0, "groups": set(), "countries": set()},
    }
    for row in rows:
        discovered = _news_parse_date(row["discovered_at"])
        if not discovered or discovered < cutoff:
            continue
        source = row["source"] if "source" in row.keys() and row["source"] else "RansomLook"
        if source not in source_stats:
            source_stats[source] = {"source": source, "processed": 0, "rows_visible": 0, "groups": set(), "countries": set()}
        stats = source_stats[source]
        stats["processed"] += 1
        record = {
            "id": row["id"], "victim": row["victim"], "group_name": row["group_name"],
            "discovered_at": row["discovered_at"], "description": row["description"],
            "source_link": row["source_link"], "source": source,
            "country_code": row["country_code"],
            "country_name": row["country_name"], "country_basis": row["country_basis"],
        }
        # Ransomware.live contributes aggregate indicators only in the public dashboard.
        if source != "Ransomware.live":
            posts.append(record)
            stats["rows_visible"] += 1
        group_key = row["group_name"]
        group_entry = group_counts.setdefault(group_key, {
            "name": group_key, "count": 0, "source_counts": {"RansomLook": 0, "Ransomware.live": 0}
        })
        group_entry["count"] += 1
        group_entry["source_counts"][source] = group_entry["source_counts"].get(source, 0) + 1
        stats["groups"].add(group_key)
        code = row["country_code"]
        if code:
            stats["countries"].add(code)
            entry = country_counts.setdefault(code, {
                "code": code, "name": row["country_name"], "lat": row["country_lat"],
                "lon": row["country_lon"], "count": 0,
                "source_counts": {"RansomLook": 0, "Ransomware.live": 0},
            })
            entry["count"] += 1
            entry["source_counts"][source] = entry["source_counts"].get(source, 0) + 1

    # Temporal aggregation exposes only counts by source and time bucket.
    # It intentionally omits victim names and other individual claim details.
    timeline = []
    if period == "24h":
        bucket_seconds = 4 * 60 * 60
        current_bucket = int(datetime.now(timezone.utc).timestamp() // bucket_seconds * bucket_seconds)
        bucket_starts = [
            datetime.fromtimestamp(current_bucket - offset * bucket_seconds, timezone.utc)
            for offset in reversed(range(6))
        ]
        buckets = {
            bucket.strftime("%Y-%m-%dT%H:%M:%SZ"): {
                "key": bucket.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "start": int(bucket.timestamp() * 1000),
                "end": int((bucket + timedelta(seconds=bucket_seconds)).timestamp() * 1000),
                "label": bucket.strftime("%H:%M"), "total": 0,
                "RansomLook": 0, "Ransomware.live": 0
            }
            for bucket in bucket_starts
        }
        for row in rows:
            discovered = _news_parse_date(row["discovered_at"])
            if not discovered or discovered < cutoff:
                continue
            bucket_start = int(discovered.timestamp() // bucket_seconds * bucket_seconds)
            key = datetime.fromtimestamp(bucket_start, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if key not in buckets:
                continue
            source = row["source"] if "source" in row.keys() and row["source"] else "RansomLook"
            if source not in {"RansomLook", "Ransomware.live"}:
                continue
            buckets[key]["total"] += 1
            buckets[key][source] += 1
        timeline = list(buckets.values())
        timeline_unit = "4h"
    else:
        today = datetime.now(timezone.utc).date()
        bucket_dates = [today - timedelta(days=offset) for offset in reversed(range(7))]
        buckets = {
            bucket_date.isoformat(): {
                "key": bucket_date.isoformat(),
                "start": int(datetime.combine(bucket_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000),
                "end": int((datetime.combine(bucket_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)).timestamp() * 1000),
                "label": bucket_date.strftime("%d %b"), "total": 0,
                "RansomLook": 0, "Ransomware.live": 0
            }
            for bucket_date in bucket_dates
        }
        for row in rows:
            discovered = _news_parse_date(row["discovered_at"])
            if not discovered or discovered < cutoff:
                continue
            key = discovered.astimezone(timezone.utc).date().isoformat()
            if key not in buckets:
                continue
            source = row["source"] if "source" in row.keys() and row["source"] else "RansomLook"
            if source not in {"RansomLook", "Ransomware.live"}:
                continue
            buckets[key]["total"] += 1
            buckets[key][source] += 1
        timeline = list(buckets.values())
        timeline_unit = "day"

    countries = sorted(country_counts.values(), key=lambda x: (-x["count"], x["name"]))
    groups = sorted(group_counts.values(), key=lambda x: (-x["count"], x["name"].casefold()))[:8]
    try:
        source_results = json.loads(meta.get("source_results", "[]")) if meta.get("source_results") else []
    except Exception:
        source_results = []
    result_lookup = {item.get("source"): item for item in source_results if isinstance(item, dict)}
    source_output = []
    for source, stats in source_stats.items():
        result = result_lookup.get(source, {})
        source_output.append({
            "source": source, "ok": result.get("ok") if result else None,
            "error": result.get("error"), "cached": bool(result.get("cached")),
            "processed": stats["processed"], "rows_visible": stats["rows_visible"],
            "groups_count": len(stats["groups"]), "countries_count": len(stats["countries"]),
            "last_refresh": meta.get("last_refresh"),
            "last_success": result.get("last_success") or (meta.get("last_refresh") if result.get("ok") else None),
            "checked_at": result.get("checked_at"),
        })
    total_processed = sum(item["processed"] for item in source_output)
    try:
        unmapped_count = sum(1 for row in rows
            if (row["source"] if "source" in row.keys() and row["source"] else "RansomLook") != "Ransomware.live"
            and _news_parse_date(row["discovered_at"]) and _news_parse_date(row["discovered_at"]) >= cutoff
            and not row["country_code"])
    except Exception:
        unmapped_count = 0
    return {
        "period": period, "items": posts, "count": total_processed,
        "listed_items_count": len(posts), "processed_items_count": total_processed,
        "groups_count": len(group_counts), "top_groups": groups,
        "countries": countries, "countries_count": len(countries),
        "timeline": timeline, "timeline_unit": timeline_unit,
        "unmapped_count": unmapped_count,
        "last_refresh": meta.get("last_refresh"), "last_attempt": meta.get("last_attempt"),
        "sources": source_results, "source_stats": source_output,
        "source_home": RANSOMLOOK_HOME, "ransomwarelive_home": RANSOMWARELIVE_HOME,
        "source_attribution": "RansomLook · Ransomware.live",
        "refresh_floor_minutes": RANSOMLOOK_REFRESH_FLOOR_MINUTES,
    }



# Public vulnerability intelligence: CISA KEV + NVD + FIRST EPSS
CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
EPSS_API_URL = "https://api.first.org/data/v1/epss"

def _vuln_meta(key, value=None):
    with db() as c:
        if value is None:
            row = c.execute("SELECT value FROM vulnerability_meta WHERE key=?", (key,)).fetchone()
            return row["value"] if row else None
        c.execute("INSERT INTO vulnerability_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    return str(value)


def _nvd_vulnerability_detail(cve):
    metrics = cve.get("metrics") or {}
    cvss_detail = {}
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key) or []
        if not entries:
            continue
        entry = entries[0] or {}
        data = entry.get("cvssData") or {}
        cvss_detail = {
            "version": data.get("version"), "base_score": data.get("baseScore"),
            "severity": data.get("baseSeverity") or entry.get("baseSeverity"),
            "vector": data.get("vectorString"), "attack_vector": data.get("attackVector"),
            "attack_complexity": data.get("attackComplexity"),
            "privileges_required": data.get("privilegesRequired"),
            "user_interaction": data.get("userInteraction"), "scope": data.get("scope"),
            "confidentiality_impact": data.get("confidentialityImpact"),
            "integrity_impact": data.get("integrityImpact"),
            "availability_impact": data.get("availabilityImpact"),
            "exploit_maturity": data.get("exploitMaturity"),
            "source": entry.get("source"), "type": entry.get("type")
        }
        break
    weaknesses = []
    for weakness in cve.get("weaknesses") or []:
        for desc in weakness.get("description") or []:
            value = desc.get("value")
            if value and value not in weaknesses:
                weaknesses.append(value)
    affected = []
    def walk_node(node):
        if not isinstance(node, dict): return
        for match in node.get("cpeMatch") or []:
            criteria = match.get("criteria") or match.get("cpe23Uri")
            if criteria:
                affected.append({
                    "criteria": criteria, "vulnerable": bool(match.get("vulnerable", True)),
                    "version_start_including": match.get("versionStartIncluding"),
                    "version_start_excluding": match.get("versionStartExcluding"),
                    "version_end_including": match.get("versionEndIncluding"),
                    "version_end_excluding": match.get("versionEndExcluding")
                })
        for child in node.get("children") or []: walk_node(child)
    for config in cve.get("configurations") or []:
        for node in config.get("nodes") or []: walk_node(node)
        if config.get("cpeMatch"): walk_node(config)
    references = []
    for ref in cve.get("references") or []:
        if ref.get("url"):
            references.append({"url":ref["url"],"source":ref.get("source") or "","tags":ref.get("tags") or []})
    return {
        "cvss":cvss_detail,"weaknesses":weaknesses[:20],"affected_products":affected[:50],
        "references":references[:20],"cve_status":cve.get("vulnStatus"),
        "source_identifier":cve.get("sourceIdentifier"),"published":cve.get("published"),
        "last_modified":cve.get("lastModified")
    }


def _workaround_guidance(record, details):
    cisa=details.get("cisa") or {}; nvd=details.get("nvd") or {}; guidance=[]
    if cisa.get("required_action"):
        guidance.append({"kind":"official","title":"Acción requerida por CISA KEV",
                         "text":cisa["required_action"],"source":"CISA KEV"})
    vendor_refs=[r for r in (nvd.get("references") or []) if any(
        t in " ".join(r.get("tags") or []).lower() for t in ("vendor advisory","patch","mitigation"))]
    if vendor_refs:
        guidance.append({"kind":"official_refs","title":"Avisos y parches del fabricante",
                         "text":"Consulta estas referencias antes de aplicar cambios.","references":vendor_refs[:8]})
    else:
        guidance.append({"kind":"caution","title":"Mitigación específica no identificada en los datos disponibles",
                         "text":"Revisa las referencias NVD y confirma con el fabricante qué versiones corrigen la falla. No asumas que una corrección aplica a todas las versiones."})
    guidance.append({"kind":"operational","title":"Medidas compensatorias orientativas",
        "text":"Son controles defensivos generales; no constituyen un workaround confirmado para esta CVE.",
        "steps":[
            "Verifica si los productos y rangos de versión afectados están presentes en el inventario; esta ficha pública no confirma exposición de tus activos.",
            "Mientras se valida la corrección, limita la exposición de red y los accesos al servicio vulnerable cuando sea técnicamente viable.",
            "Si no existe parche, evalúa deshabilitar temporalmente solo la función afectada, con aprobación del responsable del servicio y plan de reversa.",
            "Aumenta temporalmente el monitoreo de indicadores y comportamientos descritos en los avisos del fabricante."
        ]})
    return guidance


def refresh_vulnerability_intel():
    init_db()
    # CISA KEV is the authoritative list of vulnerabilities known to be exploited.
    attempted_at = now()
    _vuln_meta("last_attempt", attempted_at)
    kev_resp = requests.get(CISA_KEV_URL, timeout=TIMEOUT, headers=HEADERS)
    kev_resp.raise_for_status()
    kev_payload = kev_resp.json()
    kev_items = kev_payload.get("vulnerabilities", [])
    kev_by_cve = {x.get("cveID"): x for x in kev_items if x.get("cveID")}
    # NVD provides CVE metadata published/modified in the last 30 days.
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    params = {"pubStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "pubEndDate": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "resultsPerPage": 2000}
    nvd_error = None
    try:
        nvd_resp = requests.get(NVD_API_URL, params=params, timeout=TIMEOUT, headers=HEADERS)
        nvd_resp.raise_for_status()
        nvd_payload = nvd_resp.json()
        nvd_items = nvd_payload.get("vulnerabilities", [])
    except Exception as exc:
        # Preserve a usable CISA KEV refresh when NVD is temporarily unavailable.
        nvd_items = []
        nvd_error = str(exc)[:220]
    # Prioritize KEV + recent NVD entries; enrich a bounded batch with current EPSS.
    records = {}
    for item in nvd_items:
        cve = item.get("cve", {})
        cve_id = cve.get("id")
        if not cve_id: continue
        desc = next((x.get("value", "") for x in cve.get("descriptions", []) if x.get("lang") == "en"), "")
        metrics = cve.get("metrics", {})
        cvss = None
        severity = "Sin CVSS"
        for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            arr = metrics.get(key) or []
            if arr:
                data = arr[0].get("cvssData", {})
                cvss = data.get("baseScore")
                severity = data.get("baseSeverity") or arr[0].get("baseSeverity") or severity
                break
        records[cve_id] = {
            "cve": cve_id, "title": cve_id, "vendor": "", "product": "",
            "description": desc[:1800], "published": cve.get("published", ""),
            "modified": cve.get("lastModified", ""), "cvss": cvss, "severity": severity,
            "kev": 0, "kev_date": "", "ransomware_use": "Unknown",
            "source_url": "https://nvd.nist.gov/vuln/detail/" + cve_id,
            "details": {"nvd": _nvd_vulnerability_detail(cve), "cisa": {}}
        }
    for cve_id, item in kev_by_cve.items():
        rec = records.setdefault(cve_id, {
            "cve": cve_id, "title": item.get("vulnerabilityName", cve_id),
            "vendor": item.get("vendorProject", ""), "product": item.get("product", ""),
            "description": item.get("shortDescription", ""), "published": "",
            "modified": "", "cvss": None, "severity": "Sin CVSS"
        })
        rec.update({"kev": 1, "kev_date": item.get("dateAdded", ""),
                    "ransomware_use": item.get("knownRansomwareCampaignUse", "Unknown"),
                    "source_url": "https://nvd.nist.gov/vuln/detail/" + cve_id})
        rec.setdefault("details", {"nvd": {}, "cisa": {}})
        rec["details"]["cisa"] = {
            "date_added": item.get("dateAdded"), "due_date": item.get("dueDate"),
            "known_ransomware_campaign_use": item.get("knownRansomwareCampaignUse"),
            "required_action": item.get("requiredAction"), "notes": item.get("notes"),
            "cwes": item.get("cwes") or [], "vendor": item.get("vendorProject"),
            "product": item.get("product"), "vulnerability_name": item.get("vulnerabilityName"),
            "short_description": item.get("shortDescription")
        }
        if not rec.get("title") or rec["title"] == cve_id:
            rec["title"] = item.get("vulnerabilityName", cve_id)
        if not rec.get("description"):
            rec["description"] = item.get("shortDescription", "")
        rec["vendor"] = item.get("vendorProject", rec.get("vendor", ""))
        rec["product"] = item.get("product", rec.get("product", ""))
    # EPSS is a probability estimate, not evidence of exploitation. Query the most relevant 100 CVEs.
    ranked = sorted(records.values(), key=lambda x: (x.get("kev", 0), x.get("published", "")), reverse=True)[:100]
    epss_map = {}
    epss_errors = []
    epss_attempted = bool(ranked)
    epss_success = False
    for offset in range(0, len(ranked), 40):
        ids = [x["cve"] for x in ranked[offset:offset+40]]
        if not ids: continue
        try:
            er = requests.get(EPSS_API_URL, params={"cve": ",".join(ids)}, timeout=TIMEOUT, headers=HEADERS)
            er.raise_for_status()
            epss_success = True
            for row in er.json().get("data", []):
                epss_map[row.get("cve")] = (float(row["epss"]), float(row["percentile"]))
        except Exception as exc:
            # EPSS is an enrichment; keep KEV/NVD data if its API is temporarily unavailable.
            epss_errors.append(str(exc)[:180])
    stamp = now()
    with db() as c:
        for rec in records.values():
            ep = epss_map.get(rec["cve"], (None, None))
            c.execute("""INSERT INTO vulnerability_items
              (cve,title,vendor,product,description,published,modified,cvss,severity,kev,kev_date,ransomware_use,epss,epss_percentile,source_url,cached_at,details_json)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(cve) DO UPDATE SET title=excluded.title,vendor=excluded.vendor,product=excluded.product,
              description=excluded.description,published=excluded.published,modified=excluded.modified,cvss=excluded.cvss,
              severity=excluded.severity,kev=excluded.kev,kev_date=excluded.kev_date,ransomware_use=excluded.ransomware_use,
              epss=COALESCE(excluded.epss,vulnerability_items.epss),epss_percentile=COALESCE(excluded.epss_percentile,vulnerability_items.epss_percentile),
              source_url=excluded.source_url,cached_at=excluded.cached_at,
              details_json=COALESCE(excluded.details_json,vulnerability_items.details_json)""",
              (rec["cve"],rec.get("title"),rec.get("vendor"),rec.get("product"),rec.get("description"),
               rec.get("published"),rec.get("modified"),rec.get("cvss"),rec.get("severity"),rec.get("kev",0),
               rec.get("kev_date"),rec.get("ransomware_use"),ep[0],ep[1],rec.get("source_url"),stamp,
               json.dumps(rec.get("details") or {},ensure_ascii=False)))
        c.execute("DELETE FROM vulnerability_items WHERE cached_at < ?", ((datetime.now(timezone.utc)-timedelta(days=45)).isoformat(),))
    source_results = [
        {"source": "CISA KEV", "ok": True, "items": len(kev_items), "checked_at": stamp, "last_success": stamp},
        {"source": "NVD CVE API", "ok": nvd_error is None, "items": len(nvd_items), "checked_at": stamp,
         "last_success": stamp if nvd_error is None else _vuln_meta("nvd_last_success") , **({"error": nvd_error} if nvd_error else {})},
        {"source": "FIRST EPSS", "ok": (epss_success or not epss_attempted) and not epss_errors,
         "items": len(epss_map), "checked_at": stamp, "last_success": stamp if (epss_success or not epss_attempted) else _vuln_meta("epss_last_success"),
         "note": "Sin CVE para enriquecer en esta consulta." if not epss_attempted else ("EPSS es un enriquecimiento opcional." if epss_errors else "Puntajes EPSS consultados."),
         **({"error": "; ".join(epss_errors)[:220]} if epss_errors else {})}
    ]
    _vuln_meta("last_refresh", stamp)
    _vuln_meta("last_success", stamp)
    _vuln_meta("cisa_last_success", stamp)
    if nvd_error is None: _vuln_meta("nvd_last_success", stamp)
    if epss_success or not epss_attempted: _vuln_meta("epss_last_success", stamp)
    _vuln_meta("source_results", json.dumps(source_results, ensure_ascii=False))
    _vuln_meta("kev_count", len(kev_items))
    if nvd_error is None:
        _vuln_meta("nvd_count", len(nvd_items))
    effective_nvd_count = int(_vuln_meta("nvd_count") or 0)
    response = {"ok": True, "partial": nvd_error is not None or bool(epss_errors),
            "kev_count": len(kev_items), "nvd_count": effective_nvd_count,
            "epss_enriched": len(epss_map), "last_refresh": stamp, "last_attempt": attempted_at,
            "sources": source_results}
    record_refresh_run("vulnerabilities", True,
        f"CISA KEV: {len(kev_items)}; NVD: {effective_nvd_count} (caché); EPSS: {len(epss_map)} enriquecidas",
        {"sources": source_results})
    return response

def get_vulnerability_intel(period="30d", search="", sort="modified_desc"):
    if period not in {"7d","30d","all"}:
        raise HTTPException(400, "Período inválido.")
    sort_expressions = {
        "modified_desc": "CASE WHEN modified IS NULL OR modified='' THEN 1 ELSE 0 END, modified DESC, kev DESC",
        "published_desc": "CASE WHEN published IS NULL OR published='' THEN 1 ELSE 0 END, published DESC, kev DESC",
        "epss_desc": "CASE WHEN epss IS NULL THEN 1 ELSE 0 END, epss DESC, kev DESC",
        "cvss_desc": "CASE WHEN cvss IS NULL THEN 1 ELSE 0 END, cvss DESC, kev DESC",
        "kev_desc": "kev DESC, CASE WHEN modified IS NULL OR modified='' THEN 1 ELSE 0 END, modified DESC",
    }
    if sort not in sort_expressions:
        raise HTTPException(400, "Criterio de ordenamiento inválido.")
    cutoff = (datetime.now(timezone.utc)-timedelta(days=7 if period=="7d" else 30)).isoformat() if period!="all" else None
    query = "SELECT * FROM vulnerability_items"
    params = []
    if cutoff:
        query += " WHERE (published >= ? OR kev=1)"
        params.append(cutoff)
    if search:
        query += (" AND" if params else " WHERE") + " (cve LIKE ? OR title LIKE ? OR vendor LIKE ? OR product LIKE ?)"
        params += [f"%{search}%"]*4
    query += f" ORDER BY {sort_expressions[sort]} LIMIT 500"
    with db() as c:
        rows = [dict(r) for r in c.execute(query, params).fetchall()]
    for row in rows:
        row.pop("details_json", None)
    try:
        sources = json.loads(_vuln_meta("source_results") or "[]")
    except Exception:
        sources = []
    return {"items": rows, "count": len(rows), "last_refresh": _vuln_meta("last_refresh"),
            "last_attempt": _vuln_meta("last_attempt"), "sources": sources,
            "kev_count": _vuln_meta("kev_count"), "nvd_count": _vuln_meta("nvd_count"),
            "sort": sort}

def _clean_html(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def _statuspage_detail(service):
    base = service["base_url"].rstrip("/")
    response = requests.get(base + "/api/v2/summary.json", timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    rollup = payload.get("status") or {}
    effective_status, evidence, active_maintenances = statuspage_effective_status(payload)
    components = []
    for item in payload.get("components") or []:
        components.append({
            "name": item.get("name", "Componente"),
            "status": normalize_statuspage(item.get("status")),
            "description": item.get("description") or "",
            "updated_at": item.get("updated_at") or ""
        })
    incidents = []
    for item in payload.get("incidents") or []:
        updates = []
        for update in (item.get("incident_updates") or [])[:10]:
            updates.append({
                "status": update.get("status") or "",
                "body": _clean_html(update.get("body")),
                "created_at": update.get("created_at") or "",
                "display_at": update.get("display_at") or ""
            })
        incidents.append({
            "name": item.get("name") or "Incidente",
            "status": item.get("status") or "",
            "impact": normalize_statuspage(item.get("impact")),
            "created_at": item.get("created_at") or "",
            "updated_at": item.get("updated_at") or "",
            "shortlink": item.get("shortlink") or "",
            "updates": updates
        })
    maintenances = []
    for item in (payload.get("scheduled_maintenances") or [])[:10]:
        maintenances.append({
            "name": item.get("name") or "Mantenimiento",
            "status": item.get("status") or "",
            "scheduled_for": item.get("scheduled_for") or "",
            "scheduled_until": item.get("scheduled_until") or "",
            "updates": [{
                "status": u.get("status") or "",
                "body": _clean_html(u.get("body")),
                "created_at": u.get("created_at") or ""
            } for u in (item.get("incident_updates") or [])[:5]]
        })
    return {
        "source_kind": "statuspage",
        "source_status": (
            (rollup.get("description") or rollup.get("indicator") or "Estado no informado")
            + (f" · Estado efectivo calculado considerando componentes/incidentes activos: {effective_status}"
               if effective_status != normalize_statuspage(rollup.get("indicator")) else "")
        ),
        "status": effective_status,
        "rollup_status": normalize_statuspage(rollup.get("indicator")),
        "status_evidence": [text for _, text in evidence[:8]],
        "components": components,
        "incidents": incidents,
        "maintenances": maintenances
    }


def _microsoft_detail(service):
    endpoint = service.get("api_url")
    if not endpoint:
        raise ValueError("La fuente pública no tiene endpoint configurado.")
    response = requests.get(endpoint, timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    posts = payload if isinstance(payload, list) else [payload]
    items = []
    for post in posts[:15]:
        raw_status = str(post.get("Status") or post.get("status") or "unknown")
        title = str(post.get("Title") or post.get("title") or service["name"])
        body = _clean_html(post.get("Message") or post.get("message") or "")
        updated = post.get("LastUpdatedTime") or post.get("AuthoredDateTime") or ""
        token = raw_status.casefold().replace("_", " ")
        if token in {"available", "operational", "resolved", "none", "healthy"}:
            state = "operational"
        elif any(x in token for x in ("interruption", "outage", "critical", "unavailable")):
            state = "outage"
        elif any(x in token for x in ("degrad", "disruption", "investigat", "identified", "monitoring", "service issue")):
            state = "degraded"
        elif any(x in token for x in ("maintenance", "scheduled")):
            state = "maintenance"
        elif any(x in token for x in ("information", "advisory", "notice")):
            state = "info"
        else:
            state = "unknown"
        items.append({"name": title, "status": state, "source_status": raw_status, "body": body, "updated_at": updated})
    return {
        "source_kind": "microsoft_public",
        "source_status": "Avisos públicos globales de Microsoft; no es Service Health específico del tenant.",
        "status": items[0]["status"] if items else "operational",
        "components": [],
        "incidents": items,
        "maintenances": []
    }


def _google_workspace_detail(service):
    response = requests.get("https://www.google.com/appsstatus/dashboard/incidents.json", timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    wanted = {x.casefold() for x in service.get("product_names", [])}
    incidents = []
    for item in payload if isinstance(payload, list) else []:
        products = item.get("affected_products") or []
        names = {str(p.get("current_title") or p.get("title") or "").casefold() for p in products}
        if not names:
            names = {str(item.get("service_name") or "").casefold()}
        if wanted and not wanted.intersection(names):
            continue
        update = item.get("most_recent_update") or {}
        incidents.append({
            "name": item.get("service_name") or service["name"],
            "status": item.get("status_impact") or update.get("status") or "",
            "impact": str(item.get("status_impact") or "").lower(),
            "created_at": item.get("begin") or "",
            "updated_at": update.get("when") or "",
            "body": _clean_html(update.get("text") or item.get("external_desc") or "")
        })
    impact_map = {"SERVICE_OUTAGE": "outage", "SERVICE_DISRUPTION": "degraded", "SERVICE_INFORMATION": "info"}
    for item in incidents:
        item["status"] = impact_map.get(str(item.get("impact") or "").upper(), "unknown")
    rank = {"operational": 0, "info": 1, "degraded": 2, "outage": 3, "unknown": -1}
    current = max((x["status"] for x in incidents), key=lambda x: rank.get(x, -1), default="operational")
    return {
        "source_kind": "google_workspace",
        "source_status": "Feed público oficial de incidentes activos de Google Workspace.",
        "status": current,
        "components": [],
        "incidents": incidents,
        "maintenances": []
    }


def _google_cloud_detail(service):
    response = requests.get("https://status.cloud.google.com/incidents.json", timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    incidents = []
    for item in payload if isinstance(payload, list) else []:
        if item.get("end"):
            continue
        update = item.get("most_recent_update") or {}
        incidents.append({
            "name": item.get("external_desc") or item.get("service_name") or "Google Cloud incident",
            "status": update.get("status") or "",
            "impact": item.get("severity") or "",
            "created_at": item.get("begin") or "",
            "updated_at": update.get("when") or "",
            "body": _clean_html(update.get("text") or ""),
            "locations": ", ".join(str(x.get("title") or x.get("id") or "") for x in (item.get("currently_affected_locations") or []) if isinstance(x, dict))
        })
    rank = {"operational": 0, "info": 1, "degraded": 2, "outage": 3, "unknown": -1}
    for item in incidents:
        sev = str(item.get("impact") or "").lower()
        state = str(item.get("status") or "").upper()
        item["status"] = ("outage" if state in {"SERVICE_OUTAGE", "OUTAGE"} or sev in {"high", "critical"}
                          else "degraded" if state in {"SERVICE_DISRUPTION", "DISRUPTION"} or sev in {"medium", "moderate"}
                          else "info" if state in {"SERVICE_INFORMATION", "INFORMATIONAL"} or sev == "low"
                          else "unknown")
    current = max((x["status"] for x in incidents), key=lambda x: rank.get(x, -1), default="operational")
    return {
        "source_kind": "google_cloud",
        "source_status": "Feed público general de Google Cloud; no sustituye Personalized Service Health.",
        "status": current,
        "components": [],
        "incidents": incidents[:20],
        "maintenances": []
    }


def _slack_detail(service):
    response = requests.get("https://slack-status.com/api/v2.0.0/current", timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    incidents = []
    for item in payload.get("active_incidents") or []:
        incidents.append({
            "name": item.get("title") or "Slack incident",
            "status": item.get("status") or "",
            "impact": item.get("type") or "",
            "created_at": item.get("date_created") or "",
            "updated_at": item.get("date_updated") or "",
            "body": _clean_html(item.get("title") or "")
        })
    rank = {"operational": 0, "info": 1, "maintenance": 2, "degraded": 3, "outage": 4}
    if payload.get("status") == "ok":
        current = "operational"
    elif incidents:
        current = "outage" if any("outage" in str(x.get("impact", "")).lower() for x in incidents) else "degraded"
    else:
        current = "unknown"
    return {
        "source_kind": "slack",
        "source_status": payload.get("status") or "Estado no informado",
        "status": current,
        "components": [],
        "incidents": incidents,
        "maintenances": []
    }


def build_service_detail(service):
    kind = service.get("type")
    if kind in {"statuspage", "watchguard"}:
        try:
            return _statuspage_detail(service)
        except Exception:
            if kind != "watchguard":
                raise
            # If the Statuspage summary endpoint is unavailable, expose the official Atom feed.
            feed_url = service.get("feed_url") or service["base_url"].rstrip("/") + "/history.atom"
            response = requests.get(feed_url, timeout=TIMEOUT, headers=HEADERS)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            incidents = []
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1].lower() not in {"entry", "item"}:
                    continue
                title, body, updated = "", "", ""
                for child in node.iter():
                    tag = child.tag.rsplit("}", 1)[-1].lower()
                    if tag == "title" and not title:
                        title = _clean_html("".join(child.itertext()))
                    elif tag in {"content", "summary", "description", "encoded"}:
                        body += " " + " ".join(child.itertext())
                    elif tag in {"updated", "pubdate"} and not updated:
                        updated = "".join(child.itertext()).strip()
                incidents.append({"name": title or "WatchGuard update", "status": "feed update", "impact": "", "created_at": updated, "updated_at": updated, "body": _clean_html(body)})
            return {"source_kind":"watchguard_atom","source_status":"Official WatchGuard Atom feed (fallback)", "status":"unknown","components":[],"incidents":incidents[:20],"maintenances":[]}
    if kind == "microsoft_public": return _microsoft_detail(service)
    if kind == "google_workspace": return _google_workspace_detail(service)
    if kind == "google_cloud": return _google_cloud_detail(service)
    if kind == "slack": return _slack_detail(service)
    return {
        "source_kind": "manual",
        "source_status": "Esta plataforma requiere validación en el portal oficial o en el portal autenticado del cliente.",
        "status": "manual",
        "components": [],
        "incidents": [],
        "maintenances": []
    }


@app.get("/api/services/{service_id}/detail")
def get_service_detail(service_id: str):
    service = next((s for s in load_config().get("services", []) if s.get("id") == service_id and s.get("enabled", True)), None)
    if not service:
        raise HTTPException(404, "Plataforma no encontrada.")
    with db() as c:
        row = c.execute("SELECT * FROM services WHERE id=?", (service_id,)).fetchone()
    saved = dict(row) if row else {}
    try:
        live = build_service_detail(service)
        detail_error = None
    except Exception as exc:
        live = {"source_kind": service.get("type", "manual"), "source_status": "No fue posible consultar el detalle en vivo.", "status": "unknown", "components": [], "incidents": [], "maintenances": []}
        detail_error = str(exc)[:250]
    return {
        "service": {
            "id": service["id"], "name": service["name"], "category": service.get("category", "General"),
            "type": service.get("type", "manual"), "base_url": service.get("base_url", ""),
            "portal_label": service.get("portal_label", "Abrir portal oficial"),
            "notes": service.get("notes", "")
        },
        "latest": {
            "status": saved.get("status") or ("manual" if service.get("type") == "manual" else "unknown"),
            "description": saved.get("description") or service.get("notes", ""),
            "checked_at": saved.get("checked_at"),
            "source_status": saved.get("source_status"),
            "error": saved.get("error")
        },
        "live": live,
        "detail_error": detail_error,
        "retrieved_at": now()
    }


@app.get("/api/events")
def get_events(limit: int = 100):
    limit = max(1, min(limit, 500))
    with db() as c: rows = c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/checklist")
def get_checklist(limit: int = 30):
    limit = max(1, min(limit, 100))
    with db() as c: rows = c.execute("SELECT * FROM checklist_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/checklist")
def create_checklist(payload: dict):
    analyst = str(payload.get("analyst", "")).strip()[:80]
    shift_name = str(payload.get("shift_name", "")).strip()[:40]
    checkpoint = str(payload.get("checkpoint", "")).strip().lower()
    notes = str(payload.get("notes", "")).strip()[:1000]
    checked_services = payload.get("checked_services", [])
    allowed_checkpoints = {"inicio", "intermedio", "termino"}
    known_ids = {s["id"] for s in load_config().get("services", [])}
    if not analyst: raise HTTPException(400, "Ingresa el nombre o identificador del analista.")
    if not shift_name: raise HTTPException(400, "Selecciona el turno.")
    if checkpoint not in allowed_checkpoints: raise HTTPException(400, "Momento de revisión inválido.")
    if not isinstance(checked_services, list): raise HTTPException(400, "La lista de plataformas revisadas no es válida.")
    clean_ids = sorted({str(x) for x in checked_services if str(x) in known_ids})
    if not clean_ids: raise HTTPException(400, "Marca al menos una plataforma revisada.")
    created = now()
    with db() as c:
        cur = c.execute("""INSERT INTO checklist_runs(analyst,shift_name,checkpoint,checked_services,total_services,notes,created_at)
            VALUES(?,?,?,?,?,?,?)""", (analyst, shift_name, checkpoint, json.dumps(clean_ids), len(clean_ids), notes, created))
        run_id = cur.lastrowid
    return {"ok": True, "id": run_id, "analyst": analyst, "shift_name": shift_name,
            "checkpoint": checkpoint, "total_services": len(clean_ids), "created_at": created}



@app.get("/api/threat-intel/news")
def api_threat_news(period: str = "7d"):
    if period not in {"24h", "7d"}:
        raise HTTPException(400, "El período debe ser 24h o 7d.")
    return get_cached_threat_news(period)


@app.post("/api/threat-intel/news/refresh")
def api_refresh_threat_news():
    try:
        return refresh_threat_news()
    except Exception as exc:
        raise HTTPException(502, f"No se pudo actualizar la inteligencia externa: {str(exc)[:220]}")


@app.get("/api/threat-intel/ransomware")
def api_ransomware_tracker(period: str = "7d"):
    if period not in {"24h", "7d"}:
        raise HTTPException(400, "El período debe ser 24h o 7d.")
    return get_cached_ransomware(period)


@app.post("/api/threat-intel/ransomware/refresh")
def api_refresh_ransomware_tracker():
    try:
        return refresh_ransomware_tracker()
    except Exception as exc:
        raise HTTPException(502, f"No se pudo actualizar el tracker de ransomware: {str(exc)[:220]}")


@app.get("/api/threat-intel/vulnerabilities/{cve_id}")
def api_vulnerability_detail(cve_id: str):
    normalized=cve_id.upper()
    if not re.fullmatch(r"CVE-\d{4}-\d{4,}", normalized):
        raise HTTPException(400,"Identificador CVE inválido.")
    with db() as c:
        row=c.execute("SELECT * FROM vulnerability_items WHERE cve=?",(normalized,)).fetchone()
    if not row:
        raise HTTPException(404,"La CVE no está en caché. Actualiza las fuentes públicas e inténtalo nuevamente.")
    item=dict(row)
    try: details=json.loads(item.get("details_json") or "{}")
    except (TypeError,json.JSONDecodeError): details={}
    details.setdefault("nvd",{}); details.setdefault("cisa",{})
    nvd=details.get("nvd") or {}
    if not (nvd.get("cvss") or nvd.get("references") or nvd.get("affected_products")):
        try:
            resp=requests.get(NVD_API_URL,params={"cveId":normalized},timeout=min(TIMEOUT,8),headers=HEADERS)
            resp.raise_for_status()
            nvd_rows=resp.json().get("vulnerabilities") or []
            if nvd_rows and nvd_rows[0].get("cve"):
                details["nvd"]=_nvd_vulnerability_detail(nvd_rows[0]["cve"])
        except Exception as exc:
            details["lookup_note"]=f"No fue posible ampliar el detalle NVD en esta consulta: {str(exc)[:160]}"
    if item.get("epss") is None:
        try:
            resp=requests.get(EPSS_API_URL,params={"cve":normalized},timeout=min(TIMEOUT,6),headers=HEADERS)
            resp.raise_for_status(); rows=resp.json().get("data") or []
            if rows:
                item["epss"]=float(rows[0].get("epss")); item["epss_percentile"]=float(rows[0].get("percentile"))
                with db() as c:
                    c.execute("UPDATE vulnerability_items SET epss=?,epss_percentile=? WHERE cve=?",
                              (item["epss"],item["epss_percentile"],normalized))
        except Exception: pass
    details["workaround_guidance"]=_workaround_guidance(item,details)
    if details.get("nvd") and (details["nvd"].get("cvss") or details["nvd"].get("references") or details["nvd"].get("affected_products")):
        with db() as c:
            c.execute("UPDATE vulnerability_items SET details_json=? WHERE cve=?",
                      (json.dumps({k:v for k,v in details.items() if k!="workaround_guidance"},ensure_ascii=False),normalized))
    return {"item":{k:v for k,v in item.items() if k!="details_json"},"details":details}


@app.get("/api/threat-intel/vulnerabilities")
def api_vulnerability_intel(period: str = "30d", search: str = "", sort: str = "modified_desc"):
    return get_vulnerability_intel(period, search[:100], sort)

@app.post("/api/threat-intel/vulnerabilities/refresh")
def api_refresh_vulnerability_intel():
    try:
        return refresh_vulnerability_intel()
    except Exception as exc:
        attempted = now()
        _vuln_meta("last_attempt", attempted)
        try:
            previous = json.loads(_vuln_meta("source_results") or "[]")
        except Exception:
            previous = []
        prior = {x.get("source"): x for x in previous if isinstance(x, dict)}
        failed = []
        for name in ("CISA KEV", "NVD CVE API", "FIRST EPSS"):
            old = prior.get(name, {})
            failed.append({"source": name, "ok": False, "checked_at": attempted,
                           "last_success": old.get("last_success"),
                           "error": str(exc)[:220] if name == "CISA KEV" else "No se ejecutó por fallo de la fuente primaria."})
        _vuln_meta("source_results", json.dumps(failed, ensure_ascii=False))
        record_refresh_run("vulnerabilities", False, f"Error en actualización: {str(exc)[:200]}", {"sources": failed})
        raise HTTPException(502, f"No se pudo actualizar inteligencia de vulnerabilidades: {str(exc)[:220]}")



def _health_age_minutes(timestamp):
    parsed = _news_parse_date(timestamp) if timestamp else None
    if not parsed:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds() // 60))


def _classify_health_source(source, fallback_success=None, stale_after_minutes=1440):
    checked = source.get("checked_at") or source.get("last_attempt")
    last_success = source.get("last_success") or fallback_success
    age = _health_age_minutes(last_success)
    if checked is None and last_success is None:
        state = "pending"
    elif source.get("ok") is False:
        state = "error" if age is None or age >= stale_after_minutes else "warning"
    elif age is None:
        state = "pending"
    elif age >= stale_after_minutes:
        state = "stale"
    else:
        state = "healthy"
    return {**source, "status": state, "age_minutes": age,
            "checked_at": checked, "last_success": last_success}


def _health_module(sources, attempted=None, last_success=None, manual=0, warning=None, stale_after_minutes=1440):
    normalized = [_classify_health_source(item, fallback_success=last_success,
                  stale_after_minutes=stale_after_minutes) for item in sources]
    healthy = sum(1 for item in normalized if item["status"] == "healthy")
    failed = sum(1 for item in normalized if item["status"] == "error")
    stale = sum(1 for item in normalized if item["status"] == "stale")
    warnings = sum(1 for item in normalized if item["status"] == "warning")
    pending = sum(1 for item in normalized if item["status"] == "pending")
    if not normalized or pending == len(normalized): state = "pending"
    elif failed == len(normalized): state = "error"
    elif failed or stale or warnings: state = "partial"
    elif pending: state = "partial"
    else: state = "healthy"
    return {"status": state, "sources": normalized, "healthy": healthy,
            "failed": failed, "stale": stale, "warnings": warnings,
            "pending": pending, "manual": manual, "last_attempt": attempted,
            "last_success": last_success, "warning": warning}


@app.get("/api/health")
def api_health():
    """Cache-only diagnostics: checks local DB and the latest saved source results, never calls vendors."""
    init_db()
    generated = now()
    db_ok = False
    counts = {}
    with db() as c:
        c.execute("SELECT 1").fetchone()
        db_ok = True
        for table in ("services", "events", "threat_news", "ransomware_posts", "vulnerability_items", "refresh_runs"):
            counts[table] = int(c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        recent_runs = [dict(row) for row in c.execute(
            "SELECT id,module,attempted_at,ok,summary,details_json FROM refresh_runs ORDER BY id DESC LIMIT 15").fetchall()]
    services = get_status().get("services", [])
    automatic = [item for item in services if item.get("type") != "manual"]
    manual_count = sum(1 for item in services if item.get("type") == "manual")
    platform_sources = []
    for item in automatic:
        platform_sources.append({"source": item["name"], "ok": not bool(item.get("error")) and bool(item.get("checked_at")),
            "checked_at": item.get("checked_at"), "last_success": item.get("last_success_at"),
            "error": item.get("error"), "service_status": item.get("status"), "note": item.get("description", "")[:180]})
    platform_last = max((item.get("checked_at") for item in automatic if item.get("checked_at")), default=None)
    modules = {"platforms": _health_module(platform_sources, attempted=platform_last,
                manual=manual_count, stale_after_minutes=60)}

    news_meta = _read_meta_table("threat_news_meta")
    try: news_sources = json.loads(news_meta.get("source_results", "[]"))
    except Exception: news_sources = []
    modules["news"] = _health_module(news_sources, news_meta.get("last_attempt"), news_meta.get("last_refresh"))

    ransom_meta = _get_ransom_meta()
    try: ransom_sources = json.loads(ransom_meta.get("source_results", "[]"))
    except Exception: ransom_sources = []
    modules["ransomware"] = _health_module(ransom_sources, ransom_meta.get("last_attempt"), ransom_meta.get("last_refresh"))

    vuln_meta = _read_meta_table("vulnerability_meta")
    try: vuln_sources = json.loads(vuln_meta.get("source_results", "[]"))
    except Exception: vuln_sources = []
    if not vuln_sources and vuln_meta.get("last_refresh"):
        vuln_sources = [
            {"source": "CISA KEV", "ok": True, "last_success": vuln_meta.get("last_refresh")},
            {"source": "NVD CVE API", "ok": True, "last_success": vuln_meta.get("last_refresh")},
            {"source": "FIRST EPSS", "ok": None, "note": "Sin detalle histórico de esta versión."}
        ]
    modules["vulnerabilities"] = _health_module(vuln_sources, vuln_meta.get("last_attempt"), vuln_meta.get("last_refresh"))

    module_states = [item["status"] for item in modules.values()]
    overall = "healthy" if module_states and all(x == "healthy" for x in module_states) else (
        "error" if module_states and all(x == "error" for x in module_states) else
        "partial" if any(x in {"error", "partial", "stale"} for x in module_states) else "pending")
    for item in recent_runs:
        try: item["details"] = json.loads(item.pop("details_json") or "{}")
        except Exception: item["details"] = {}; item.pop("details_json", None)
    return {"ok": db_ok, "version": APP_VERSION, "generated_at": generated,
        "started_at": APP_STARTED_AT, "overall": overall, "modules": modules,
        "database": {"ok": db_ok, "engine": "SQLite", "counts": counts,
            "persistence": "ephemeral", "warning": "La base SQLite reside en el sistema de archivos local. En Render Free puede perderse al reiniciar, suspenderse o redesplegarse."},
        "recent_refreshes": recent_runs}


@app.get("/api/executive-summary")
def api_executive_summary():
    """Compact snapshot for the home dashboard, assembled only from existing caches."""
    platforms = get_status()
    news = get_cached_threat_news("7d")
    ransomware = get_cached_ransomware("7d")
    vulnerabilities = get_vulnerability_intel("30d", "", "modified_desc")

    # Platform status and last successful observation.
    platform_services = platforms.get("services") or []
    platform_counts = platforms.get("counts") or {}
    checked = [item.get("checked_at") for item in platform_services if item.get("checked_at")]
    latest_platform_check = max(checked) if checked else None
    automated = [item for item in platform_services if item.get("type") != "manual" and item.get("checked_at")]
    stale_platforms = 0
    for item in automated:
        stamp = _news_parse_date(item.get("checked_at"))
        if stamp and (datetime.now(timezone.utc) - stamp) >= timedelta(minutes=60):
            stale_platforms += 1

    # Count topical tags once per article. "global" is intentionally omitted.
    category_counts = {key: 0 for key in NEWS_CATEGORIES if key != "global"}
    for item in news.get("items", []):
        for category in set(item.get("categories") or []):
            if category in category_counts:
                category_counts[category] += 1

    # Ransomware observations are source observations, not unique confirmed incidents.
    ransomware_sources = ransomware.get("source_stats") or []
    ransomware_source_ok = sum(1 for item in ransomware_sources if item.get("ok") is True)
    ransomware_source_total = len(ransomware_sources)
    ransomware_groups = ransomware.get("top_groups") or []
    ransomware_countries = ransomware.get("countries") or []

    # Severity distribution uses the currently cached 30-day + KEV window.
    vuln_items = vulnerabilities.get("items") or []
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "OTHER": 0}
    epss_over_50 = 0
    for item in vuln_items:
        severity = str(item.get("severity") or "OTHER").upper()
        if severity not in severity_counts or severity in {"OTHER"}:
            severity_counts["OTHER"] += 1
        else:
            severity_counts[severity] += 1
        try:
            if item.get("epss") is not None and float(item["epss"]) >= 0.5:
                epss_over_50 += 1
        except (TypeError, ValueError):
            pass

    return {
        "generated_at": now(),
        "windows": {"news": "7d", "ransomware": "7d", "vulnerabilities": "30d + KEV"},
        "platforms": {
            "total": len(platform_services),
            "counts": platform_counts,
            "stale": stale_platforms,
            "manual": int(platform_counts.get("manual", 0)),
            "latest_check": latest_platform_check,
        },
        "news": {
            "count": int(news.get("count", 0)),
            "categories": category_counts,
            "sources_total": len(news.get("sources") or []),
            "sources_ok": sum(1 for item in news.get("sources") or [] if item.get("ok")),
            "last_refresh": news.get("last_refresh"),
        },
        "ransomware": {
            "processed": int(ransomware.get("processed_items_count", ransomware.get("count", 0))),
            "listed": int(ransomware.get("listed_items_count", len(ransomware.get("items") or []))),
            "groups_count": int(ransomware.get("groups_count", 0)),
            "countries_count": int(ransomware.get("countries_count", 0)),
            "top_groups": ransomware_groups[:5],
            "top_countries": ransomware_countries[:5],
            "sources_total": ransomware_source_total,
            "sources_ok": ransomware_source_ok,
            "source_stats": ransomware_sources,
            "last_refresh": ransomware.get("last_refresh"),
        },
        "vulnerabilities": {
            "visible": int(vulnerabilities.get("count", len(vuln_items))),
            "kev_count": int(vulnerabilities.get("kev_count") or 0),
            "nvd_count": int(vulnerabilities.get("nvd_count") or 0),
            "severity": severity_counts,
            "epss_50_plus": epss_over_50,
            "last_refresh": vulnerabilities.get("last_refresh"),
        },
    }


@app.get("/api/config")
def get_config():
    return {"services": load_config().get("services", []), "mode": "manual"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
