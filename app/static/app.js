const labels={operational:"OPERATIVO",info:"AVISO",degraded:"DEGRADADO",outage:"INDISPONIBILIDAD",maintenance:"MANTENIMIENTO",manual:"CONSULTA MANUAL",unknown:"SIN INFORMACIÓN"};
const $=id=>document.getElementById(id);let cache=[],catalog=[];
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function date(s){if(!s)return "Aún no consultado";try{return new Date(s).toLocaleString("es-CL",{hour12:false})}catch{return s}}
function ageInfo(s){if(!s.checked_at)return {text:s.status==="manual"?"Revisión manual requerida":"Nunca consultado",kind:"never",mins:null};let mins=Math.max(0,Math.floor((Date.now()-new Date(s.checked_at).getTime())/60000));if(!Number.isFinite(mins))return {text:"Antigüedad desconocida",kind:"never",mins:null};if(mins>=60)return {text:`Desactualizado · ${mins} min`,kind:"stale",mins};return {text:mins<1?"Hace menos de 1 min":`Actualizado hace ${mins} min`,kind:"fresh",mins}}
function render(){const term=$("search").value.trim().toLowerCase(),cat=$("category").value,state=$("state").value,fresh=$("freshFilter").value;
 const rows=cache.filter(s=>{const a=ageInfo(s);return (!term||s.name.toLowerCase().includes(term)||s.category.toLowerCase().includes(term))&&(!cat||s.category===cat)&&(!state||s.status===state)&&(!fresh||a.kind===fresh)});
 $("services").innerHTML=rows.map(s=>{const a=ageInfo(s);return `<article class="service service-clickable" data-service-id="${esc(s.id)}" tabindex="0" role="button" aria-label="Ver detalle de ${esc(s.name)}"><div class="service-top"><div><span class="service-name">${esc(s.name)}</span><div class="category">${esc(s.category||"General")}</div></div><span class="pill ${esc(s.status)}">${labels[s.status]||"SIN INFORMACIÓN"}</span></div><div class="service-desc">${esc(s.description||s.error||"Pendiente de consulta")}</div><div class="service-foot"><span class="age ${a.kind}">${esc(a.text)}</span><span class="portal-area"><a class="portal-btn" href="${esc(s.source_url||"#")}" target="_blank" rel="noopener noreferrer" data-no-detail>${esc(s.portal_label||"Abrir portal oficial")} ↗</a></span></div><div class="detail-hint">Seleccionar para ver desglose e imagen del portal ↗</div>${s.error?`<div class="error-line">No se pudo consultar automáticamente: ${esc(s.error)}</div>`:""}</article>`}).join("")||'<div class="loading">No hay plataformas que coincidan con los filtros.</div>';
 updateMetricSelection();
}
function updateMetricSelection(){
 const selectedState=$("state").value;
 const selectedFresh=$("freshFilter").value;
 document.querySelectorAll(".metric-filter").forEach(card=>{
   const key=card.dataset.filter;
   const active=(key==="stale" ? selectedFresh==="stale" && !selectedState : selectedState===key && !selectedFresh);
   card.classList.toggle("active",active);
   card.setAttribute("aria-pressed",active?"true":"false");
 });
}
function renderChecklistOptions(){const groups={};for(const s of catalog){const c=s.category||"General";(groups[c]??=[]).push(s)}$("checklistServices").innerHTML=Object.entries(groups).map(([cat,items])=>`<div class="check-group"><b>${esc(cat)}</b><div class="check-items">${items.map(s=>`<label class="check-item"><input type="checkbox" class="service-check" value="${esc(s.id)}"><span>${esc(s.name)}</span><small>${s.type==="manual"?"Manual":"Fuente pública"}</small></label>`).join("")}</div></div>`).join("");}

const detailDialog=$("detailDialog");
function prettyStatus(value){
 const map={operational:"Operativo",info:"Aviso",degraded:"Degradado",outage:"Indisponible",maintenance:"Mantenimiento",manual:"Consulta manual",unknown:"Sin información"};
 return map[value]||String(value||"Sin información").replaceAll("_"," ");
}
function detailDate(value){if(!value)return "Fecha no informada";const d=new Date(value);return Number.isNaN(d.getTime())?esc(value):d.toLocaleString("es-CL",{hour12:false});}
function renderDetail(payload){
 const s=payload.service, latest=payload.latest, live=payload.live||{};
 $("detailTitle").textContent=s.name;
 $("detailSubtitle").textContent=`${s.category} · ${s.type==="manual"?"Revisión manual":"Fuente automática"} · Consultado ${detailDate(payload.retrieved_at)}`;
 const comps=(live.components||[]).slice(0,6).map(c=>`<div class="detail-row"><div><b>${esc(c.name)}</b>${c.description?`<small>${esc(c.description)}</small>`:""}</div><span class="pill ${esc(c.status)}">${esc(prettyStatus(c.status))}</span></div>`).join("");
 const incidents=(live.incidents||[]).slice(0,3).map(i=>`<article class="detail-incident"><div class="detail-row"><b>${esc(i.name||"Incidente")}</b><span class="pill ${esc(i.impact||i.status||"unknown")}">${esc(prettyStatus(i.impact||i.status||"unknown"))}</span></div><small>Inicio: ${esc(detailDate(i.created_at))} · Actualización: ${esc(detailDate(i.updated_at))}</small>${i.locations?`<p><b>Ubicaciones:</b> ${esc(i.locations)}</p>`:""}${i.body?`<p>${esc((i.body||"").slice(0,420))}</p>`:""}${(i.updates||[]).map(u=>`<div class="detail-update"><b>${esc(u.status||"Actualización")}</b> · ${esc(detailDate(u.created_at||u.display_at))}<p>${esc((u.body||"").slice(0,240))}</p></div>`).join("")}</article>`).join("");
 const maint=(live.maintenances||[]).slice(0,3).map(m=>`<article class="detail-incident"><b>${esc(m.name)}</b><small>${esc(m.status)} · ${esc(detailDate(m.scheduled_for))} – ${esc(detailDate(m.scheduled_until))}</small>${(m.updates||[]).map(u=>`<p>${esc(u.body)}</p>`).join("")}</article>`).join("");
 $("detailBody").innerHTML=`
  <div class="detail-summary">
   <div><span class="eyebrow">ESTADO PUBLICADO AHORA</span><h3><span class="pill ${esc(live.status||"unknown")}">${esc(prettyStatus(live.status||"unknown"))}</span></h3><p>${esc(live.source_status||"Sin resumen del proveedor")}</p><small>Consulta en vivo: ${esc(detailDate(payload.retrieved_at))}</small></div>
   <div class="detail-source"><span class="eyebrow">ÚLTIMO ESTADO GUARDADO</span><h3><span class="pill ${esc(latest.status)}">${esc(prettyStatus(latest.status))}</span></h3><p>${esc(latest.description||s.notes||"Sin descripción disponible.")}</p><small>Última actualización registrada: ${esc(detailDate(latest.checked_at))}</small></div>
  </div>
  ${payload.detail_error?`<div class="detail-warning">No se pudo obtener el desglose en vivo: ${esc(payload.detail_error)}. Se conserva el último resultado registrado.</div>`:""}
  ${live.source_kind==="manual"?`<div class="detail-warning">${esc(s.notes||"Esta fuente requiere revisión manual.")}</div>`:""}
  <section class="detail-section"><h3>Componentes y servicios</h3>${comps||'<p class="muted">La fuente no publica un desglose de componentes para esta integración.</p>'}</section>
  <section class="detail-section"><h3>Incidentes y actualizaciones</h3>${incidents||'<p class="muted">No hay incidentes activos publicados en esta respuesta.</p>'}</section>
  <section class="detail-section"><h3>Mantenimientos</h3>${maint||'<p class="muted">No se informan mantenimientos en esta respuesta.</p>'}</section>
  <div class="detail-footer"><span>Los estados corresponden a fuentes públicas y no necesariamente reflejan el tenant o instancia particular de tu organización.</span><a class="portal-btn" href="${esc(s.base_url)}" target="_blank" rel="noopener noreferrer">${esc(s.portal_label||"Abrir portal oficial")} ↗</a></div>`;
}
async function openServiceDetail(id){
 detailDialog.showModal();
 $("detailTitle").textContent="Cargando detalle…";
 $("detailSubtitle").textContent="";
 $("detailBody").innerHTML='<div class="loading">Consultando desglose e información actual del proveedor…</div>';
 try{
  const response=await fetch(`/api/services/${encodeURIComponent(id)}/detail`);
  const payload=await response.json();
  if(!response.ok)throw new Error(payload.detail||"No se pudo consultar el detalle");
  renderDetail(payload);
 }catch(error){
  $("detailBody").innerHTML=`<div class="detail-warning">${esc(error.message)}</div>`;
 }
}
$("closeDetail").addEventListener("click",()=>detailDialog.close());
detailDialog.addEventListener("click",e=>{if(e.target===detailDialog)detailDialog.close()});
$("services").addEventListener("click",e=>{
 if(e.target.closest("[data-no-detail]"))return;
 const card=e.target.closest("[data-service-id]");
 if(card)openServiceDetail(card.dataset.serviceId);
});
$("services").addEventListener("keydown",e=>{
 if((e.key==="Enter"||e.key===" ")&&e.target.matches("[data-service-id]")){e.preventDefault();openServiceDetail(e.target.dataset.serviceId);}
});

async function load(){try{const [sr,er,cr]=await Promise.all([fetch("/api/status"),fetch("/api/events?limit=100"),fetch("/api/config")]);if(!sr.ok||!er.ok||!cr.ok||!kr.ok)throw new Error("API no disponible");const data=await sr.json(),events=await er.json(),config=await cr.json();cache=data.services;catalog=config.services;
 for(const k of ["operational","info","degraded","outage","maintenance","manual","unknown"])$(k).textContent=data.counts[k]??0;
 const automatic=cache.filter(s=>s.status!=="manual"&&s.checked_at);const stale=automatic.filter(s=>ageInfo(s).kind==="stale").length;$("stale").textContent=stale;
 const checks=automatic.map(s=>s.checked_at).filter(Boolean).sort();$("updated").textContent=checks.length?date(checks[checks.length-1]):"Aún no consultado";
 $("freshSummary").textContent=`${automatic.length} fuentes con consulta registrada · ${stale} con datos de 60 min o más · ${cache.filter(s=>s.status==="manual").length} requieren revisión manual`;
 const cats=[...new Set(config.services.map(s=>s.category||"General"))].sort(),old=$("category").value;$("category").innerHTML='<option value="">Todas las categorías</option>'+cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join("");$("category").value=cats.includes(old)?old:"";render();
 $("events").innerHTML=events.length?events.map(e=>`<tr><td>${date(e.occurred_at)}</td><td><b>${esc(e.service_name)}</b></td><td class="change">${labels[e.old_status]||e.old_status} → ${labels[e.new_status]||e.new_status}</td><td>${esc(e.description)}</td></tr>`).join(""):'<tr><td colspan="4">Sin cambios de estado registrados.</td></tr>';
 }catch(e){$("services").innerHTML='<div class="loading">No se pudo conectar con el backend. Intenta nuevamente.</div>';$("freshSummary").textContent="No fue posible cargar los datos."}}
$("refresh").addEventListener("click",async()=>{$("refresh").disabled=true;$("refresh").textContent="Consultando fuentes…";try{const r=await fetch("/api/poll",{method:"POST"});const result=await r.json();if(!r.ok)throw new Error(result.detail||"Error");await load();toast(`Consulta finalizada: ${result.success} fuentes con respuesta, ${result.errors} sin información y ${result.manual} para revisar manualmente.`)}catch(e){toast("No se pudo completar la consulta: "+e.message)}finally{$("refresh").disabled=false;$("refresh").textContent="↻ Actualizar ahora"}});
document.querySelectorAll(".metric-filter").forEach(card=>card.addEventListener("click",()=>{
 const key=card.dataset.filter;
 $("search").value="";
 if(key==="stale"){ const already=$("freshFilter").value==="stale" && !$("state").value; $("state").value=""; $("freshFilter").value=already?"":"stale"; }
 else { $("state").value=($("state").value===key && !$("freshFilter").value)?"":key; $("freshFilter").value=""; }
 render();
 document.querySelector("#services").scrollIntoView({behavior:"smooth",block:"start"});
}));
$("search").addEventListener("input",render);$("category").addEventListener("change",render);$("state").addEventListener("change",render);$("freshFilter").addEventListener("change",render);
$("selectAll").addEventListener("click",()=>document.querySelectorAll(".service-check").forEach(x=>x.checked=true));$("clearAll").addEventListener("click",()=>document.querySelectorAll(".service-check").forEach(x=>x.checked=false));
$("saveChecklist").addEventListener("click",async()=>{const analyst=$("analyst").value.trim(),shift_name=$("shift").value,checkpoint=$("checkpoint").value,checked_services=[...document.querySelectorAll(".service-check:checked")].map(x=>x.value),notes=$("checkNotes").value.trim();$("saveChecklist").disabled=true;$("saveChecklist").textContent="Guardando…";try{const r=await fetch("/api/checklist",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({analyst,shift_name,checkpoint,checked_services,notes})});const data=await r.json();if(!r.ok)throw new Error(data.detail||"No se pudo guardar");$("checkMsg").textContent=`Revisión registrada: ${data.total_services} plataformas · ${date(data.created_at)}`;$("checkMsg").className="check-msg ok";document.querySelectorAll(".service-check").forEach(x=>x.checked=false);$("checkNotes").value="";await load()}catch(e){$("checkMsg").textContent=e.message;$("checkMsg").className="check-msg error"}finally{$("saveChecklist").disabled=false;$("saveChecklist").textContent="Registrar revisión"}});
function toast(t){$("toast").textContent=t;$("toast").classList.add("show");setTimeout(()=>$("toast").classList.remove("show"),4500)}
function tick(){$("clock").textContent=new Date().toLocaleTimeString("es-CL",{hour12:false})}tick();setInterval(tick,1000);load();

// ---------------------------------------------------------------------------
// SOC Global Threat Intelligence — Part 1: manually refreshed public news
// ---------------------------------------------------------------------------
let intelPeriod = "7d";
let intelCategory = "all";
let intelItems = [];
const intelCategoryNames = {
  global: "Noticias mundiales",
  ransomware: "Ransomware",
  espionage: "Espionaje",
  leaks: "Filtraciones",
  ddos: "DDoS",
  malware: "Malware"
};

function renderIntelNews() {
  const visible = intelItems.filter(item =>
    intelCategory === "all" || (item.categories || []).includes(intelCategory)
  );
  $("intelCount").textContent = `${visible.length} publicaciones`;
  $("intelNewsList").innerHTML = visible.length ? visible.map(item => {
    const tags = (item.categories || []).map(key =>
      `<span class="intel-tag tag-${esc(key)}">${esc(intelCategoryNames[key] || key)}</span>`
    ).join("");
    const published = item.published_at ? date(item.published_at) : "Fecha no informada";
    return `<article class="intel-news-card">
      <div class="intel-card-top"><span class="intel-source-name">${esc(item.source)}</span><time>${esc(published)}</time></div>
      <h3>${esc(item.title)}</h3>
      <p>${esc(item.summary || "La fuente no publicó un extracto.")}</p>
      <div class="intel-card-bottom"><div class="intel-tags">${tags}</div>
      <a href="${esc(item.link)}" target="_blank" rel="noopener noreferrer">Leer fuente original ↗</a></div>
    </article>`;
  }).join("") : `<div class="intel-empty"><b>No hay publicaciones para este filtro</b><span>Prueba otra categoría o amplía el período a 7 días.</span></div>`;

  document.querySelectorAll(".intel-category").forEach(button => {
    const active = button.dataset.intelCategory === intelCategory;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  document.querySelectorAll(".intel-period-btn").forEach(button => {
    const active = button.dataset.period === intelPeriod;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function renderIntelSources(sources) {
  if (!sources || !sources.length) {
    $("intelSources").innerHTML = '<span class="muted">Todavía no se ha ejecutado una actualización.</span>';
    return;
  }
  $("intelSources").innerHTML = sources.map(source => `
    <div class="intel-source-row">
      <b>${esc(source.source)}</b>
      ${source.ok
        ? `<span class="intel-source-ok">Consultada · ${Number(source.items || 0)} entradas</span>`
        : `<span class="intel-source-fail">Sin respuesta · ${esc(source.error || "Error de consulta")}</span>`}
    </div>`).join("");
}

async function loadIntelNews() {
  try {
    const response = await fetch(`/api/threat-intel/news?period=${encodeURIComponent(intelPeriod)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "No se pudo leer la caché");
    intelItems = data.items || [];
    $("intelLastRefresh").textContent = data.last_refresh
      ? `Última consulta: ${date(data.last_refresh)}`
      : "Sin actualización registrada";
    const totalSources = (data.sources || []).length || 5;
    $("intelSourceSummary").textContent = `${data.sources?.filter(x => x.ok).length || 0} de ${totalSources} fuentes respondieron en la última consulta`;
    renderIntelSources(data.sources || []);
    renderIntelNews();
    return true;
  } catch (error) {
    $("intelSourceSummary").textContent = `No se pudo cargar la inteligencia: ${error.message}`;
    $("intelNewsList").innerHTML = `<div class="intel-empty"><b>No se pudo cargar la inteligencia</b><span>${esc(error.message)}</span></div>`;
    return false;
  }
}

$("refreshIntel").addEventListener("click", async () => {
  const button = $("refreshIntel");
  button.disabled = true;
  button.textContent = "Consultando fuentes…";
  $("intelSourceSummary").textContent = "Consultando cinco fuentes públicas en paralelo. Puede tardar varios segundos…";
  $("intelNewsList").innerHTML = '<div class="intel-empty"><b>Consultando fuentes públicas…</b><span>Se está actualizando la caché. No cierres esta pestaña durante la consulta.</span></div>';
  try {
    const response = await fetch("/api/threat-intel/news/refresh", {
      method: "POST",
      cache: "no-store",
      headers: { "Accept": "application/json" }
    });
    let result;
    try {
      result = await response.json();
    } catch {
      throw new Error(`El servidor respondió HTTP ${response.status}, pero no entregó una respuesta JSON válida.`);
    }
    if (!response.ok) throw new Error(result.detail || `El servidor respondió HTTP ${response.status}.`);
    const loaded = await loadIntelNews();
    if (!loaded) throw new Error("La consulta terminó, pero no fue posible recuperar las publicaciones guardadas.");
    const totalSources = (result.sources || []).length || 5;
    const successful = Number(result.successful_sources || 0);
    $("intelSourceSummary").textContent = `Consulta completada: ${successful} de ${totalSources} fuentes disponibles · ${result.fetched || 0} registros procesados.`;
    toast(`Inteligencia actualizada: ${result.fetched || 0} publicaciones procesadas · ${successful}/${totalSources} fuentes disponibles.`);
  } catch (error) {
    $("intelSourceSummary").textContent = `No se pudo actualizar: ${error.message}`;
    $("intelNewsList").innerHTML = `<div class="intel-empty"><b>No se pudo actualizar la inteligencia</b><span>${esc(error.message)}. Verifica que Render haya terminado de iniciar y vuelve a intentarlo.</span></div>`;
    toast("No se pudo actualizar la inteligencia: " + error.message);
  } finally {
    button.disabled = false;
    button.textContent = "↻ Actualizar inteligencia";
  }
});

document.querySelectorAll(".intel-period-btn").forEach(button => {
  button.addEventListener("click", () => {
    intelPeriod = button.dataset.period;
    loadIntelNews();
  });
});
document.querySelectorAll(".intel-category").forEach(button => {
  button.addEventListener("click", () => {
    intelCategory = button.dataset.intelCategory;
    renderIntelNews();
  });
});

loadIntelNews();

// ---------------------------------------------------------------------------
// SOC Global Threat Intelligence — Part 2: ransomware claims and country map
// ---------------------------------------------------------------------------
let rwPeriod = "7d";
let rwItems = [];
let rwMapInstance = null;
let rwMapMarkers = null;

function rwUtcDate(value) {
  if (!value) return "Fecha no informada";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

function renderRansomwareSources(sources) {
  if (!sources || !sources.length) {
    $("rwSources").innerHTML = '<span class="muted">Todavía no se ha ejecutado una actualización.</span>';
    return;
  }
  $("rwSources").innerHTML = sources.map(source => `
    <div class="intel-source-row">
      <b>${esc(source.source || "Fuente externa")}</b>
      ${source.ok
        ? `<span class="intel-source-ok">${source.cached ? "Caché reutilizada" : "Consultada"} · ${Number(source.items || 0)} registros</span>`
        : `<span class="intel-source-fail">Sin respuesta · ${esc(source.error || "Error de consulta")}</span>`}
    </div>`).join("");
}

function renderRansomwareMap(countries) {
  const status = $("rwMapStatus");
  if (!window.L) {
    status.textContent = "Mapa externo no disponible";
    $("rwMap").innerHTML = '<div class="rw-map-fallback">No se pudo cargar la librería del mapa. La distribución por país está disponible en el resumen lateral.</div>';
    return;
  }
  if (!rwMapInstance) {
    rwMapInstance = L.map("rwMap", { scrollWheelZoom: false, worldCopyJump: true }).setView([20, 0], 2);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      minZoom: 1, maxZoom: 7,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
    }).addTo(rwMapInstance);
    rwMapMarkers = L.layerGroup().addTo(rwMapInstance);
  }
  rwMapMarkers.clearLayers();
  const valid = (countries || []).filter(c => Number.isFinite(Number(c.lat)) && Number.isFinite(Number(c.lon)));
  valid.forEach(country => {
    const count = Number(country.count || 0);
    const radius = Math.min(18, 6 + Math.sqrt(count) * 2.2);
    const marker = L.circleMarker([Number(country.lat), Number(country.lon)], {
      radius, color: "#ff9eae", weight: 1.5, opacity: .95,
      fillColor: "#c94765", fillOpacity: .72
    });
    marker.bindPopup(`<b>${esc(country.name)}</b><br>${count} publicación(es) asociada(s)`);
    marker.addTo(rwMapMarkers);
  });
  if (valid.length > 1) {
    const bounds = L.latLngBounds(valid.map(c => [Number(c.lat), Number(c.lon)]));
    rwMapInstance.fitBounds(bounds, { padding: [22, 22], maxZoom: 3 });
  } else if (valid.length === 1) {
    rwMapInstance.setView([Number(valid[0].lat), Number(valid[0].lon)], 3);
  } else {
    rwMapInstance.setView([20, 0], 2);
  }
  status.textContent = valid.length ? `${valid.length} países representados` : "Sin países identificados";
  const mapNode = $("rwMap");
  if (!valid.length) {
    mapNode.classList.add("map-no-data");
    if (!mapNode.querySelector(".rw-map-empty")) {
      const note=document.createElement("div");
      note.className="rw-map-empty";
      note.textContent="No hay publicaciones con país identificable en el período seleccionado. El mapa se mostrará cuando existan ubicaciones respaldadas por la fuente.";
      mapNode.appendChild(note);
    }
  } else {
    mapNode.classList.remove("map-no-data");
    mapNode.querySelector(".rw-map-empty")?.remove();
  }
  setTimeout(() => rwMapInstance && rwMapInstance.invalidateSize(), 180);
}

function renderRansomwareRankedLists(data) {
  const countries = data.countries || [];
  $("rwCountryList").innerHTML = countries.length ? countries.slice(0, 8).map(country => `
    <div class="rw-rank-item"><span>${esc(country.name)}</span><b>${Number(country.count || 0)}</b></div>`).join("")
    : '<span class="muted">No hay países asociados con confianza suficiente.</span>';
  const groups = data.top_groups || [];
  $("rwGroupList").innerHTML = groups.length ? groups.map(group => `
    <div class="rw-rank-item"><span>${esc(group.name)}</span><b>${Number(group.count || 0)}</b></div>`).join("")
    : '<span class="muted">No hay grupos publicados en este período.</span>';
}

function renderRansomwareRows() {
  const term = $("rwSearch").value.trim().toLowerCase();
  const group = $("rwGroupFilter").value;
  const visible = rwItems.filter(item => {
    const haystack = `${item.victim || ""} ${item.group_name || ""} ${item.country_name || ""}`.toLowerCase();
    return (!term || haystack.includes(term)) && (!group || item.group_name === group);
  });
  $("rwVisibleCount").textContent = `${visible.length} de ${rwItems.length} registros`;
  $("rwItems").innerHTML = visible.length ? visible.map(item => {
    const country = item.country_name
      ? `<span class="rw-country">${esc(item.country_name)}</span>`
      : '<span class="rw-no-country">Sin asignar</span>';
    const context = item.description
      ? `<div class="rw-context"><details><summary>Ver contexto</summary><p>${esc(item.description)}</p></details></div>`
      : '<span class="rw-no-country">Sin contexto</span>';
    return `<tr>
      <td>${esc(rwUtcDate(item.discovered_at))}</td>
      <td><span class="rw-victim">${esc(item.victim)}</span></td>
      <td><span class="rw-group">${esc(item.group_name)}</span></td>
      <td>${country}</td>
      <td>${context}</td>
      <td><a href="${esc(item.source_link || "https://www.ransomlook.io/recent")}" target="_blank" rel="noopener noreferrer">RansomLook ↗</a></td>
    </tr>`;
  }).join("") : '<tr><td colspan="6" class="rw-empty-cell">No hay publicaciones que coincidan con los filtros.</td></tr>';
}

function renderRansomware(data) {
  rwItems = data.items || [];
  $("rwVictimCount").textContent = Number(data.count || 0).toLocaleString("es-CL");
  $("rwGroupCount").textContent = Number(data.groups_count || 0).toLocaleString("es-CL");
  $("rwCountryCount").textContent = Number(data.countries_count || 0).toLocaleString("es-CL");
  $("rwUnknownCount").textContent = Number(data.unmapped_count || 0).toLocaleString("es-CL");
  $("rwLastRefresh").textContent = data.last_refresh ? `Última consulta: ${date(data.last_refresh)}` : "Sin actualización registrada";
  const groupNames = [...new Set(rwItems.map(item => item.group_name).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"es"));
  const selectedGroup = $("rwGroupFilter").value;
  $("rwGroupFilter").innerHTML = '<option value="">Todos los grupos</option>' + groupNames.map(name => `<option value="${esc(name)}">${esc(name)}</option>`).join("");
  $("rwGroupFilter").value = groupNames.includes(selectedGroup) ? selectedGroup : "";
  document.querySelectorAll(".rw-period-btn").forEach(button => {
    const active = button.dataset.rwPeriod === rwPeriod;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  renderRansomwareRankedLists(data);
  renderRansomwareMap(data.countries || []);
  renderRansomwareRows();
  renderRansomwareSources(data.sources || []);
}

async function loadRansomware() {
  try {
    const response = await fetch(`/api/threat-intel/ransomware?period=${encodeURIComponent(rwPeriod)}`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    renderRansomware(data);
    if (!data.count && !data.last_refresh) {
      $("rwMapStatus").textContent = "Pendiente de primera consulta";
    }
    return true;
  } catch (error) {
    $("rwMapStatus").textContent = "No se pudo cargar la información";
    $("rwItems").innerHTML = `<tr><td colspan="6" class="rw-empty-cell">No se pudo cargar el tracker: ${esc(error.message)}</td></tr>`;
    return false;
  }
}

$("refreshRansomware").addEventListener("click", async () => {
  const button = $("refreshRansomware");
  button.disabled = true;
  button.textContent = "Consultando RansomLook…";
  $("rwMapStatus").textContent = "Actualizando publicaciones…";
  $("rwItems").innerHTML = '<tr><td colspan="6" class="rw-empty-cell">Consultando la fuente pública. Puede tardar unos segundos…</td></tr>';
  try {
    const response = await fetch("/api/threat-intel/ransomware/refresh", {
      method: "POST", cache: "no-store", headers: { "Accept": "application/json" }
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
    const loaded = await loadRansomware();
    if (!loaded) throw new Error("La fuente respondió, pero no se pudo recuperar la caché local.");
    if (result.skipped) {
      toast(result.message || "Se reutilizó la caché reciente.");
    } else if (result.ok) {
      toast(`Ransomware actualizado: ${Number(result.fetched || 0)} publicaciones procesadas.`);
    } else {
      const reason = result.sources?.find(x => !x.ok)?.error || "La fuente no respondió correctamente.";
      $("rwMapStatus").textContent = "Última consulta con error; caché conservada";
      toast("No se pudo actualizar RansomLook: " + reason);
    }
  } catch (error) {
    $("rwMapStatus").textContent = "No se pudo completar la consulta";
    $("rwItems").innerHTML = `<tr><td colspan="6" class="rw-empty-cell">Error: ${esc(error.message)}. La caché anterior se conserva.</td></tr>`;
    toast("No se pudo actualizar el tracker: " + error.message);
  } finally {
    button.disabled = false;
    button.textContent = "↻ Actualizar ransomware";
  }
});

document.querySelectorAll(".rw-period-btn").forEach(button => {
  button.addEventListener("click", () => {
    rwPeriod = button.dataset.rwPeriod;
    loadRansomware();
  });
});
$("rwSearch").addEventListener("input", renderRansomwareRows);
$("rwGroupFilter").addEventListener("change", renderRansomwareRows);
loadRansomware();


// Vulnerability intelligence: CISA KEV, NVD and FIRST EPSS
let vulnRowsCache = [];
function renderVulnerabilities(data) {
  vulnRowsCache = data.items || [];
  $("vulnCount").textContent = data.count || 0;
  $("vulnKevCount").textContent = data.kev_count || "—";
  $("vulnNvdCount").textContent = data.nvd_count || "—";
  $("vulnLastRefresh").textContent = data.last_refresh ? new Date(data.last_refresh).toLocaleString("es-CL") : "Pendiente";
  const rows = vulnRowsCache.map(v => {
    const cvss = v.cvss == null ? "—" : `${Number(v.cvss).toFixed(1)} · ${esc(v.severity || "")}`;
    const epss = v.epss == null ? "—" : `${(Number(v.epss)*100).toFixed(2)}%`;
    const kev = Number(v.kev) ? `<span class="vuln-kev">Sí · ${esc(v.ransomware_use || "Unknown")}</span>` : "No";
    const date = v.published ? new Date(v.published).toLocaleDateString("es-CL") : (v.kev_date || "—");
    return `<tr><td><a href="${esc(v.source_url)}" target="_blank" rel="noopener">${esc(v.cve)}</a></td><td><b>${esc(v.title || v.cve)}</b><small>${esc([v.vendor,v.product].filter(Boolean).join(" · "))}</small><p>${esc(v.description || "")}</p></td><td>${cvss}</td><td>${epss}</td><td>${kev}</td><td>${esc(date)}</td><td><a href="${esc(v.source_url)}" target="_blank" rel="noopener">NVD ↗</a></td></tr>`;
  }).join("");
  $("vulnRows").innerHTML = rows || '<tr><td colspan="7">No hay registros para este filtro. Actualiza las fuentes públicas.</td></tr>';
}
async function loadVulnerabilities() {
  const period = $("vulnPeriod").value;
  const search = $("vulnSearch").value.trim();
  try {
    const response = await fetch(`/api/threat-intel/vulnerabilities?period=${encodeURIComponent(period)}&search=${encodeURIComponent(search)}`, {cache:"no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    renderVulnerabilities(data);
    $("vulnMessage").textContent = data.last_refresh ? "Caché local · Fuentes: CISA KEV, NVD y enriquecimiento EPSS cuando está disponible." : "Pendiente de primera actualización.";
  } catch (e) {
    $("vulnMessage").textContent = "No se pudo cargar la caché: " + e.message;
  }
}
$("refreshVulns").addEventListener("click", async () => {
  const button = $("refreshVulns");
  button.disabled = true; button.textContent = "Consultando CISA, NVD y EPSS…";
  $("vulnMessage").textContent = "Actualizando fuentes públicas. Puede tardar unos segundos…";
  try {
    const response = await fetch("/api/threat-intel/vulnerabilities/refresh", {method:"POST",cache:"no-store",headers:{"Accept":"application/json"}});
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
    await loadVulnerabilities();
    $("vulnMessage").textContent = `Actualizado: ${result.kev_count} registros CISA KEV · ${result.nvd_count} CVE NVD · ${result.epss_enriched} enriquecidas con EPSS.`;
    toast("Inteligencia de vulnerabilidades actualizada.");
  } catch(e) {
    $("vulnMessage").textContent = "Error al actualizar: " + e.message + ". Se conserva la caché anterior.";
    toast("No se pudo actualizar vulnerabilidades: " + e.message);
  } finally { button.disabled = false; button.textContent = "↻ Actualizar vulnerabilidades"; }
});
$("vulnPeriod").addEventListener("change", loadVulnerabilities);
let vulnSearchTimer;
$("vulnSearch").addEventListener("input", () => { clearTimeout(vulnSearchTimer); vulnSearchTimer = setTimeout(loadVulnerabilities, 250); });
loadVulnerabilities();

// v1.8.1: módulo de inicio y navegación por tarjetas
const moduleTitles={platforms:"Estado de plataformas",news:"Ataques y amenazas publicados",ransomware:"Ransomware tracker y mapa geográfico",vulns:"Vulnerability Intelligence"};
function showModule(name){
  $("moduleHome").hidden=true;
  $("moduleNav").hidden=false;
  document.querySelectorAll(".module-view").forEach(v=>v.hidden=true);
  const view=$("view-"+name); if(view) view.hidden=false;
  $("activeModuleName").textContent=moduleTitles[name]||"";
  if(name==="ransomware" && rwMapInstance) setTimeout(()=>rwMapInstance.invalidateSize(),220);
  if(name==="ransomware" && !rwItems.length) loadRansomware();
}
document.querySelectorAll("[data-open-module]").forEach(card=>card.addEventListener("click",()=>showModule(card.dataset.openModule)));
$("backHome").addEventListener("click",()=>{
  document.querySelectorAll(".module-view").forEach(v=>v.hidden=true);
  $("moduleNav").hidden=true; $("moduleHome").hidden=false;
});
$("homeRefresh").addEventListener("click",()=>{$("refresh").click()});
