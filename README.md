# SOC Service Status Monitor — v1.8.1.1 (corrección de navegación)

Panel web de consulta del estado de plataformas y de inteligencia pública de ciberamenazas. Esta entrega corrige la navegación de la interfaz modular.

## Módulos incluidos

1. **Estado de plataformas:** catálogo de servicios, consulta manual, detalle, enlaces oficiales, componentes, incidentes y mantenimientos cuando la fuente lo publica.
2. **SOC Global Threat Intelligence:** noticias públicas de ciberseguridad con filtros temporales y temáticos.
3. **Ransomware Tracker:** publicaciones públicas de RansomLook, con filtros por período/grupo y mapa de países cuando el país puede identificarse explícitamente.
4. **Vulnerability Intelligence:** CISA KEV, CVE de NVD y enriquecimiento EPSS de FIRST cuando está disponible.


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
- Health check: `/api/status`
- No requiere API keys ni variables de entorno adicionales para las fuentes públicas incluidas.

Para actualizar: reemplazar el contenido del repositorio GitHub existente con el contenido de esta carpeta, conservar `.git` si se utiliza GitHub Desktop, realizar commit/push y ejecutar **Manual Deploy → Deploy latest commit** en el servicio Render actual. No crear un servicio nuevo.

## Rutas principales

- `GET /api/status`
- `POST /api/poll`
- `GET /api/events`
- `GET /api/threat-intel/news` y `POST /api/threat-intel/news/refresh`
- `GET /api/threat-intel/ransomware` y `POST /api/threat-intel/ransomware/refresh`
- `GET /api/threat-intel/vulnerabilities` y `POST /api/threat-intel/vulnerabilities/refresh`

## Seguridad y limitaciones operativas

- La aplicación no tiene autenticación. Cualquier persona con acceso a la URL puede consultar el panel y enviar entradas al checklist. No introducir datos de clientes, tickets, IOC internos, credenciales ni información confidencial.
- Render Free puede suspender el servicio por inactividad. El almacenamiento local SQLite no es persistente garantizado y puede perderse en reinicios o redeploys. No usar el checklist piloto como evidencia formal de auditoría.
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
