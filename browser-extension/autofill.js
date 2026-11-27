// Automatización asistida y conservadora. Nunca pulsa botones de envío.
(() => {
  const HOST = location.hostname.toLowerCase();
  const VENDOR = HOST.includes("virustotal") ? "virustotal" : HOST.includes("fortiguard") ? "fortiguard" :
    (HOST.includes("google.com") || HOST.includes("safebrowsing.google.com")) ? "google" :
    HOST.includes("netcraft") ? "netcraft" : HOST.includes("eset.com") ? "eset" :
    HOST.includes("cloudflare.com") ? "cloudflare" : HOST.includes("urlabuse") ? "urlabuse" :
    HOST.includes("watchguard") ? "watchguard" : "";
  if (!VENDOR) return;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const norm = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const visible = el => !!(el && el.getClientRects().length && getComputedStyle(el).visibility !== "hidden");
  const candidates = () => [...document.querySelectorAll('input:not([type="hidden"]),textarea,[contenteditable="true"],select')].filter(visible);
  const labelText = el => {
    const bits = [el.getAttribute("aria-label"),el.getAttribute("placeholder"),el.name,el.id,el.getAttribute("autocomplete")];
    if (el.id) { const lab=document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if(lab) bits.push(lab.innerText); }
    const parent=el.closest("label"); if(parent) bits.push(parent.innerText);
    const p=el.parentElement; if(p) bits.push(p.innerText?.slice(0,180));
    return norm(bits.filter(Boolean).join(" "));
  };
  const setValue = (el, value) => {
    if (!value || !el || el.disabled || el.readOnly) return false;
    if (el.tagName === "SELECT") {
      const wanted=norm(value);
      const opt=[...el.options].find(o=>norm(o.textContent).includes(wanted)||norm(o.value).includes(wanted));
      if (!opt) return false;
      el.value=opt.value; el.dispatchEvent(new Event("input",{bubbles:true})); el.dispatchEvent(new Event("change",{bubbles:true})); return true;
    }
    const proto=el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter=Object.getOwnPropertyDescriptor(proto,"value")?.set;
    if (setter) setter.call(el,value); else el.textContent=value;
    el.dispatchEvent(new Event("input",{bubbles:true})); el.dispatchEvent(new Event("change",{bubbles:true})); return true;
  };
  const find = patterns => candidates().find(el => patterns.some(p=>labelText(el).includes(p)));
  const fillFirst = (patterns,value) => { const el=find(patterns); return el ? setValue(el,value) : false; };
  function fill(report) {
    const p=report.payload, urls=p.urls || [], url=urls[0] || "";
    let filled=0, notes=[];
    const put=(patterns,value,label)=>{if(value && fillFirst(patterns,value)){filled++;notes.push(label);}};
    if (VENDOR === "virustotal") {
      put(["url","search","buscar"],url,"URL para análisis");
    } else if (VENDOR === "fortiguard") {
      put(["url","web filter","lookup","website"],url,"URL de Web Filter");
    } else if (VENDOR === "google") {
      put(["url","website","sitio web"],url,"URL del sitio");
      // Los desplegables de tipo de abuso se dejan al analista: sus etiquetas/opciones pueden cambiar.
    } else if (VENDOR === "netcraft") {
      put(["url","website","web site","site address"],urls.join("\n"),"URL(s) del reporte");
      put(["email"],"", "");
    } else if (VENDOR === "eset") {
      put(["url","website","sample"],url,"URL sospechosa");
      put(["organization","brand","impersonat","company"],p.brand,"Organización suplantada");
      put(["comment","description","additional information"],p.description,"Comentarios / evidencia");
    } else if (VENDOR === "cloudflare") {
      let host=""; try{host=new URL(url).hostname;}catch{}
      put(["domain in question","domain","hostname"],host,"Dominio en cuestión");
      put(["specific phishing link","url","website"],url,"Enlace específico");
      put(["description","details","evidence"],p.description,"Descripción");
    } else if (VENDOR === "urlabuse") {
      put(["malicious url","url","website"],url,"URL maliciosa");
      put(["target","brand","organization"],p.brand,"Marca objetivo");
      put(["description","comment","details"],p.description,"Descripción");
      // No completa nombre público del reportante ni categoría: requieren decisión explícita.
    } else if (VENDOR === "watchguard") {
      put(["url","uncategorized","miscategorized","website"],urls.map(u=>`${u}, Phishing and Other Frauds`).join("\n"),"URLs y categoría sugerida");
    }
    showNotice(filled,notes);
  }
  function showNotice(count,notes) {
    if (document.getElementById("soc-extension-autofill-notice")) return;
    const box=document.createElement("section"); box.id="soc-extension-autofill-notice";
    box.style.cssText="position:fixed;z-index:2147483647;right:16px;bottom:16px;max-width:360px;background:#101b2c;color:#fff;border:1px solid #4387c8;border-radius:12px;padding:14px 16px;font:13px/1.45 system-ui;box-shadow:0 8px 30px #0006";
    const title=document.createElement("strong"); title.textContent="SOC · Asistente de formulario";
    const msg=document.createElement("p"); msg.style.margin="8px 0"; msg.textContent=count ? `Se completaron ${count} campo(s): ${notes.join(", ")}.` : "No se detectaron campos compatibles para completar automáticamente.";
    const warning=document.createElement("p"); warning.style.margin="8px 0"; warning.textContent="Revisa todos los datos, completa los campos pendientes y realiza el envío manualmente. No se ha enviado ningún reporte.";
    const close=document.createElement("button"); close.textContent="Entendido"; close.style.cssText="background:#2866a0;color:white;border:0;border-radius:6px;padding:6px 10px;cursor:pointer"; close.onclick=()=>box.remove();
    box.append(title,msg,warning,close); document.documentElement.appendChild(box);
  }
  async function run() {
    for(let i=0;i<20;i++) {
      const {socPendingReport}=await chrome.storage.local.get("socPendingReport");
      if(socPendingReport && socPendingReport.vendor===VENDOR && Date.now()-socPendingReport.createdAt<120000) {
        await sleep(1200); fill(socPendingReport); await chrome.storage.local.remove("socPendingReport"); return;
      }
      await sleep(500);
    }
  }
  run().catch(()=>{});
})();
