# SOC Phishing Reporter Assistant — Chrome / Edge

## Actualización 1.0.1
Para Google Safe Browsing, la extensión ahora intenta:
1. Elegir «Esta página no es segura» en Tipo de informe.
2. Elegir «Ingeniería social» en Tipo de amenaza.
3. Elegir «Phishing bancario o financiero» en Categoría de amenaza, si Google la ofrece para esa selección.
4. Pegar la descripción del reporte SOC en «Información adicional».
5. Completar la URL denunciada.

La selección de categoría depende de que Google habilite y muestre esa opción después de elegir el tipo de amenaza. Si el formulario cambia, el analista deberá completar manualmente el campo pendiente.

## Instalación / actualización
1. Descomprime el ZIP.
2. Abre `chrome://extensions` (Chrome) o `edge://extensions` (Edge).
3. En la extensión existente, pulsa Recargar; si no actualiza los archivos locales, elimina la versión anterior y vuelve a cargar la carpeta descomprimida.
4. Recarga la pestaña de Google Safe Browsing.

La extensión no pulsa Enviar, no resuelve CAPTCHA y no evita controles del proveedor. Revisa todos los campos antes de enviar.
