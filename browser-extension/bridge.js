// Puente aislado: recibe un evento de la aplicación SOC y guarda el paquete localmente.
(() => {
  const ALLOWED = new Set(["virustotal","fortiguard","google","netcraft","eset","cloudflare","urlabuse","watchguard"]);
  window.addEventListener("soc-phishing-extension-dispatch", (event) => {
    const detail = event.detail;
    if (!detail || !ALLOWED.has(detail.vendor) || !detail.payload) return;
    const urls = Array.isArray(detail.payload.urls) ? detail.payload.urls : [];
    if (!urls.length || urls.length > 20) return;
    const safe = {
      vendor: detail.vendor,
      payload: {
        brand: String(detail.payload.brand || "").slice(0,120),
        analyst: String(detail.payload.analyst || "").slice(0,80),
        category: String(detail.payload.category || "Phishing").slice(0,80),
        reference: String(detail.payload.reference || "").slice(0,100),
        description: String(detail.payload.description || "").slice(0,1200),
        urls: urls.map(x => String(typeof x === "string" ? x : x.url || "")).filter(x => /^https?:\/\//i.test(x)).slice(0,20)
      },
      createdAt: Date.now()
    };
    if (!safe.payload.urls.length) return;
    chrome.storage.local.set({socPendingReport: safe});
  });
})();
