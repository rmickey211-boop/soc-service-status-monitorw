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
