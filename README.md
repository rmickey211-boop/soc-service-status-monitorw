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
