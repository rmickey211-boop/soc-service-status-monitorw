from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import datetime, timezone
import sqlite3, json, os, re
import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")
CONFIG_PATH = BASE / "config.json"
DB_PATH = os.getenv("DATABASE_PATH", str(BASE / "data" / "status_monitor.db"))
TIMEOUT = 12
HEADERS = {"User-Agent": "SOC-Service-Status-Monitor/1.0 (+manual operator initiated checks)"}

app = FastAPI(title="SOC Service Status Monitor", version="1.3.0")
app.mount("/static", StaticFiles(directory=str(BASE / "app" / "static")), name="static")


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY, name TEXT, category TEXT, portal_label TEXT, status TEXT, description TEXT,
            source_url TEXT, checked_at TEXT, source_status TEXT, error TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, service_id TEXT, service_name TEXT,
            old_status TEXT, new_status TEXT, description TEXT, occurred_at TEXT,
            source_url TEXT)""")
        # Migrate an earlier prototype database without deleting its history.
        cols = {r[1] for r in c.execute("PRAGMA table_info(services)").fetchall()}
        for name, typ in [("category", "TEXT"), ("portal_label", "TEXT"), ("source_status", "TEXT"), ("error", "TEXT")]:
            if name not in cols:
                c.execute(f"ALTER TABLE services ADD COLUMN {name} {typ}")


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def normalize_statuspage(value):
    s = (value or "").strip().lower().replace("_", " ")
    # Statuspage roll-up indicators: none, minor, major, critical.
    if s in {"none", "operational", "ok", "resolved"}:
        return "operational"
    if s in {"minor", "degraded performance", "degraded", "partial outage", "service disruption"}:
        return "degraded"
    if s in {"major", "critical", "major outage", "outage", "service outage"}:
        return "outage"
    if "maintenance" in s:
        return "maintenance"
    # Component statuses
    if s == "operational": return "operational"
    if s == "partial outage": return "degraded"
    if s == "major outage": return "outage"
    if s == "degraded performance": return "degraded"
    return "unknown"


def fetch_statuspage(service):
    base = service["base_url"].rstrip("/")
    endpoint = base + "/api/v2/summary.json"
    response = requests.get(endpoint, timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    rollup = (payload.get("status") or {})
    status = normalize_statuspage(rollup.get("indicator"))
    description = rollup.get("description") or "El proveedor no publicó una descripción."

    # Component-level status can reveal a degradation not reflected in the roll-up.
    component_states = []
    for component in payload.get("components") or []:
        cstatus = normalize_statuspage(component.get("status"))
        if cstatus != "operational" and cstatus != "unknown":
            component_states.append((component.get("name", "Componente"), cstatus))
    if component_states:
        rank = {"operational": 0, "maintenance": 1, "degraded": 2, "outage": 3}
        worst = max((s for _, s in component_states), key=lambda x: rank.get(x, 0))
        if rank.get(worst, 0) > rank.get(status, 0):
            status = worst
        detail = ", ".join(f"{n}: {s.replace('_',' ')}" for n, s in component_states[:5])
        description = f"{description} | Componentes: {detail}"

    active = payload.get("incidents") or []
    if active:
        titles = []
        impacts = []
        for incident in active[:5]:
            title = incident.get("name") or "Incidente activo"
            impact = normalize_statuspage(incident.get("impact"))
            impacts.append(impact)
            titles.append(f"{title} ({incident.get('impact','impacto no informado')})")
        rank = {"operational": 0, "maintenance": 1, "degraded": 2, "outage": 3}
        worst = max(impacts, key=lambda x: rank.get(x, 0), default="unknown")
        if rank.get(worst, 0) > rank.get(status, 0): status = worst
        description = "Incidentes activos: " + " | ".join(titles)

    maintenances = payload.get("scheduled_maintenances") or []
    active_maint = [m for m in maintenances if (m.get("status") or "").lower() in {"in_progress", "in progress"}]
    if active_maint and status == "operational":
        status = "maintenance"
        description = "Mantenimiento en curso: " + " | ".join(m.get("name", "Mantenimiento") for m in active_maint[:3])
    elif maintenances and not active:
        upcoming = [m for m in maintenances if (m.get("status") or "").lower() in {"scheduled", "not_started", "not started"}]
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
        update_status = ((incident.get("most_recent_update") or {}).get("status") or "").upper()
        if incident.get("end") or update_status == "AVAILABLE":
            continue
        impact = (incident.get("status_impact") or "").upper()
        if impact == "SERVICE_OUTAGE":
            status = "outage"
        elif impact == "SERVICE_DISRUPTION":
            status = "degraded"
        elif impact == "SERVICE_INFORMATION":
            status = "info"
        else:
            status = "unknown"
        active.append((status, incident.get("external_desc") or "Incidente publicado por Google.", incident.get("id")))
    rank = {"operational": 0, "info": 1, "degraded": 2, "outage": 3, "unknown": -1}
    if not active:
        return "operational", "No hay incidentes activos publicados para este servicio.", service["base_url"], "AVAILABLE"
    worst = max((x[0] for x in active), key=lambda x: rank.get(x, -1))
    details = []
    for status, desc, incident_id in active[:4]:
        clean = re.sub(r"\s+", " ", desc).strip()
        details.append(clean[:420])
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
    titles = []
    for item in incidents[:5]:
        title = item.get("title", "Incidente activo")
        titles.append(title)
    types = {str(x.get("type", "incident")).lower() for x in incidents}
    incident_states = {str(x.get("status", "active")).lower() for x in incidents}
    if "scheduled" in incident_states or "maintenance" in types:
        status = "maintenance"
    else:
        status = "outage" if "outage" in types else "degraded"
    return status, "Incidentes activos: " + " | ".join(titles), service["base_url"], str(payload.get("status", "active"))


def fetch_service(service, google_payload=None):
    kind = service.get("type")
    if kind == "statuspage":
        return fetch_statuspage(service)
    if kind == "slack":
        return fetch_slack(service)
    if kind == "google_workspace":
        if google_payload is None:
            raise RuntimeError("No se pudo obtener el feed oficial de Google Workspace.")
        return fetch_google_workspace(service, google_payload)
    if kind == "manual":
        return "manual", service.get("notes") or "Revisión manual en el portal oficial.", service["base_url"], "manual"
    raise RuntimeError(f"Tipo de fuente no soportado: {kind}")


def store_result(service, status, description, source_url, raw, error=None):
    # Manual portals are not fetched by the backend; do not imply they were checked.
    checked = None if status == "manual" else now()
    with db() as c:
        previous = c.execute("SELECT status FROM services WHERE id=?", (service["id"],)).fetchone()
        old = previous["status"] if previous else None
        c.execute("""INSERT INTO services(id,name,category,portal_label,status,description,source_url,checked_at,source_status,error)
            VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,category=excluded.category,portal_label=excluded.portal_label,status=excluded.status,
            description=excluded.description,source_url=excluded.source_url,
            checked_at=excluded.checked_at,source_status=excluded.source_status,error=excluded.error""",
            (service["id"], service["name"], service.get("category", "General"),
             service.get("portal_label", "Abrir portal oficial"), status, description,
             source_url, checked, raw, error))
        # Keep an audit trail of confirmed status transitions only; unknown/manual are not outages.
        if old is not None and status not in {"unknown", "manual"} and old not in {"unknown", "manual"} and old != status:
            c.execute("""INSERT INTO events(service_id,service_name,old_status,new_status,description,occurred_at,source_url)
                VALUES(?,?,?,?,?,?,?)""", (service["id"], service["name"], old, status, description, checked, source_url))
    return {"id": service["id"], "status": status, "error": error}


def poll_once():
    config = load_config()
    enabled = [s for s in config.get("services", []) if s.get("enabled", True)]
    google_payload = None
    if any(s.get("type") == "google_workspace" for s in enabled):
        try:
            r = requests.get("https://www.google.com/appsstatus/dashboard/incidents.json", timeout=TIMEOUT, headers=HEADERS)
            r.raise_for_status()
            google_payload = r.json()
            if not isinstance(google_payload, list):
                raise ValueError("Formato JSON de Google Workspace no reconocido")
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

    # Parallelize requests so a slow provider does not block the entire checklist refresh.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(run_one, service) for service in enabled]
        for future in as_completed(futures):
            results.append(future.result())
    return {
        "ok": True,
        "checked": len(results),
        "automated": sum(1 for s in enabled if s.get("type") != "manual"),
        "manual": sum(1 for s in enabled if s.get("type") == "manual"),
        "success": sum(1 for r in results if r["status"] not in {"unknown", "manual"}),
        "errors": sum(1 for r in results if r["status"] == "unknown"),
        "results": results,
        "completed_at": now()
    }


@app.on_event("startup")
def startup():
    # Fase 1: el analista ejecuta cada consulta con el botón. No hay polling en segundo plano.
    init_db()


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "app" / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def get_status():
    with db() as c:
        rows = c.execute("SELECT * FROM services ORDER BY category, name").fetchall()
    result = [dict(r) for r in rows]
    keys = ["operational", "info", "degraded", "outage", "maintenance", "manual", "unknown"]
    counts = {k: sum(1 for x in result if x["status"] == k) for k in keys}
    return {"services": result, "counts": counts, "server_time": now(), "mode": "manual"}


@app.get("/api/events")
def get_events(limit: int = 100):
    limit = max(1, min(limit, 500))
    with db() as c:
        rows = c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/poll")
def manual_poll():
    try:
        return poll_once()
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/config")
def get_config():
    return {"services": load_config().get("services", []), "mode": "manual"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
