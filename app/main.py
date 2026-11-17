from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import datetime, timezone
import sqlite3, json, os, re
import xml.etree.ElementTree as ET
import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")
CONFIG_PATH = BASE / "config.json"
DB_PATH = os.getenv("DATABASE_PATH", str(BASE / "data" / "status_monitor.db"))
TIMEOUT = 12
HEADERS = {"User-Agent": "SOC-Service-Status-Monitor/1.5 (+public vendor status checks)"}
app = FastAPI(title="SOC Service Status Monitor", version="1.6.0")
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
        cols = {r[1] for r in c.execute("PRAGMA table_info(services)").fetchall()}
        for name, typ in [("category", "TEXT"), ("portal_label", "TEXT"), ("source_status", "TEXT"), ("error", "TEXT")]:
            if name not in cols:
                c.execute(f"ALTER TABLE services ADD COLUMN {name} {typ}")


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


def fetch_statuspage(service):
    base = service["base_url"].rstrip("/")
    endpoint = base + "/api/v2/summary.json"
    response = requests.get(endpoint, timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    rollup = payload.get("status") or {}
    status = normalize_statuspage(rollup.get("indicator"))
    description = rollup.get("description") or "El proveedor no publicó una descripción."
    component_states = []
    for component in payload.get("components") or []:
        cstatus = normalize_statuspage(component.get("status"))
        if cstatus not in {"operational", "unknown"}:
            component_states.append((component.get("name", "Componente"), cstatus))
    rank = {"operational": 0, "info": 1, "maintenance": 2, "degraded": 3, "outage": 4}
    if component_states:
        worst = max((s for _, s in component_states), key=lambda x: rank.get(x, 0))
        if rank.get(worst, 0) > rank.get(status, 0):
            status = worst
        description += " | Componentes: " + ", ".join(f"{n}: {s}" for n, s in component_states[:5])
    active = payload.get("incidents") or []
    if active:
        titles, impacts = [], []
        for incident in active[:5]:
            impact = normalize_statuspage(incident.get("impact"))
            impacts.append(impact)
            titles.append(f"{incident.get('name') or 'Incidente activo'} ({incident.get('impact') or 'impacto no informado'})")
        worst = max(impacts, key=lambda x: rank.get(x, 0), default="unknown")
        if rank.get(worst, 0) > rank.get(status, 0): status = worst
        description = "Incidentes activos: " + " | ".join(titles)
    maintenances = payload.get("scheduled_maintenances") or []
    active_maint = [m for m in maintenances if (m.get("status") or "").lower().replace("_", " ") in {"in progress", "verifying"}]
    if active_maint and status == "operational":
        status = "maintenance"
        description = "Mantenimiento en curso: " + " | ".join(m.get("name", "Mantenimiento") for m in active_maint[:3])
    upcoming = [m for m in maintenances if (m.get("status") or "").lower().replace("_", " ") in {"scheduled", "not started"}]
    if upcoming:
        description += f" | Mantenimientos programados: {len(upcoming)}"
    return status, description, base + "/", rollup.get("indicator", "")


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
    with db() as c:
        previous = c.execute("SELECT status FROM services WHERE id=?", (service["id"],)).fetchone()
        old = previous["status"] if previous else None
        c.execute("""INSERT INTO services(id,name,category,portal_label,status,description,source_url,checked_at,source_status,error)
            VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,category=excluded.category,portal_label=excluded.portal_label,status=excluded.status,
            description=excluded.description,source_url=excluded.source_url,checked_at=excluded.checked_at,
            source_status=excluded.source_status,error=excluded.error""",
            (service["id"], service["name"], service.get("category", "General"), service.get("portal_label", "Abrir portal oficial"),
             status, description, source_url, checked, raw, error))
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
    return {"ok": True, "checked": len(results),
            "automated": sum(1 for s in enabled if s.get("type") != "manual"),
            "manual": sum(1 for s in enabled if s.get("type") == "manual"),
            "success": sum(1 for r in results if r["status"] not in {"unknown", "manual"}),
            "errors": sum(1 for r in results if r["status"] == "unknown"),
            "results": results, "completed_at": now()}


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



def _clean_html(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def _statuspage_detail(service):
    base = service["base_url"].rstrip("/")
    response = requests.get(base + "/api/v2/summary.json", timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    rollup = payload.get("status") or {}
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
        "source_status": rollup.get("description") or rollup.get("indicator") or "Estado no informado",
        "status": normalize_statuspage(rollup.get("indicator")),
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


@app.get("/api/config")
def get_config():
    return {"services": load_config().get("services", []), "mode": "manual"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
