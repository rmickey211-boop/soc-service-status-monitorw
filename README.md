# SOC Service Status Monitor — Fase 1.4

Versión evolutiva sobre el v1.3 desplegado en Render. Conserva la consulta bajo demanda, el catálogo previo, los enlaces oficiales, filtros, historial de cambios y suma indicadores de antigüedad, nuevas fuentes públicas y registro piloto del checklist MDR.

## Novedades v1.4
- Dashboard ampliado con contadores de mantenimiento y antigüedad de datos.
- Filtro por datos actualizados, antiguos (60 minutos o más) y nunca consultados.
- Checklist MDR: analista, turno, momento (inicio/intermedio/término), plataformas revisadas y observaciones.
- Historial de revisiones.
- Integración adicional de Google Cloud Service Health mediante su feed JSON público documentado.
- Nuevas páginas Statuspage públicas: DigitalOcean, GitLab.com y Datadog US1.
- Se conserva la consulta manual; no se añade polling en segundo plano ni correo.

## Fuentes automáticas
- Google Workspace: Gmail, Drive, Meet, Calendar, Chat y Admin Console mediante el feed público de incidentes.
- Google Cloud Service Health mediante `https://status.cloud.google.com/incidents.json` (incidentes públicos generales; no eventos personalizados por proyecto).
- Slack mediante `https://slack-status.com/api/v2.0.0/current`.
- Statuspage v2: Exabeam, Tenable, Cloudflare, GitHub, Atlassian Jira, DigitalOcean y GitLab.com, Datadog US1.

## Fuentes manuales
Se mantienen Microsoft Exchange Online, Teams, SharePoint, OneDrive, Azure, Power Platform, Entra ID, Defender XDR, Wazuh, Gurucul, Fortinet/FortiGuard, WatchGuard, CrowdStrike, Okta, Cisco Umbrella, Cisco Cloud, Zoom y AWS. Las fuentes manuales nunca se muestran como operativas: requieren que el analista abra el portal y confirme visualmente.

## Despliegue en Render
Se mantiene compatible con el servicio Web existente:
- Runtime: Python 3
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/status`
- No requiere variables de entorno adicionales.

Para actualizar el servicio actual: subir el contenido de esta carpeta al mismo repositorio GitHub `soc-service-status-monitor`, conservar la rama `main`, realizar commit y en Render ejecutar Manual Deploy → Deploy latest commit. No crear un segundo servicio.

## API
- `GET /api/status`
- `GET /api/events`
- `POST /api/poll`
- `GET /api/config`
- `GET /api/checklist`
- `POST /api/checklist`

## Limitaciones y seguridad
- El estado público del fabricante no garantiza la salud del tenant/instancia de cada cliente ni prueba conectividad desde la red del cliente.
- El estado de Google Cloud proviene del feed público de incidentes amplios; los incidentes personalizados de proyectos requieren Personalized Service Health.
- En Render Free el servicio puede dormir por inactividad y el filesystem local no es almacenamiento persistente garantizado. SQLite puede perder registros al reiniciar, suspender o redeplegar. El checklist v1.4 es piloto, no evidencia formal de auditoría.
- La aplicación no tiene autenticación: cualquier persona con la URL puede ver los registros y enviar entradas al checklist. No ingresar información sensible, datos de clientes, tickets confidenciales ni detalles internos. Antes de uso formal, añadir autenticación/autorización y almacenamiento persistente.
- El recolector consulta únicamente cuando un analista pulsa «Actualizar ahora».


## Corrección v1.4.1 (hotfix)
Se corrigieron dos defectos de la v1.4:
1. El frontend llamaba a `POST /api/poll`, pero la ruta no estaba implementada en el backend. El botón «Actualizar ahora» recibía HTTP 404 y no ejecutaba las consultas.
2. `GET /api/status` devolvía solo filas existentes en SQLite, por lo que el catálogo aparecía vacío antes de la primera consulta. Ahora combina `config.json` con los resultados guardados y muestra todas las plataformas habilitadas desde el primer acceso.

Tras reemplazar los archivos y desplegar el commit, prueba:
- `GET /api/status`: debe devolver todas las plataformas habilitadas.
- `POST /api/poll`: debe responder JSON con `checked`, `success`, `errors`, `manual` y resultados por plataforma.


## Mejora v1.4.2 — tarjetas KPI interactivas
Las ocho tarjetas superiores son ahora filtros interactivos:
- Operativos, avisos, degradados, indisponibles, mantenimientos, consulta manual y sin información filtran por estado.
- Datos antiguos (+60 min) filtra por antigüedad.
- Al seleccionar una tarjeta se limpia el texto de búsqueda, se conserva la categoría elegida, se actualiza el filtro y la lista se desplaza a las plataformas.
- Al volver a pulsar la tarjeta activa se quita ese filtro.
- Se actualiza `aria-pressed` y se añade foco visible para teclado.


## Versión 1.5.0 — ampliación de fuentes automáticas

### Nuevas fuentes automáticas
- WatchGuard: consulta del resumen público Statuspage; fallback al feed Atom oficial `https://status.watchguard.com/history.atom`.
- FortiGuard: hub público Statuspage `https://status.fortiguard.net`.
- Zoom: API pública Statuspage `https://www.zoomstatus.com`.
- Cisco Webex: API pública Statuspage `https://status.webex.com`.
- Microsoft Azure: endpoint público JSON `https://status.cloud.microsoft/api/posts/azure`.
- Microsoft Power Platform: endpoint público JSON `https://status.cloud.microsoft/api/posts/ppac`.
- Microsoft 365 Admin Center: avisos públicos JSON `https://status.cloud.microsoft/api/posts/mac`.

### Fuentes que permanecen manuales por una razón técnica
- Exchange Online, Teams, SharePoint, OneDrive, Entra ID y Defender XDR: el estado detallado para clientes empresariales es tenant-specific y se consulta en el Microsoft 365 Admin Center / Service Health autenticado. Las fuentes públicas añadidas no deben confundirse con el estado detallado del tenant.
- AWS: el panel público muestra eventos generales, mientras que el estado específico de cuenta requiere AWS Health autenticado; feeds públicos pueden ser por servicio/región y no representan un resumen global completo.
- Okta: el portal público presenta datos, pero no se integró scraping de una estructura no documentada como si fuera API estable.
- Cisco Umbrella y Cisco Cloud Status: se mantienen manuales hasta confirmar un endpoint/feed público estable y soportado para las vistas actuales.
- CrowdStrike: el enlace configurado requiere acceso al portal de soporte; no se identificó una fuente pública anónima estable.
- Wazuh y Gurucul: no se identificó un feed público oficial de estado verificable.

### Consideraciones
Las consultas muestran el estado público del proveedor, no la disponibilidad de la instancia específica del cliente. Un fallo de conexión a la fuente se registra como `unknown`/sin información, nunca como indisponibilidad del proveedor.
No se ejecutan consultas en segundo plano; el analista sigue iniciando cada ciclo con «Actualizar ahora».
Microsoft `api/posts/*` es una fuente pública global de avisos y no reemplaza el Microsoft Graph Service Communications API, que requiere autenticación y permisos.


## Inventario de automatización v1.5.0
Total configurado: 36 entradas; automáticas: 23; revisión manual: 13.
Automáticas: Google Workspace (6), Google Cloud (1), Slack (1), Statuspage (11), Microsoft public posts (3) y WatchGuard (1).
Manual: Microsoft Exchange/Teams/SharePoint/OneDrive/Entra/Defender, Wazuh, Gurucul, CrowdStrike, Okta, Cisco Umbrella, AWS y Cisco Cloud Status.
El criterio de inclusión es disponer de API/feed público legible sin credenciales y con semántica suficiente para evitar inferir falsos estados. No se usa scraping HTML frágil para sustituir APIs no documentadas.


## Versión 1.6.0 — detalle de plataforma y captura del portal

- Las tarjetas de plataforma abren una ventana de detalle accesible con ratón o teclado.
- Endpoint `GET /api/services/{service_id}/detail` obtiene información estructurada en vivo cuando el proveedor ofrece una fuente pública compatible.
- Statuspage: componentes, incidentes, actualizaciones y mantenimientos.
- Microsoft public posts, Google Workspace, Google Cloud y Slack: detalle de avisos/incidentes según la fuente pública disponible.
- Fuentes manuales: se explica por qué requieren validación en el portal oficial.
- Al final del detalle se muestra una captura del portal mediante WordPress.com mShots (`s.wordpress.com/mshots/v1`). Es un servicio externo sin API key; su disponibilidad y tiempo de actualización dependen de ese proveedor y del portal capturado. Si falla, se mantiene el enlace oficial para abrir el sitio.
- La captura puede tener caché y no se garantiza que sea una reproducción en tiempo real exacta. La información estructurada de la API/feed es la fuente primaria para el estado.
- No se requiere una nueva variable de entorno ni un nuevo servicio Render.


## Versión 1.6.1 — depuración del catálogo

Se retiraron del catálogo las siguientes plataformas, según solicitud:
- DigitalOcean
- Wazuh
- Cisco Webex
- Datadog US1

El catálogo queda con 32 plataformas. No se modificaron los conectores ni la lógica de las demás fuentes. No requiere variables de entorno nuevas ni cambios en la configuración del servicio Render.


## Hotfix v1.6.2 — consistencia de estados Statuspage

Se corrigió la divergencia entre las tarjetas y la ventana de detalle:
- Antes, la tarjeta aplicaba el peor estado entre el resumen global, componentes e incidentes activos.
- La ventana de detalle solo mostraba el indicador global (`status.indicator`), por lo que podía decir "All Systems Operational" aunque hubiera un incidente minor/monitoring abierto.
- Ahora ambas vistas utilizan `statuspage_effective_status()`, con la misma prioridad: indisponibilidad > degradación > mantenimiento > aviso > operativo.
- Incidentes `resolved`, `postmortem` o `closed` no se consideran activos.
- La ventana de detalle conserva y muestra el estado global original y explica cuándo el estado efectivo cambia por un componente o incidente activo.

La lógica no afirma que toda la plataforma esté caída por un incidente regional menor: clasifica el estado efectivo como degradado y muestra el nombre/impacto del incidente para contexto.
