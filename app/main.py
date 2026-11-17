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
HEADERS = {"User-Agent": "SOC-Service-Status-Monitor/1.4 (+manual operator initiated checks)"}
app = FastAPI(title="SOC Service Status Monitor", version="1.4.2")
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


def fetch_service(service, google_payload=None):
    kind = service.get("type")
    if kind == "statuspage": return fetch_statuspage(service)
    if kind == "slack": return fetch_slack(service)
    if kind == "google_workspace":
        if google_payload is None: raise RuntimeError("No se pudo obtener el feed oficial de Google Workspace.")
        return fetch_google_workspace(service, google_payload)
    if kind == "google_cloud": return fetch_google_cloud(service)
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
