# SOC Phishing Reporter Assistant — Chrome / Edge

Extensión Manifest V3 para complementar el módulo Phishing URL Reporter del SOC Service Status Monitor. No usa APIs de proveedores ni transmite datos a un backend propio. Los datos se guardan temporalmente en el almacenamiento local de la extensión.

## Instalación de prueba
1. Extrae el ZIP en una carpeta local.
2. Abre `chrome://extensions` en Chrome o `edge://extensions` en Edge.
3. Activa **Modo desarrollador**.
4. Selecciona **Cargar descomprimida** y elige esta carpeta `browser-extension`.
5. Abre o recarga `https://soc-service-status-monitor.onrender.com/`.
6. Prepara un reporte y pulsa el botón para abrir el portal.

## Alcance y seguridad
- Intenta rellenar campos visibles y reconocibles en VirusTotal, FortiGuard, Google Safe Browsing, Netcraft, ESET, Cloudflare, URLAbuse y WatchGuard.
- La detección de campos es heurística; depende del HTML, idioma, sesión y cambios del portal. Un proveedor puede cambiar su formulario sin aviso.
- **Nunca pulsa botones de enviar**, no resuelve CAPTCHA, no inicia sesión, no evita controles anti-bot y no confirma reportes.
- Categorías sensibles, identidad pública del reportante y opciones ambiguas quedan para selección manual.
- VirusTotal es análisis de reputación, no reporte directo a todos sus motores. FortiGuard y WatchGuard pueden ser flujos de revisión de categoría.
- Los portales pueden compartir la información recibida conforme a sus propias políticas. Evita incluir tokens, credenciales o datos personales.
- La extensión solicita acceso a los dominios indicados en `manifest.json` y al dominio de Render para recibir el paquete de reporte.

## Limitaciones conocidas
Esta primera versión es una automatización asistida de mejor esfuerzo. No se ha validado contra cada formulario autenticado ni con todas las variantes regionales. El analista debe comprobar que cada campo quedó correcto antes de continuar.
