// Automatización asistida. Nunca pulsa botones de envío ni resuelve CAPTCHA.
(() => {
  const HOST = location.hostname.toLowerCase();
  const VENDOR = HOST.includes("virustotal") ? "virustotal" : HOST.includes("fortiguard") ? "fortiguard" :
    (HOST.includes("google.com") || HOST.includes("safebrowsing.google.com")) ? "google" :
    HOST.includes("netcraft") ? "netcraft" : HOST.includes("eset.com") ? "eset" :
    HOST.includes("cloudflare.com") ? "cloudflare" : HOST.includes("urlabuse") ? "urlabuse" :
    HOST.includes("watchguard") ? "watchguard" : "";
  if (!VENDOR) return;

  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const norm = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/\s+/g, " ").trim();
  const visible = el => !!(el && el.getClientRects().length &&
    getComputedStyle(el).visibility !== "hidden" && getComputedStyle(el).display !== "none");
  const controls = () => [...document.querySelectorAll(
    'input:not([type="hidden"]),textarea,[contenteditable="true"],select,[role="combobox"]'
  )].filter(visible);

  const labelText = el => {
    const bits = [el.getAttribute("aria-label"), el.getAttribute("placeholder"),
      el.getAttribute("name"), el.id, el.getAttribute("autocomplete"),
      el.getAttribute("data-placeholder")];
    if (el.id) {
      const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lab) bits.push(lab.innerText);
    }
    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) labelledBy.split(/\s+/).forEach(id => {
      const node = document.getElementById(id); if (node) bits.push(node.innerText);
    });
    const parent = el.closest("label");
    if (parent) bits.push(parent.innerText);
    const wrapper = el.closest('[class*="field"],[class*="form"],[role="group"]') || el.parentElement;
    if (wrapper) bits.push(wrapper.innerText?.slice(0, 220));
    return norm(bits.filter(Boolean).join(" "));
  };

  function nativeSet(el, value) {
    if (!el || el.disabled || el.readOnly) return false;
    const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype :
      el.tagName === "INPUT" ? HTMLInputElement.prototype : null;
    const setter = proto && Object.getOwnPropertyDescriptor(proto, "value")?.set;
    if (setter) setter.call(el, value);
    else if (el.isContentEditable) el.textContent = value;
    else return false;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function findField(patterns) {
    return controls().find(el => patterns.some(p => labelText(el).includes(norm(p))));
  }

  function fillField(patterns, value) {
    if (!value) return false;
    const el = findField(patterns);
    if (!el || el.tagName === "SELECT" || el.getAttribute("role") === "combobox") return false;
    return nativeSet(el, value);
  }

  async function chooseOption(control, wanted) {
    if (!control || !wanted || control.disabled || control.getAttribute("aria-disabled") === "true") return false;
    const target = norm(wanted);

    if (control.tagName === "SELECT") {
      const option = [...control.options].find(o => norm(o.textContent) === target) ||
        [...control.options].find(o => norm(o.textContent).includes(target));
      if (!option) return false;
      control.value = option.value;
      control.dispatchEvent(new Event("input", { bubbles: true }));
      control.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }

    control.click();
    await sleep(250);
    const options = [...document.querySelectorAll(
      '[role="option"],[role="menuitem"],[data-value],li,mat-option'
    )].filter(visible);
    const option = options.find(o => norm(o.innerText || o.textContent) === target) ||
      options.find(o => norm(o.innerText || o.textContent).includes(target));
    if (!option) {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return false;
    }
    option.click();
    await sleep(350);
    return true;
  }

  async function chooseByLabel(patterns, wanted) {
    const control = controls().find(el =>
      (el.tagName === "SELECT" || el.getAttribute("role") === "combobox") &&
      patterns.some(p => labelText(el).includes(norm(p)))
    );
    return chooseOption(control, wanted);
  }

  async function fillGoogle(report) {
    const p = report.payload;
    const url = (p.urls || [])[0] || "";

    // El primer selector corresponde al tipo de informe.
    const reportType = await chooseByLabel(
      ["tipo de informe", "report type"], "Esta página no es segura"
    );

    // El segundo selector corresponde al tipo de amenaza.
    const threatType = await chooseByLabel(
      ["tipo de amenaza", "threat type"], "Ingeniería social"
    );

    // Google habilita la categoría después de escoger el tipo de amenaza.
    await sleep(500);
    const threatCategory = await chooseByLabel(
      ["categoría de amenaza", "categoria de amenaza", "threat category"],
      p.googleThreatCategory || "Phishing bancario o financiero"
    );

    const urlFilled = fillField(["url que quieres denunciar", "url", "website", "sitio web"], url);
    const descriptionFilled = fillField(
      ["información adicional", "informacion adicional", "additional information", "description"],
      p.description || ""
    );

    showNotice(
      [reportType, threatType, threatCategory, urlFilled, descriptionFilled].filter(Boolean).length,
      [
        reportType && "Tipo de informe",
        threatType && "Tipo de amenaza",
        threatCategory && "Categoría de amenaza",
        urlFilled && "URL",
        descriptionFilled && "Información adicional"
      ].filter(Boolean)
    );
  }

  function fillOther(report) {
    const p = report.payload, urls = p.urls || [], url = urls[0] || "";
    let filled = 0, notes = [];
    const put = (patterns, value, label) => {
      if (value && fillField(patterns, value)) { filled++; notes.push(label); }
    };
    if (VENDOR === "virustotal") put(["url", "search", "buscar"], url, "URL para análisis");
    else if (VENDOR === "fortiguard") put(["url", "web filter", "lookup", "website"], url, "URL de Web Filter");
    else if (VENDOR === "netcraft") put(["url", "website", "web site", "site address"], urls.join("\n"), "URL(s) del reporte");
    else if (VENDOR === "eset") {
      put(["url", "website", "sample"], url, "URL sospechosa");
      put(["organization", "brand", "impersonat", "company"], p.brand, "Organización suplantada");
      put(["comment", "description", "additional information"], p.description, "Comentarios / evidencia");
    } else if (VENDOR === "cloudflare") {
      let host = ""; try { host = new URL(url).hostname; } catch {}
      put(["domain in question", "domain", "hostname"], host, "Dominio en cuestión");
      put(["specific phishing link", "url", "website"], url, "Enlace específico");
      put(["description", "details", "evidence"], p.description, "Descripción");
    } else if (VENDOR === "urlabuse") {
      put(["malicious url", "url", "website"], url, "URL maliciosa");
      put(["target", "brand", "organization"], p.brand, "Marca objetivo");
      put(["description", "comment", "details"], p.description, "Descripción");
    } else if (VENDOR === "watchguard") {
      put(["url", "uncategorized", "miscategorized", "website"],
        urls.map(u => `${u}, Phishing and Other Frauds`).join("\n"), "URLs y categoría sugerida");
    }
    showNotice(filled, notes);
  }

  function showNotice(count, notes) {
    const old = document.getElementById("soc-extension-autofill-notice");
    if (old) old.remove();
    const box = document.createElement("section");
    box.id = "soc-extension-autofill-notice";
    box.style.cssText = "position:fixed;z-index:2147483647;right:16px;bottom:16px;max-width:370px;background:#101b2c;color:#fff;border:1px solid #4387c8;border-radius:12px;padding:14px 16px;font:13px/1.45 system-ui;box-shadow:0 8px 30px #0006";
    const title = document.createElement("strong"); title.textContent = "SOC · Asistente de formulario";
    const msg = document.createElement("p"); msg.style.margin = "8px 0";
    msg.textContent = count ? `Se completaron ${count} campo(s): ${notes.join(", ")}.` :
      "No se detectaron campos compatibles. Puede que el portal haya cambiado su formulario.";
    const warning = document.createElement("p"); warning.style.margin = "8px 0";
    warning.textContent = "Revisa la URL, las selecciones y la descripción antes de enviar. No se ha enviado ningún reporte.";
    const close = document.createElement("button"); close.textContent = "Entendido";
    close.style.cssText = "background:#2866a0;color:white;border:0;border-radius:6px;padding:6px 10px;cursor:pointer";
    close.onclick = () => box.remove();
    box.append(title, msg, warning, close);
    document.documentElement.appendChild(box);
  }

  async function run() {
    for (let i = 0; i < 30; i++) {
      const { socPendingReport } = await chrome.storage.local.get("socPendingReport");
      if (socPendingReport && socPendingReport.vendor === VENDOR &&
          Date.now() - socPendingReport.createdAt < 120000) {
        await sleep(900);
        if (VENDOR === "google") await fillGoogle(socPendingReport);
        else fillOther(socPendingReport);
        await chrome.storage.local.remove("socPendingReport");
        return;
      }
      await sleep(500);
    }
  }
  run().catch(() => {});
})();
