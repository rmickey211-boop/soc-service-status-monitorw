# SOC Service Status Monitor — Fase 1 v1.3

Dashboard web con 31 plataformas/servicios para checklist MDR, consulta manual mediante el botón **Actualizar ahora** y enlaces a los portales oficiales. No realiza polling en segundo plano, no envía correos y no requiere API Keys para las fuentes públicas integradas.

## Plataformas incluidas

### Consulta automática sin API Key (12 tarjetas)
- Google Workspace: Gmail, Google Drive, Google Meet, Google Calendar, Google Chat y Admin Console (feed JSON oficial de incidentes).
- Exabeam, Tenable, Cloudflare, GitHub y Atlassian (API pública de Statuspage).
- Slack (API oficial pública `slack-status.com/api/v2.0.0/current`).

### Verificación manual en portal oficial (19 tarjetas)
- Microsoft Exchange Online, Microsoft Teams, SharePoint Online y OneDrive for Business.
- Microsoft Azure y Power Platform.
- Google Cloud Platform.
- Microsoft Entra ID y Defender XDR; Wazuh, Gurucul, Fortinet/FortiGuard, WatchGuard, CrowdStrike (Falcon Status requiere acceso de cliente), Okta, Cisco Umbrella, Cisco Cloud, Zoom, AWS y Google Cloud.

**Importante:** en Microsoft 365, el portal público permite comprobar avisos generales, pero el estado detallado por servicio/tenant —incluido Exchange Online— se consulta en el Centro de administración con una cuenta autorizada. No se simula una lectura automática donde el fabricante no ofrece una fuente pública apropiada.

Google publica un JSON de historial de incidentes y documenta su uso programático. El recolector considera activos los incidentes sin fecha de término y cuyo último estado no esté marcado como `AVAILABLE`; los estados de información se muestran como AVISO, no como degradación.

## Ejecutar localmente en Windows 11

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abrir http://127.0.0.1:8000 y pulsar **Actualizar ahora**.

## Despliegue en Render

El archivo `render.yaml` define un Web Service en plan Free. También se puede crear el servicio manualmente desde el repositorio:
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/status`

En Render Free el servicio puede dormir por inactividad y tardar en despertar al abrir la página. El botón ejecuta la consulta una vez que el servicio está activo. El almacenamiento local gratuito es efímero: el historial SQLite puede perderse al reiniciar, redeplegar o suspender el servicio. La Fase 1 está pensada como consulta operacional, no como registro histórico de auditoría garantizado.

## Estados
- OPERATIVO: la fuente pública no reporta incidentes activos.
- AVISO: Google publica información/aviso sin clasificarlo como interrupción.
- DEGRADADO: degradación o interrupción parcial.
- INDISPONIBILIDAD: outage mayor/crítico.
- MANTENIMIENTO: mantenimiento en curso informado por el proveedor.
- CONSULTA MANUAL: abrir el portal del fabricante; no hay lectura automática configurada.
- SIN INFORMACIÓN: el endpoint no respondió o el formato no pudo interpretarse. No significa que el proveedor esté caído.

## Buenas prácticas y límites
- El portal Falcon Status de CrowdStrike está disponible para clientes desde su consola/portal y no se trata como una fuente pública universal. El estado público del fabricante no garantiza el estado de la instancia/tenant de cada cliente.
- Una consulta correcta confirma lo que publica el fabricante, no prueba conectividad desde las redes de clientes.
- Las URLs y formatos pueden cambiar; validar las fuentes antes de incorporar el dashboard al procedimiento formal.
- La aplicación no tiene autenticación en esta fase. Si se usa para el equipo, restringir el acceso mediante la configuración de Render/red corporativa o agregar autenticación antes de publicar datos internos.
- No se incluyen credenciales ni API Keys.

## Endpoints
- `GET /api/status`: estado almacenado y contadores.
- `GET /api/events`: cambios detectados entre consultas.
- `POST /api/poll`: ejecutar una consulta manual a todas las fuentes automáticas.
- `GET /api/config`: lista de fuentes y categorías.
