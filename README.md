# SOC Service Status Monitor — v1.9.4 (Phishing URL Reporter · asistente por vendor)

Panel web de consulta del estado de plataformas y de inteligencia pública de ciberamenazas. Esta entrega corrige la navegación de la interfaz modular.

## Módulos incluidos

1. **Estado de plataformas:** catálogo de servicios, consulta manual, detalle, enlaces oficiales, componentes, incidentes y mantenimientos cuando la fuente lo publica.
2. **SOC Global Threat Intelligence:** noticias públicas de ciberseguridad con filtros temporales y temáticos.
3. **Ransomware Tracker:** publicaciones públicas de RansomLook, con filtros por período/grupo y mapa de países cuando el país puede identificarse explícitamente.
4. **Vulnerability Intelligence:** CISA KEV, CVE de NVD y enriquecimiento EPSS de FIRST cuando está disponible.
5. **Phishing URL Reporter:** preparación de reportes para VirusTotal, FortiGuard, Google Safe Browsing, Netcraft, ESET, Cloudflare, URLAbuse y WatchGuard.


## Fuentes y criterios

- El estado de una página pública no demuestra la salud de un tenant, red o servicio específico del cliente.
- Las noticias son reportes de fuentes externas, no incidentes confirmados.
- Una publicación en un sitio de ransomware representa una reclamación del actor; no equivale a una brecha verificada. El país se asigna solo si hay una mención reconocible y no ambigua.
- CISA KEV identifica vulnerabilidades con explotación conocida; CVSS representa severidad técnica; EPSS estima probabilidad de explotación. No son métricas intercambiables.
- Los datos pueden variar según disponibilidad, límites y cambios de las API externas. La actualización se inicia manualmente desde los botones de cada módulo.

## Despliegue en el servicio Render existente

- Runtime: Python 3
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/health` (consulta SQLite y metadatos guardados; no consulta proveedores externos)
- No requiere API keys ni variables de entorno adicionales para las fuentes públicas incluidas.

La aplicación desplegada utiliza `app/main.py` y los recursos `app/static/index.html`, `app/static/app.js` y `app/static/style.css`. Los archivos duplicados de la raíz se conservan por compatibilidad histórica, pero no son los recursos servidos por el comando Render indicado.

Para actualizar: reemplazar el contenido del repositorio GitHub existente con el contenido de esta carpeta, conservar `.git` si se utiliza GitHub Desktop, realizar commit/push y ejecutar **Manual Deploy → Deploy latest commit** en el servicio Render actual. No crear un servicio nuevo.


## v1.9.2 — Phishing URL Reporter · Etapa 2

- Historial persistente en `localStorage` del navegador de cada analista. Los datos no se envían al backend ni se sincronizan entre equipos o perfiles de navegador.
- Registro por vendor y lote con fecha, URL(s), analista, marca suplantada, categoría, referencia, descripción y estado de gestión.
- Detección histórica de duplicados por combinación vendor + URL. Las coincidencias se omiten por defecto; el analista puede permitir explícitamente repetirlas cuando exista nueva evidencia o una justificación.
- Estados de seguimiento: preparado/pendiente, portal abierto, confirmado por analista y descartado/cancelado. La confirmación continúa siendo manual y no demuestra que el vendor haya aceptado el reporte.
- Exportación completa del historial a JSON o CSV e importación de respaldos en ambos formatos. La importación evita agregar registros que ya tengan el mismo identificador.
- Filtros de historial por texto, vendor y estado; acciones para copiar nuevamente la plantilla, abrir el portal o eliminar un registro.
- Plantillas de texto diferenciadas para VirusTotal, FortiGuard, Google Safe Browsing, Netcraft, ESET, Cloudflare, URLAbuse y WatchGuard. Se distingue análisis, reporte de abuso y solicitud de recategorización.
- No se agregan APIs de vendors, extensiones, dependencias Python, endpoints, tablas SQLite ni envío automatizado. No se automatiza autenticación, CAPTCHA ni el envío externo.
- El almacenamiento local no es un repositorio central: cada navegador y perfil conserva su propio historial. Se recomienda exportar respaldos periódicos y evitar URLs con tokens, credenciales, datos personales o secretos. El sistema limita el tamaño del historial local para respetar las cuotas habituales del navegador.

### Alcance heredado de v1.9.1 — Etapa 1
- Nuevo módulo web integrado en la navegación lateral, sin modificar los cuatro módulos SOC existentes.
- Preparación de lotes de hasta 20 URLs, una por línea, con validación HTTP/HTTPS, rechazo de credenciales embebidas y eliminación de duplicados normalizados dentro del lote.
- Campos para marca suplantada, analista, categoría, referencia interna y descripción/evidencia.
- Ocho portales oficiales con instrucciones que distinguen análisis de reputación, reportes de phishing y solicitudes de recategorización.
- Copia de los datos preparados por vendor o del resumen del lote; apertura individual de cada portal.
- VirusTotal se presenta como análisis de URL, no como reporte directo a todos sus motores. FortiGuard y WatchGuard se identifican como consulta/revisión de categoría.

### Portales oficiales incluidos
- VirusTotal: https://www.virustotal.com/gui/home/url
- FortiGuard Web Filter: https://www.fortiguard.com/webfilter
- Google Safe Browsing — phishing report: https://safebrowsing.google.com/safebrowsing/report_phish/
- Netcraft: https://report.netcraft.com/report
- ESET (español): https://phishing.eset.com/es-cl/report
- Cloudflare Abuse: https://abuse.cloudflare.com/
- URLAbuse: https://urlabuse.com/report
- WatchGuard URL Categorization: https://www.watchguard.com/securityportal/UrlCategorization.aspx

## Rutas principales

- `GET /api/status`
- `POST /api/poll`
- `GET /api/events`
- `GET /api/threat-intel/news` y `POST /api/threat-intel/news/refresh`
- `GET /api/threat-intel/ransomware` y `POST /api/threat-intel/ransomware/refresh`
- `GET /api/threat-intel/vulnerabilities` y `POST /api/threat-intel/vulnerabilities/refresh`

## Seguridad y limitaciones operativas

- La aplicación no tiene autenticación. Cualquier persona con acceso a la URL puede consultar el panel y enviar entradas al checklist. No introducir datos de clientes, tickets, IOC internos, credenciales ni información confidencial.
- Render Free puede suspender el servicio por inactividad. El almacenamiento SQLite local del backend no es persistente garantizado y puede perderse en reinicios o redeploys. El historial de Phishing URL Reporter es independiente: reside en el almacenamiento local del navegador del analista y tampoco sustituye un repositorio central o una evidencia formal de auditoría.
- El mapa utiliza Leaflet y cartografía de OpenStreetMap; requiere conexión a Internet.
- Las pruebas automatizadas validan lógica y respuestas simuladas; no garantizan disponibilidad en vivo de servicios externos.

## Pruebas

Ejecutar desde la raíz del proyecto:

```bash
python -m pytest -q
```


## v1.8.1 — mejoras de experiencia de usuario
- Pantalla inicial con cuatro tarjetas de navegación: estado de plataformas, noticias/amenazas, ransomware y vulnerabilidades.
- Se eliminó el Checklist MDR y su historial de la interfaz.
- Se retiró la captura automática de portales oficiales; se conserva el enlace al portal original.
- Se acotó el detalle de plataformas: hasta 6 componentes, 3 incidentes y 3 mantenimientos, con textos largos limitados.
- El mapa se redimensiona al abrir el módulo y muestra un mensaje explicativo cuando no hay países identificables. La ausencia de marcadores no se reemplaza con ubicaciones inventadas.


## v1.8.1.1 — corrección crítica de navegación
- Se retiraron los controladores JavaScript que seguían intentando acceder a los controles del Checklist MDR eliminados de la página. Ese acceso nulo detenía la ejecución del archivo `app.js` antes de registrar los clics de las tarjetas.
- Se corrigió una referencia antigua a la variable `kr` que había quedado en la carga principal.
- Se actualizó el identificador de versión de JS/CSS para invalidar la caché del navegador.
- Se agregaron pruebas de regresión para verificar que las cuatro tarjetas tengan su vista correspondiente, que los IDs usados por JavaScript existan y que los elementos eliminados no vuelvan a enlazarse.


## Ficha detallada de vulnerabilidades — v1.8.2
- Cada fila CVE abre una ficha dentro de Vulnerability Intelligence.
- Incluye descripción, CVSS y vector, EPSS y percentil, estado CISA KEV, uso conocido en ransomware, fechas, CWE, configuraciones CPE y referencias.
- Muestra acciones y fechas de CISA KEV, además de enlaces de advisories/patches del fabricante cuando NVD los clasifica así.
- En registros KEV antiguos, realiza una consulta puntual a NVD al abrir la ficha si la información técnica no está en caché; EPSS también se consulta individualmente si falta.
- Las medidas compensatorias generales están marcadas como orientativas; no se muestran como workaround específico confirmado.
- La columna `details_json` se incorpora mediante migración SQLite, sin borrar filas existentes.


## v1.8.3 — fechas CVE y fuentes ransomware ampliadas
- La tabla de vulnerabilidades separa fecha de publicación NVD y fecha de incorporación a CISA KEV; la ficha técnica conserva también fecha de última modificación.
- Se incorpora el RSS público de Ransomware.live sin API key, junto con RansomLook.
- Ransomware.live se utiliza para indicadores agregados de países y grupos, no para redistribuir públicamente nombres individuales de víctimas; su feed se atribuye y enlaza.
- Las publicaciones individuales de la tabla se identifican como RansomLook.
- Las reclamaciones de grupos ransomware se presentan como no verificadas.
- La fuente RSS se consulta con caché e intervalo mínimo de 15 minutos.

- Nota geográfica: el RSS no garantiza un campo de país estructurado. Solo se asigna país cuando aparece una mención explícita y no ambigua en el resumen disponible; si el feed no la incluye, el registro queda sin país. No se infiere por dominio, nombre de empresa ni ubicación de grupo.
- Condiciones de reutilización: Ransomware.live se limita a indicadores agregados en la vista pública y siempre se atribuye/enlaza; revisar sus términos vigentes antes de cualquier uso comercial o redistribución.


## v1.8.4 — desglose visible de fuentes ransomware
- Se sube el estado de RansomLook y Ransomware.live al inicio del módulo.
- Se distinguen publicaciones procesadas por fuente de filas individuales visibles en la tabla.
- La tabla indica explícitamente que sus filas individuales visibles corresponden a RansomLook.
- Países y grupos muestran el aporte de RansomLook y Ransomware.live por separado.
- El mapa usa colores por fuente (RansomLook, Ransomware.live o ambas) y el popup presenta el desglose.
- Los totales se denominan observaciones procesadas; no implican víctimas únicas ni incidentes confirmados.


## v1.8.5 — acceso directo a Ransomware.live
- Se agrega junto al encabezado de publicaciones individuales un enlace visible y directo al portal oficial de Ransomware.live.
- Se etiqueta expresamente la tabla como publicaciones individuales de RansomLook.
- Se explica que Ransomware.live aporta indicadores agregados visibles en las tarjetas superiores; sus nombres de víctimas no se redistribuyen en la tabla pública.
- Se elimina el panel de estado duplicado del final de la tabla; el estado principal de fuentes permanece al inicio del módulo.


## v1.8.6 — nueva fuente Cyber Security News
- Se incorpora Cyber Security News mediante RSS público: https://cybersecuritynews.com/feed/
- El catálogo de inteligencia pasa de cinco a seis fuentes.
- Los artículos quedan atribuidos a Cyber Security News y enlazados al sitio original.
- Se mantienen los filtros temáticos, la caché y la actualización manual.
- Solo se almacenan metadatos, titulares y extractos breves; no se replica el artículo completo.


## v1.8.7 — subcategoría Vulnerabilidades en noticias
- Se agrega el filtro temático "Vulnerabilidades" dentro de Ataques y amenazas publicados.
- La clasificación incluye referencias CVE, zero-day/zero-click, fallos de seguridad, RCE, escalada de privilegios, bypass de autenticación, inyección y explotación reportada.
- Una noticia puede conservar otras etiquetas simultáneamente (por ejemplo ransomware + vulnerabilidades).
- Este filtro es editorial/noticioso; el análisis técnico de CVE, CVSS, KEV y EPSS permanece en el módulo Vulnerability Intelligence.


## v1.8.8 — filtro de noticias por fuente
- Se incorpora un selector "Filtrar por fuente" junto al selector de período en Ataques y amenazas publicados.
- Las fuentes se generan a partir del estado de las fuentes y de las publicaciones disponibles, mostrando cantidad de noticias y estado sin respuesta.
- El filtro por fuente se combina con el período y la subcategoría elegida, sin reemplazar los filtros existentes.
- Se conserva la opción "Todas las fuentes".
- Se incluye en la interfaz la subcategoría "Vulnerabilidades" junto con su etiqueta visual.


## v1.8.9 — fuentes especializadas y CSIRT Chile
Se agregan tres fuentes RSS públicas al módulo Ataques y amenazas publicados:
- SecurityWeek · Vulnerabilities: https://www.securityweek.com/category/vulnerabilities/feed/
- The Hacker News: https://thehackernews.com/feeds/posts/default?alt=rss
- CSIRT Chile: https://csirt.gob.cl/rss/alertas

El módulo pasa de seis a nueve fuentes. El filtro por fuente se alimenta automáticamente con los nombres devueltos por el backend. La clasificación incorpora términos de ciberseguridad en español (vulnerabilidades, parches, ejecución remota de código, phishing, malware, filtración de datos y otros) para mejorar la categorización de alertas CSIRT Chile.
Cada proveedor se consulta de forma independiente; un fallo de una fuente no debe impedir procesar las demás. Los titulares y extractos siguen enlazando al artículo o alerta original.


## v1.8.10 — NVD Last Modified y ordenamiento
- Se agrega la columna NVD LAST MODIFIED a la tabla principal, además de NVD PUBLISHED DATE y ALTA CISA KEV.
- El orden predeterminado pasa a ser última modificación NVD más reciente primero.
- El selector permite ordenar por última modificación, fecha de publicación, EPSS, CVSS o prioridad CISA KEV.
- El orden se aplica en SQL antes del límite de 500 filas, evitando que se pierdan CVE recientes por el orden anterior.
- La ficha de detalle mantiene las fechas de publicación y modificación.


## v1.8.10 — NVD Last Modified y ordenamiento
- Se agrega la columna NVD LAST MODIFIED a la tabla principal, además de NVD PUBLISHED DATE y ALTA CISA KEV.
- El orden predeterminado pasa a ser última modificación NVD más reciente primero.
- El selector permite ordenar por última modificación, fecha de publicación, EPSS, CVSS o prioridad CISA KEV.
- El orden se aplica en SQL antes del límite de 500 filas, evitando que se pierdan CVE recientes por el orden anterior.
- La ficha de detalle mantiene las fechas de publicación y modificación.


## v1.8.11 — actualización global de los cuatro módulos
- El botón de la pantalla inicial consulta las cuatro rutas existentes: estado de plataformas, noticias RSS, tracker ransomware y Vulnerability Intelligence.
- Las cuatro solicitudes se ejecutan en paralelo para evitar que el fallo de un módulo bloquee a los demás.
- Al terminar, vuelve a cargar las cuatro vistas y sus contadores desde sus respectivas cachés.
- Se muestra un resumen por módulo con estado completo, parcial o error.
- El tracker ransomware conserva el intervalo mínimo de caché de 15 minutos; una actualización global dentro de ese intervalo puede reutilizar sus datos recientes en lugar de repetir solicitudes.
- Los botones de actualización individuales de cada módulo se mantienen.


## v1.9.0 — Fase 1: Executive Dashboard
- Se incorpora un resumen ejecutivo en la pantalla inicial con KPIs de plataformas, noticias, ransomware y CISA KEV.
- Se agregan visualizaciones de distribución de estados, noticias por categoría, actividad ransomware y severidad de vulnerabilidades.
- Se agrega el estado de actualización de los cuatro módulos y sus últimas fechas de consulta disponibles.
- Nuevo endpoint GET `/api/executive-summary`, que consolida exclusivamente las cachés existentes y no realiza consultas externas.
- Los períodos se identifican explícitamente: noticias 7 días, ransomware 7 días y vulnerabilidades 30 días + KEV.
- Los gráficos reflejan las cachés reales; no se crean series históricas ni eventos ficticios.
- La actualización ejecutiva se refresca al abrir la página, al terminar la actualización global y después de las actualizaciones individuales de cada módulo.


## v1.9.0 — Fase 1.1: navegación lateral
- Se reemplazan las cuatro tarjetas grandes de módulo por un menú lateral persistente.
- El menú ofrece Inicio ejecutivo y acceso directo a Estado de plataformas, Ataques y amenazas, Ransomware tracker y Vulnerability Intelligence.
- En escritorio, el menú puede contraerse a una barra de iconos.
- En móviles, el menú funciona como panel lateral desplegable con fondo oscurecido y cierre mediante selección, botón menú, fondo o tecla Escape.
- Se mantiene el Executive Dashboard como pantalla inicial y se conserva el botón de actualización global.
- La selección del módulo activo se resalta en el menú lateral; ya no es necesario volver a Inicio para cambiar de sección.

- Versión de paquete: `1.9.0-phase1-nav`; las tarjetas grandes se sustituyen por navegación lateral y el panel ejecutivo sigue siendo la vista de inicio.


## v1.9.0 — Fase 2: Inteligencia visual por módulo

### Estado de plataformas
- Distribución por estado actual (operativas, avisos, degradadas, indisponibles, mantenimiento, manual y sin información).
- Barras apiladas por categoría de plataforma.
- Transiciones registradas en los últimos 7 días a partir del historial real de eventos. No se interpreta como disponibilidad continua.

### Ataques y amenazas publicados
- Evolución de publicaciones por fecha publicada: 7 días (diario) o 24 horas (bloques de 4 horas).
- Distribución por categoría temática y fuente, usando los filtros actuales de período, fuente y categoría.
- Los conteos corresponden a las noticias almacenadas en caché, no a un total global de incidentes.

### Ransomware tracker
- Evolución por fecha observada: 7 días (diario) o 24 horas (bloques de 4 horas).
- Desglose de grupos con observaciones por RansomLook y Ransomware.live.
- Se agrega al endpoint de caché un timeline de conteos agregados por fuente y período. No contiene nombres de víctimas ni detalles individuales de publicaciones de Ransomware.live.

### Vulnerability Intelligence
- Distribución de los registros visibles por severidad CVSS.
- Bandas EPSS: <10%, 10–<50%, ≥50% y sin puntaje.
- Proporción de registros visibles incluidos/no incluidos en CISA KEV.
- Las distribuciones reflejan los registros devueltos por el filtro actual y no el universo completo de NVD.

### Implementación
- Visualizaciones construidas con HTML/CSS/JavaScript nativo; no se agrega una dependencia de gráficos externa.
- Los módulos conservan sus tablas, filtros, mapas, fuentes y botones actuales.
- Los gráficos se recalculan al cambiar período, filtros o refrescar el módulo correspondiente.


## v1.9.0 — Fase 2.1: hotfix de ejecución

- Se eliminó una expresión `async` aislada que provocaba `ReferenceError` al cargar `app.js` e interrumpía la ejecución completa del frontend.
- Se incorporó una prueba de regresión para detectar nuevamente este patrón.
- Se actualizó el identificador de caché de los recursos estáticos a `1.9.0-phase2.1` y el pie de página para verificar el despliegue correcto.
- Validación: 68 pruebas aprobadas; compilación Python; sintaxis JavaScript; prueba local de navegador sin errores de ejecución y navegación entre módulos operativa.


## v1.9.0 — Fase 3: análisis interactivo y navegación a registros

- Los gráficos de estado de plataformas permiten filtrar el catálogo por estado y categoría; la tendencia diaria filtra el historial de transiciones.
- Los gráficos de noticias permiten filtrar publicaciones por tema, fuente y fecha; el período de 24 horas mantiene ventanas de cuatro horas y el de 7 días, ventanas diarias.
- El gráfico de grupos ransomware permite saltar al filtro de publicaciones individuales de RansomLook cuando existen filas visibles para el grupo. Si el grupo solo aparece en los agregados de Ransomware.live, se informa que no hay detalle individual público en la tabla.
- Las tendencias ransomware filtran publicaciones individuales por el intervalo UTC del bucket seleccionado; el backend entrega solo los límites del intervalo y los conteos agregados, sin datos de víctimas Ransomware.live.
- Los gráficos CVSS, EPSS y CISA KEV filtran la tabla CVE en el navegador sin repetir la consulta al backend.
- Cada módulo presenta el filtro activo y un control para quitarlo; los controles son botones accesibles por teclado.
- Se mejora la adaptación táctil de gráficos, botones y filtros para móviles.
- No se incorpora ninguna dependencia de gráficos, API de pago ni servicio nuevo.

### Limitaciones de comparación histórica
Las fuentes actuales entregan ventanas activas (24 horas/7 días en noticias y ransomware) y el historial de estados disponible (100 transiciones más recientes). No existe una serie histórica uniforme y persistente para comparar períodos consecutivos sin introducir una nueva estrategia de almacenamiento. Por ello, esta fase habilita filtrado por ventana y detalle de registros, pero no presenta comparaciones históricas simuladas.


## v1.9.0 — Fase 4: diagnóstico operativo y trazabilidad

- Nuevo endpoint `GET /api/health`, sin llamadas externas, que resume conectividad SQLite, fuentes, última consulta, último éxito y frescura de datos por módulo.
- Panel de diagnóstico en Inicio ejecutivo con estado correcto, parcial, error, datos antiguos y pendientes por fuente.
- Historial local de las últimas 100 actualizaciones manuales, con resultados resumidos por módulo.
- Noticias y ransomware separan último intento de última consulta exitosa; un fallo total ya no renueva falsamente la fecha del último éxito y se conserva la caché previa.
- Plataformas guarda `checked_at` y `last_success_at` por separado; un fallo temporal no borra el último éxito conocido y el diagnóstico distingue error reciente de datos antiguos.
- Vulnerability Intelligence mantiene la actualización de CISA KEV aunque NVD esté temporalmente indisponible; la interfaz informa el resultado parcial y conserva el detalle de la fuente fallida. EPSS continúa como enriquecimiento opcional.
- El diagnóstico no consulta proveedores, evita tráfico adicional y no incorpora nuevas dependencias, servicios, API keys ni costos.
- El health check de Render apunta a `/api/health`.

### Limitaciones importantes
- La aplicación sigue usando SQLite local. Render Free utiliza un sistema de archivos efímero: los datos locales pueden perderse al reiniciar, suspenderse o redesplegarse. El historial local es diagnóstico operativo, no una bitácora persistente de auditoría.
- No se agregaron alertas por correo, SMS o push: requieren un canal de entrega y un proceso de ejecución programada que el despliegue actual no tiene.
- El endpoint de salud evalúa la última respuesta guardada, no realiza un sondeo vivo de cada proveedor. Para verificar una fuente se debe ejecutar la actualización manual del módulo.
- Fuentes manuales (por ejemplo portales que requieren login o no exponen un feed público) no se cuentan como fallidas: permanecen identificadas como revisión manual.


## v1.9.3 — Precarga útil del formulario externo

- Se elimina el texto genérico tipo plantilla como flujo principal. El botón de copia ahora genera datos breves y directamente útiles para los campos del vendor.
- Para Google Safe Browsing, el botón de apertura construye un enlace con `hl=es` y `url=<URL codificada>` para intentar precargar el campo URL. Este parámetro `url` se ha utilizado históricamente en integraciones de navegador, pero no forma parte del enlace básico que Google publica actualmente; se debe validar en el formulario real y puede cambiar sin aviso.
- Si el lote contiene varias URLs para Google, la tarjeta permite abrir una por una, ya que el formulario es de una URL por envío. El estado de gestión solo puede confirmarse después de haber abierto cada URL y de que el analista declare que completó todos los envíos.
- Al abrir Google, los detalles adicionales (máximo 800 caracteres) se copian al portapapeles para pegarlos en el campo «Detalles adicionales». El tipo/categoría de amenaza y el botón de envío siguen siendo manuales.
- Los demás vendors conservan enlaces directos y copia de datos; no se inventan parámetros de precarga no documentados.
- Sin APIs de vendors, extensiones ni nuevas dependencias. El navegador no permite que la página SOC manipule directamente los campos internos de otro dominio ni pulse el botón de envío externo.


## v1.9.4 — Asistente de campos por vendor

- Se generaliza la selección de URL individual para VirusTotal, FortiGuard, Google Safe Browsing, ESET, Cloudflare y URLAbuse; Netcraft y WatchGuard admiten preparación de lotes.
- VirusTotal abre su formulario de análisis y copia la URL para pegarla. Es una consulta de reputación, no un reporte directo a cada motor; las URLs enviadas pueden compartirse con partners, por lo que se advierte no enviar tokens ni datos sensibles.
- FortiGuard abre la consulta con `q=<URL>` y prepara una sugerencia de categoría `Security Risk → Phishing`; la solicitud de revisión se inicia desde el resultado mediante `Request a Review`.
- Google mantiene la precarga de URL mediante `url=<URL>`; tipo de amenaza (`Ingeniería social`) y categoría (`Phishing bancario o financiero`) deben seleccionarse manualmente. La información adicional se copia por separado.
- Netcraft prepara el lote en líneas separadas para su opción `Report in bulk`; los detalles adicionales se copian en otro campo. El correo de contacto es opcional y lo completa el analista.
- ESET presenta campos separados para URL, organización suplantada y comentarios, según su formulario de reporte de phishing.
- Cloudflare presenta la categoría `Phishing & Malware` como selección manual, el dominio en cuestión y el enlace específico de phishing. Solo debe utilizarse cuando exista relación verificable con servicios/IPs de Cloudflare.
- URLAbuse presenta URL, marca objetivo, tipo de abuso `Phishing` y una advertencia explícita de que el nombre/alias del reportante se muestra públicamente; el nombre se completa manualmente con un alias autorizado.
- WatchGuard prepara las URLs en líneas separadas con la categoría sugerida `Phishing and Other Frauds`; el portal puede requerir inicio de sesión y reCAPTCHA.
- Al abrir un portal, la página muestra un asistente con botón de copia por campo y copia automáticamente el primer campo útil. Los campos externos que no admiten una precarga pública se completan mediante pegado manual.
- Se mantiene el envío manual; no se utilizan APIs, extensiones, automatización entre dominios ni mecanismos para eludir CAPTCHA o autenticación.
