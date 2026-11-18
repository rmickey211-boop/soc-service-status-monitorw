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


# SOC Global Threat Intelligence — v1.8.0 · Parte 1

## Alcance de esta entrega

Se agrega un panel independiente de noticias y publicaciones públicas de ciberseguridad. El monitor de disponibilidad, el detalle de plataformas, el checklist y el historial existentes se mantienen.

### Fuentes integradas

| Fuente | Feed público | Enfoque |
|---|---|---|
| The Record | `https://therecord.media/feed/` | Ciberataques, ransomware, espionaje y filtraciones |
| BleepingComputer | `https://www.bleepingcomputer.com/feed/` | Malware, brechas, ransomware y vulnerabilidades |
| CISA | `https://www.cisa.gov/rss.xml` | Alertas y avisos oficiales |
| Cisco Talos | `https://blog.talosintelligence.com/rss/` | Malware y campañas de amenazas |
| Google Threat Intelligence | `https://feeds.feedburner.com/threatintelligence/pvexyqv7v0v` | Actores, campañas y análisis de amenazas |

Los feeds se consultan solo al pulsar «Actualizar inteligencia». Los resultados se guardan en SQLite y sobreviven a recargas mientras el almacenamiento de Render siga disponible. Se conservan hasta 30 días en la base local; la consulta de pantalla permite filtrar las últimas 24 horas o los últimos 7 días.

### Categorías

Cada publicación recibe una clasificación temática automática:
- Noticias mundiales (vista global que incluye todas las publicaciones).
- Ransomware.
- Espionaje.
- Filtraciones.
- DDoS.
- Malware.

Una publicación puede pertenecer a más de una categoría. La clasificación se basa en palabras clave del título y resumen RSS; es orientativa y no sustituye el análisis de un investigador.

### Caché y consulta manual

- `GET /api/threat-intel/news?period=24h`
- `GET /api/threat-intel/news?period=7d`
- `POST /api/threat-intel/news/refresh`

La pantalla carga la caché al abrirse y no ejecuta llamadas externas automáticamente. El botón de actualización consulta las cinco fuentes en paralelo y actualiza el almacén local. Si una fuente falla, las demás siguen procesándose y se muestra el estado individual de cada fuente.

### Privacidad y costos

- Solo se consultan feeds de acceso público.
- No se capturan ni transmiten datos de la empresa, clientes o plataformas internas.
- No se requieren API Keys, credenciales internas ni nuevos servicios.
- Se utilizan las dependencias estándar ya presentes (FastAPI, requests, SQLite y ElementTree).
- El diseño no agrega un servicio de pago. Render Free mantiene sus limitaciones de suspensión por inactividad y almacenamiento efímero.

### Presentación y copyright

El portal muestra titulares, extractos limitados a 420 caracteres, fuente, fecha y enlace al artículo original. No republica artículos completos.

### Límites de esta parte

Esta entrega aún no incluye:
- Mapa geográfico de víctimas.
- Feed estructurado de reclamos ransomware.
- CISA KEV, EPSS o NVD como módulo CVE.

Esas funciones se incorporarán en las siguientes partes de la versión 1.8.


## Hotfix v1.8.0 · Parte 1.1 — actualización de inteligencia

Se corrige la interacción del botón «Actualizar inteligencia» y la carga de recursos estáticos:
- Se agregan identificadores de versión (`?v=1.8.0-part1.1`) a CSS y JavaScript para evitar que el navegador reutilice archivos antiguos de la versión anterior.
- El botón queda declarado explícitamente como `type="button"`.
- Durante la consulta se muestra un estado visible y el botón queda temporalmente deshabilitado.
- Si el servidor devuelve un error HTTP, una respuesta no JSON o no se puede recuperar la caché, el panel muestra el motivo en pantalla; ya no depende únicamente de una notificación temporal.
- El total de fuentes se calcula a partir de la respuesta y no queda fijado visualmente a cinco.

La ruta `POST /api/threat-intel/news/refresh` se mantiene. No se incorporan servicios, credenciales, API Keys ni costos nuevos.


# SOC Global Threat Intelligence — v1.8.0 · Parte 2

## Alcance de esta entrega

Se incorpora un tracker de publicaciones relacionadas con ransomware y un mapa de países asociados a esas publicaciones. El panel original de estado de plataformas, el checklist MDR y las noticias de la Parte 1 se conservan.

### Fuente integrada

| Fuente | Endpoint público | Datos utilizados |
|---|---|---|
| RansomLook | `https://www.ransomlook.io/api/posts?days=7` | Nombre publicado, grupo atribuido, fecha de observación y descripción/contexto |

La documentación pública de RansomLook muestra el endpoint de publicaciones recientes y ejemplos de los campos `post_title`, `group_name`, `discovered` y `description`. No requiere una API key para el feed público de recientes. Se enlaza la ficha de grupo o página pública de RansomLook; no se enlazan directamente sitios de filtración.

### Períodos y actualización

- La pantalla permite filtrar publicaciones de las últimas 24 horas o los últimos 7 días.
- La consulta se inicia manualmente con «Actualizar ransomware».
- Los resultados se conservan en SQLite local y se muestran desde caché al volver a abrir la página.
- Se aplica un intervalo mínimo de 15 minutos entre consultas para evitar llamadas repetidas al servicio externo. Si se vuelve a pulsar antes, se reutiliza la caché.
- Se conservan hasta 30 días de metadatos en la base local.
- En caso de error de la fuente, la caché anterior no se borra y el estado de la consulta se muestra en pantalla.

### Mapa y atribución geográfica

RansomLook publica descripciones de contexto que pueden incluir país o gentilicio de la organización. Como los registros no siempre incluyen un campo de país estructurado, el sistema busca menciones explícitas en la descripción del registro (no en el nombre de la organización) y las compara con un catálogo local de países y coordenadas aproximadas.

- Solo se representa un país cuando el texto coincide con una única ubicación reconocible.
- Si la descripción no contiene país, o menciona varios países sin que sea posible resolver uno de forma segura, el registro queda como «Sin asignar».
- No se infiere el país a partir del nombre del grupo, del dominio de la víctima ni de la ubicación del atacante.
- Los marcadores representan publicaciones asociadas a un país, no ubicaciones precisas ni límites territoriales.
- El mapa utiliza Leaflet y teselas de OpenStreetMap con atribución visible. Requiere conexión a internet para cargar el mapa base.

### Interpretación y limitaciones

- Cada registro es una publicación/afirmación observada por RansomLook; no demuestra por sí sola que la intrusión, exfiltración o afectación sean reales.
- `discovered` representa la fecha/hora en que RansomLook observó la publicación; no es necesariamente la fecha del ataque.
- La clasificación geográfica depende del texto descriptivo y puede quedar incompleta. No reemplaza validación con la organización afectada, autoridad competente o fuentes primarias.
- No se descargan ni almacenan archivos filtrados, muestras de malware, credenciales ni datos personales publicados en sitios criminales.

### API interna del módulo

- `GET /api/threat-intel/ransomware?period=24h`
- `GET /api/threat-intel/ransomware?period=7d`
- `POST /api/threat-intel/ransomware/refresh`

### Privacidad y costos

- Solo se consulta el endpoint público de RansomLook.
- No se recopila ni transmite información corporativa, de clientes, tickets internos, credenciales o APIs privadas.
- No se agregan variables de entorno, API keys, servicios externos de pago ni procesos automáticos en segundo plano.
- La consulta es manual y el caché utiliza SQLite, con las mismas limitaciones de almacenamiento efímero de Render Free descritas en las versiones anteriores.
- El catálogo de países y coordenadas es un archivo JSON local; no añade dependencias Python.

### Atribución

Fuente de los registros: [RansomLook](https://www.ransomlook.io/recent). La documentación de RansomLook indica licencia de API CC BY 4.0. El mapa base utiliza [OpenStreetMap](https://www.openstreetmap.org/copyright), cuyos colaboradores reciben atribución en la propia vista.


## v1.8.0 Parte 3 — Vulnerability Intelligence

Añade una sección de inteligencia pública de vulnerabilidades con tres fuentes:
- **CISA KEV**: catálogo oficial de vulnerabilidades con explotación conocida.
- **NVD CVE API 2.0**: vulnerabilidades publicadas en los últimos 30 días y metadatos CVSS cuando están disponibles.
- **FIRST EPSS**: enriquecimiento opcional de un subconjunto priorizado de CVE con probabilidad estimada de explotación en los próximos 30 días.

La actualización es manual. Los resultados se guardan en SQLite local y se pueden filtrar por 7 días, 30 días o todos los registros almacenados, además de buscar por CVE, proveedor o producto. EPSS es una estimación, no evidencia de explotación; KEV sí representa inclusión en el catálogo de explotación conocida. No se correlaciona con inventarios internos.

Fuentes oficiales:
- https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- https://nvd.nist.gov/developers/vulnerabilities
- https://www.first.org/epss/
