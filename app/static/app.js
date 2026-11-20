const labels={operational:"OPERATIVO",info:"AVISO",degraded:"DEGRADADO",outage:"INDISPONIBILIDAD",maintenance:"MANTENIMIENTO",manual:"CONSULTA MANUAL",unknown:"SIN INFORMACIÓN"};
const $=id=>document.getElementById(id);let cache=[],catalog=[],eventCache=[],platformEventDateFilter="";
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function date(s){if(!s)return "Aún no consultado";try{return new Date(s).toLocaleString("es-CL",{hour12:false})}catch{return s}}
function ageInfo(s){if(!s.checked_at)return {text:s.status==="manual"?"Revisión manual requerida":"Nunca consultado",kind:"never",mins:null};let mins=Math.max(0,Math.floor((Date.now()-new Date(s.checked_at).getTime())/60000));if(!Number.isFinite(mins))return {text:"Antigüedad desconocida",kind:"never",mins:null};if(mins>=60)return {text:`Desactualizado · ${mins} min`,kind:"stale",mins};return {text:mins<1?"Hace menos de 1 min":`Actualizado hace ${mins} min`,kind:"fresh",mins}}
function render(){const term=$("search").value.trim().toLowerCase(),cat=$("category").value,state=$("state").value,fresh=$("freshFilter").value;
 const rows=cache.filter(s=>{const a=ageInfo(s);return (!term||s.name.toLowerCase().includes(term)||s.category.toLowerCase().includes(term))&&(!cat||s.category===cat)&&(!state||s.status===state)&&(!fresh||a.kind===fresh)});
 $("services").innerHTML=rows.map(s=>{const a=ageInfo(s);return `<article class="service service-clickable" data-service-id="${esc(s.id)}" tabindex="0" role="button" aria-label="Ver detalle de ${esc(s.name)}"><div class="service-top"><div><span class="service-name">${esc(s.name)}</span><div class="category">${esc(s.category||"General")}</div></div><span class="pill ${esc(s.status)}">${labels[s.status]||"SIN INFORMACIÓN"}</span></div><div class="service-desc">${esc(s.description||s.error||"Pendiente de consulta")}</div><div class="service-foot"><span class="age ${a.kind}">${esc(a.text)}</span><span class="portal-area"><a class="portal-btn" href="${esc(s.source_url||"#")}" target="_blank" rel="noopener noreferrer" data-no-detail>${esc(s.portal_label||"Abrir portal oficial")} ↗</a></span></div><div class="detail-hint">Seleccionar para ver el detalle y el enlace oficial ↗</div>${s.error?`<div class="error-line">No se pudo consultar automáticamente: ${esc(s.error)}</div>`:""}</article>`}).join("")||'<div class="loading">No hay plataformas que coincidan con los filtros.</div>';
 updateMetricSelection();
 renderPlatformDrillFilter();
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

// ---------------------------------------------------------------------------
// Fase 2 — Visualizaciones del módulo Estado de plataformas
// ---------------------------------------------------------------------------

function localDateKey(value) {
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
function buildDailyTimeline(items, dateKey, days=7) {
  const today=new Date(); today.setHours(0,0,0,0);
  const buckets=[];
  for(let offset=days-1;offset>=0;offset--){
    const day=new Date(today); day.setDate(today.getDate()-offset);
    buckets.push({key:localDateKey(day),label:day.toLocaleDateString("es-CL",{day:"2-digit",month:"short"}),count:0});
  }
  const lookup=new Map(buckets.map((item,index)=>[item.key,index]));
  (items||[]).forEach(item=>{
    const stamp=item[dateKey]; if(!stamp)return;
    const key=localDateKey(stamp); const index=lookup.get(key);
    if(index!==undefined)buckets[index].count+=1;
  });
  return buckets;
}
function buildFourHourTimeline(items,dateKey) {
  const now=new Date(), width=4*60*60*1000, current=Math.floor(now.getTime()/width)*width;
  const buckets=[];
  for(let offset=5;offset>=0;offset--){
    const start=new Date(current-offset*width), end=new Date(start.getTime()+width);
    buckets.push({start:start.getTime(),end:end.getTime(),key:start.toISOString(),label:start.toLocaleTimeString("es-CL",{hour:"2-digit",minute:"2-digit"}),count:0});
  }
  (items||[]).forEach(item=>{
    const stamp=new Date(item[dateKey]||"").getTime(); if(!Number.isFinite(stamp))return;
    const bucket=buckets.find(x=>stamp>=x.start&&stamp<x.end);
    if(bucket)bucket.count+=1;
  });
  return buckets;
}
function renderTimelineChart(targetId,buckets,options={}) {
  const node=$(targetId); if(!node)return;
  const max=Math.max(1,...(buckets||[]).map(x=>Number(x.count||x.total||0)));
  if(!(buckets||[]).some(x=>Number(x.count||x.total||0)>0)){
    node.innerHTML=`<span class="module-chart-empty">${esc(options.empty||"Sin registros para graficar.")}</span>`;
    return;
  }
  node.innerHTML=`<div class="module-timeline-columns">${buckets.map(item=>{
    const value=Number(item.count||item.total||0), height=value?Math.max(4,value/max*100):0;
    const title=`${item.label}: ${value} registros`;
    let segments="";
    if(options.stacked){
      const a=Number(item.RansomLook||0), b=Number(item["Ransomware.live"]||0), sum=a+b||1;
      segments=`<i class="timeline-segment rlook" style="height:${(a/sum*height).toFixed(2)}%"></i><i class="timeline-segment rlive" style="height:${(b/sum*height).toFixed(2)}%"></i>`;
    } else {
      segments=`<i style="height:${height.toFixed(2)}%;background:${options.color||"#5daaf5"}"></i>`;
    }
    const drill = options.filterType
      ? `type="button" class="module-timeline-column module-chart-drilldown${options.isActive?.(item) ? " is-active" : ""}" data-chart-filter="${esc(options.filterType)}" data-chart-value="${esc(item.key||"")}" data-chart-start="${Number(item.start||0)}" data-chart-end="${Number(item.end||0)}" aria-label="Filtrar por ${esc(item.label)}: ${value} registros"`
      : `class="module-timeline-column"`;
    const tag = options.filterType ? "button" : "div";
    return `<${tag} ${drill} title="${esc(title)}"><b>${value||""}</b><div class="module-timeline-track">${segments}</div><small>${esc(item.label)}</small></${tag}>`;
  }).join("")}</div>${options.stacked?'<div class="module-chart-legend-inline"><span><i class="rlook"></i>RansomLook</span><span><i class="rlive"></i>Ransomware.live</span></div>':""}`;
}
function renderHorizontalChart(targetId,items,options={}) {
  const node=$(targetId); if(!node)return;
  const rows=(items||[]).filter(item=>Number(item.value||0)>0).sort((a,b)=>b.value-a.value).slice(0,options.limit||8);
  if(!rows.length){node.innerHTML=`<span class="module-chart-empty">${esc(options.empty||"Sin registros para graficar.")}</span>`;return;}
  const max=Math.max(1,...rows.map(x=>Number(x.value||0)));
  node.innerHTML=rows.map(item=>{
    const width=Math.max(2,Number(item.value||0)/max*100);
    const drill=options.filterType?`type="button" class="module-horizontal-row module-chart-drilldown${options.isActive?.(item) ? " is-active" : ""}" data-chart-filter="${esc(options.filterType)}" data-chart-value="${esc(item.filterValue??item.label)}" aria-label="Filtrar ${esc(item.label)}: ${Number(item.value).toLocaleString("es-CL")} registros"`:`class="module-horizontal-row"`;
    const tag=options.filterType?"button":"div";
    return `<${tag} ${drill}><div class="module-horizontal-label"><span>${esc(item.label)}</span><b>${Number(item.value).toLocaleString("es-CL")}</b></div><div class="module-horizontal-track"><i style="width:${width.toFixed(1)}%;background:${item.color||options.color||"#5daaf5"}"></i></div></${tag}>`;
  }).join("");
}

const platformChartStates = [
  {key:"operational",label:"Operativas",color:"#35c99a"},
  {key:"info",label:"Avisos",color:"#5daaf5"},
  {key:"degraded",label:"Degradadas",color:"#efbd5d"},
  {key:"outage",label:"Indisponibles",color:"#ef777d"},
  {key:"maintenance",label:"Mantenimiento",color:"#9b8be9"},
  {key:"manual",label:"Consulta manual",color:"#8796aa"},
  {key:"unknown",label:"Sin información",color:"#56677b"}
];

function renderPlatformAnalytics(services, events) {
  const counts = Object.fromEntries(platformChartStates.map(x=>[x.key,0]));
  (services||[]).forEach(service=>{
    const state = counts[service.status] === undefined ? "unknown" : service.status;
    counts[state] += 1;
  });
  const total = (services||[]).length;
  $("platformStateTotal").textContent = total.toLocaleString("es-CL");
  let cursor=0;
  const segments=[];
  platformChartStates.forEach(item=>{
    const value=counts[item.key]||0;
    if(!value)return;
    const start=cursor; cursor += value/Math.max(1,total)*100;
    segments.push(`${item.color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`);
  });
  $("platformStateDonut").style.background = total
    ? `conic-gradient(${segments.join(",")})`
    : "conic-gradient(#27384c 0 100%)";
  $("platformStateLegend").innerHTML = platformChartStates.filter(x=>counts[x.key]>0).map(item=>{
    const value=counts[item.key], pct=total?(value/total*100).toFixed(0):0;
    return `<button type="button" class="module-chart-legend-row module-chart-drilldown${$("state").value===item.key?" is-active":""}" data-chart-filter="platform-status" data-chart-value="${item.key}" aria-label="Filtrar plataformas: ${item.label}, ${value}"><i style="background:${item.color}"></i><span>${item.label}</span><b>${value}</b><small>${pct}%</small></button>`;
  }).join("") || '<span class="module-chart-empty">Aún no hay estados registrados.</span>';

  const byCategory=new Map();
  (services||[]).forEach(service=>{
    const category=service.category||"General";
    if(!byCategory.has(category))byCategory.set(category,Object.fromEntries(platformChartStates.map(x=>[x.key,0])));
    const state=counts[service.status]===undefined?"unknown":service.status;
    byCategory.get(category)[state]+=1;
  });
  const categories=[...byCategory.entries()].map(([name,values])=>({name,values,total:Object.values(values).reduce((a,b)=>a+b,0)}))
    .sort((a,b)=>b.total-a.total).slice(0,8);
  const maxCategory=Math.max(1,...categories.map(x=>x.total));
  $("platformCategoryBars").innerHTML=categories.length?categories.map(item=>{
    const parts=platformChartStates.filter(state=>item.values[state.key]>0).map(state=>{
      const width=item.values[state.key]/maxCategory*100;
      return `<i class="stack-segment" title="${esc(state.label)}: ${item.values[state.key]}" style="width:${width.toFixed(2)}%;background:${state.color}"></i>`;
    }).join("");
    return `<button type="button" class="module-stack-row module-chart-drilldown${$("category").value===item.name?" is-active":""}" data-chart-filter="platform-category" data-chart-value="${esc(item.name)}" aria-label="Filtrar categoría ${esc(item.name)}: ${item.total} plataformas"><div class="module-stack-label"><span>${esc(item.name)}</span><b>${item.total}</b></div><div class="module-stack-track">${parts}</div></button>`;
  }).join(""):'<span class="module-chart-empty">No hay categorías de plataformas.</span>';

  const timeline=buildDailyTimeline(events||[],"occurred_at",7).map(x=>({...x,count:x.count}));
  renderTimelineChart("platformEventTrend",timeline,{color:"#5daaf5",filterType:"platform-event-date",isActive:item=>platformEventDateFilter===item.key,empty:"Sin cambios de estado registrados en este período."});
  renderPlatformDrillFilter();
  const totalEvents=timeline.reduce((sum,item)=>sum+item.count,0);
  $("platformEventNote").textContent=`${totalEvents} transiciones en los últimos 7 días, calculadas sobre los 100 cambios más recientes disponibles. Solo se cuentan cambios detectados; no son mediciones continuas de disponibilidad.`;
}

function renderPlatformEvents(){
 const rows=platformEventDateFilter?eventCache.filter(item=>localDateKey(item.occurred_at)===platformEventDateFilter):eventCache;
 $("events").innerHTML=rows.length?rows.map(e=>`<tr><td>${date(e.occurred_at)}</td><td><b>${esc(e.service_name)}</b></td><td class="change">${labels[e.old_status]||e.old_status} → ${labels[e.new_status]||e.new_status}</td><td>${esc(e.description)}</td></tr>`).join(""):'<tr><td colspan="4">Sin cambios de estado para el filtro seleccionado.</td></tr>';
 renderPlatformDrillFilter();
}
function renderPlatformDrillFilter(){
 const parts=[];
 if($("state").value)parts.push(`Estado: ${prettyStatus($("state").value)}`);
 if($("category").value)parts.push(`Categoría: ${$("category").value}`);
 renderDrillFilter("platformDrillFilter",[...parts,...(platformEventDateFilter?[`Historial: ${platformEventDateFilter}`]:[])].join(" · "),()=>{
  $("state").value="";$("category").value="";$("freshFilter").value="";platformEventDateFilter="";render();renderPlatformEvents();renderPlatformAnalytics(cache,eventCache);
 });
}
function renderDrillFilter(targetId,label,onClear){
 const node=$(targetId);if(!node)return;
 node.innerHTML=label?`<span class="drill-filter-label"><b>Filtro activo</b> ${esc(label)}</span><button type="button" class="drill-filter-clear" data-clear-drill="${esc(targetId)}">Quitar filtro ×</button>`:"";
 if(label&&onClear)node._clearDrill=onClear;else node._clearDrill=null;
}
async function load(){try{const [sr,er,cr]=await Promise.all([fetch("/api/status"),fetch("/api/events?limit=100"),fetch("/api/config")]);if(!sr.ok||!er.ok||!cr.ok)throw new Error("API no disponible");const data=await sr.json(),events=await er.json(),config=await cr.json();cache=data.services;catalog=config.services;
 for(const k of ["operational","info","degraded","outage","maintenance","manual","unknown"])$(k).textContent=data.counts[k]??0;
 const automatic=cache.filter(s=>s.status!=="manual"&&s.checked_at);const stale=automatic.filter(s=>ageInfo(s).kind==="stale").length;$("stale").textContent=stale;
 const checks=automatic.map(s=>s.checked_at).filter(Boolean).sort();$("updated").textContent=checks.length?date(checks[checks.length-1]):"Aún no consultado";
 $("freshSummary").textContent=`${automatic.length} fuentes con consulta registrada · ${stale} con datos de 60 min o más · ${cache.filter(s=>s.status==="manual").length} requieren revisión manual`;
 const cats=[...new Set(config.services.map(s=>s.category||"General"))].sort(),old=$("category").value;$("category").innerHTML='<option value="">Todas las categorías</option>'+cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join("");$("category").value=cats.includes(old)?old:"";render();
 eventCache=events||[];renderPlatformEvents();renderPlatformAnalytics(cache,eventCache);
 }catch(e){$("services").innerHTML='<div class="loading">No se pudo conectar con el backend. Intenta nuevamente.</div>';$("freshSummary").textContent="No fue posible cargar los datos."}}
$("refresh").addEventListener("click",async()=>{$("refresh").disabled=true;$("refresh").textContent="Consultando fuentes…";try{const r=await fetch("/api/poll",{method:"POST"});const result=await r.json();if(!r.ok)throw new Error(result.detail||"Error");await load();await loadExecutiveDashboard();toast(`Consulta finalizada: ${result.success} fuentes con respuesta, ${result.errors} sin información y ${result.manual} para revisar manualmente.`)}catch(e){toast("No se pudo completar la consulta: "+e.message)}finally{$("refresh").disabled=false;$("refresh").textContent="↻ Actualizar ahora"}});
document.querySelectorAll(".metric-filter").forEach(card=>card.addEventListener("click",()=>{
 const key=card.dataset.filter;
 $("search").value="";
 if(key==="stale"){ const already=$("freshFilter").value==="stale" && !$("state").value; $("state").value=""; $("freshFilter").value=already?"":"stale"; }
 else { $("state").value=($("state").value===key && !$("freshFilter").value)?"":key; $("freshFilter").value=""; }
 render();
 document.querySelector("#services").scrollIntoView({behavior:"smooth",block:"start"});
}));
$("search").addEventListener("input",render);$("category").addEventListener("change",render);$("state").addEventListener("change",render);$("freshFilter").addEventListener("change",render);
function toast(t){$("toast").textContent=t;$("toast").classList.add("show");setTimeout(()=>$("toast").classList.remove("show"),4500)}
function tick(){$("clock").textContent=new Date().toLocaleTimeString("es-CL",{hour12:false})}tick();setInterval(tick,1000);load();

// ---------------------------------------------------------------------------
// SOC Global Threat Intelligence — Part 1: manually refreshed public news
// ---------------------------------------------------------------------------
let intelPeriod = "7d";
let intelCategory = "all";
let intelSource = "all";
let intelDateFilter = null;
let intelItems = [];
let intelSourceResults = [];
const intelCategoryNames = {
  global: "Noticias mundiales",
  ransomware: "Ransomware",
  espionage: "Espionaje",
  leaks: "Filtraciones",
  ddos: "DDoS",
  malware: "Malware",
  vulnerabilities: "Vulnerabilidades"
};

function renderIntelSourceFilter() {
  const select = $("intelSourceFilter");
  if (!select) return;
  const counts = new Map();
  intelItems.forEach(item => {
    const source = (item.source || "Fuente desconocida").trim();
    counts.set(source, (counts.get(source) || 0) + 1);
  });
  const names = new Set([
    ...intelSourceResults.map(item => item.source).filter(Boolean),
    ...counts.keys(),
    ...(intelSource !== "all" ? [intelSource] : [])
  ]);
  const sources = [...names].sort((a,b) => a.localeCompare(b, "es"));
  select.innerHTML = '<option value="all">Todas las fuentes</option>' + sources.map(name => {
    const count = counts.get(name) || 0;
    const state = intelSourceResults.find(item => item.source === name);
    const suffix = state && state.ok === false ? " · sin respuesta" : ` · ${count} noticias`;
    return `<option value="${esc(name)}">${esc(name)}${esc(suffix)}</option>`;
  }).join("");
  select.value = intelSource;
}

function renderNewsAnalytics(items) {
  $("intelChartWindow").textContent = intelPeriod === "24h" ? "ÚLTIMAS 24 HORAS" : "ÚLTIMOS 7 DÍAS";
  const timeline = intelPeriod === "24h"
    ? buildFourHourTimeline(items,"published_at")
    : buildDailyTimeline(items,"published_at",7);
  renderTimelineChart("intelTrendChart",timeline,{color:"#5daaf5",filterType:"intel-date",isActive:item=>intelDateFilter&&(intelDateFilter.start===Number(item.start||0)&&intelDateFilter.end===Number(item.end||0)||intelDateFilter.key===item.key),empty:"Sin publicaciones en el período seleccionado."});

  const categoryCounts={};
  const categoryLabels={ransomware:"Ransomware",espionage:"Espionaje",leaks:"Filtraciones",ddos:"DDoS",malware:"Malware",vulnerabilities:"Vulnerabilidades"};
  (items||[]).forEach(item=>{
    [...new Set(item.categories||[])].filter(key=>key!=="global").forEach(key=>{
      categoryCounts[key]=(categoryCounts[key]||0)+1;
    });
  });
  const categoryRows=Object.entries(categoryCounts).map(([key,value])=>({
    label:categoryLabels[key]||key,filterValue:key,value,color:{
      ransomware:"#e58a78",espionage:"#a98ae8",leaks:"#e7b45e",
      ddos:"#5ea8e9",malware:"#64c49c",vulnerabilities:"#c5a4ef"
    }[key]||"#5daaf5"
  }));
  renderHorizontalChart("intelCategoryChart",categoryRows,{filterType:"intel-category",isActive:item=>intelCategory===item.filterValue,empty:"No hay etiquetas temáticas en el filtro seleccionado."});

  const sourceCounts={};
  (items||[]).forEach(item=>{
    const name=item.source||"Fuente desconocida";
    sourceCounts[name]=(sourceCounts[name]||0)+1;
  });
  renderHorizontalChart("intelSourceChart",Object.entries(sourceCounts).map(([label,value])=>({label,value})),{
    color:"#39c99a",limit:9,filterType:"intel-source",isActive:item=>intelSource===item.label,empty:"No hay publicaciones para las fuentes seleccionadas."
  });
}

function renderIntelNews() {
  renderIntelSourceFilter();
  const chartItems = intelItems.filter(item =>
    (intelCategory === "all" || (item.categories || []).includes(intelCategory)) &&
    (intelSource === "all" || item.source === intelSource)
  );
  const visible = chartItems.filter(item => !intelDateFilter || (intelDateFilter.start && intelDateFilter.end
    ? new Date(item.published_at||0).getTime()>=intelDateFilter.start && new Date(item.published_at||0).getTime()<intelDateFilter.end
    : localDateKey(item.published_at)===intelDateFilter.key));
  $("intelCount").textContent = `${visible.length} publicaciones`;
  renderNewsAnalytics(chartItems);
  const dateLabel=intelDateFilter?(intelDateFilter.key||new Date(intelDateFilter.start).toLocaleString("es-CL")):"";
  renderDrillFilter("intelDrillFilter",[intelCategory!=="all"?`Tema: ${intelCategoryNames[intelCategory]||intelCategory}`:"",intelSource!=="all"?`Fuente: ${intelSource}`:"",dateLabel?`Fecha: ${dateLabel}`:""].filter(Boolean).join(" · "),()=>{intelCategory="all";intelSource="all";intelDateFilter=null;$("intelSourceFilter").value="all";renderIntelNews();});
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
    intelSourceResults = data.sources || [];
    $("intelLastRefresh").textContent = data.last_refresh
      ? `Última consulta: ${date(data.last_refresh)}`
      : "Sin actualización registrada";
    const totalSources = (data.sources || []).length || 9;
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
  $("intelSourceSummary").textContent = "Consultando nueve fuentes públicas en paralelo. Puede tardar varios segundos…";
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
    await loadExecutiveDashboard();
    if (!loaded) throw new Error("La consulta terminó, pero no fue posible recuperar las publicaciones guardadas.");
    const totalSources = (result.sources || []).length || 9;
    const successful = Number(result.successful_sources || 0);
    const failed = Number(result.failed_sources || 0);
    $("intelSourceSummary").textContent = `${result.ok === false ? "Consulta sin fuentes disponibles" : result.partial ? "Consulta parcial" : "Consulta completada"}: ${successful}/${totalSources} fuentes disponibles · ${failed} fallidas · ${result.fetched || 0} registros procesados.`;
    if (result.ok === false) toast("No respondió ninguna fuente RSS. Se conserva la última caché exitosa.");
    else toast(`Inteligencia actualizada: ${result.fetched || 0} publicaciones · ${successful}/${totalSources} fuentes disponibles.`);
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
    intelPeriod = button.dataset.period;intelDateFilter=null;
    loadIntelNews();
  });
});
document.querySelectorAll(".intel-category").forEach(button => {
  button.addEventListener("click", () => {
    intelCategory = button.dataset.intelCategory;
    renderIntelNews();
  });
});
$("intelSourceFilter").addEventListener("change", event => {
  intelSource = event.target.value || "all";
  renderIntelNews();
});

loadIntelNews();

// ---------------------------------------------------------------------------
// SOC Global Threat Intelligence — Part 2: ransomware claims and country map
// ---------------------------------------------------------------------------
let rwPeriod = "7d";
let rwDateFilter = null;
let rwItems = [];
let rwMapInstance = null;
let rwMapMarkers = null;

function rwUtcDate(value) {
  if (!value) return "Fecha no informada";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

function renderRansomwareSources(stats) {
  const sourceInfo = (stats || []);
  if (!sourceInfo.length) {
    $("rwSources").innerHTML = `
      <div class="rw-source-card"><b>RansomLook</b><span class="rw-source-pending">Pendiente de consulta</span></div>
      <div class="rw-source-card"><b>Ransomware.live</b><span class="rw-source-pending">Pendiente de consulta</span></div>`;
    $("rwSourceQueryTime").textContent = "Sin consulta registrada";
    return;
  }
  const definitions = [
    {name:"RansomLook", url:"https://www.ransomlook.io/recent", description:"Publicaciones individuales"},
    {name:"Ransomware.live", url:"https://www.ransomware.live/", description:"Indicadores agregados; sin filas individuales"}
  ];
  $("rwSources").innerHTML = definitions.map(def => {
    const item = sourceInfo.find(x => x.source === def.name) || {};
    const status = item.ok === true
      ? '<span class="rw-source-status ok">● Conectada</span>'
      : item.ok === false
        ? '<span class="rw-source-status fail">● Error de consulta</span>'
        : '<span class="rw-source-status pending">● Sin estado reciente</span>';
    const processed = Number(item.processed || 0);
    const rows = Number(item.rows_visible || 0);
    const groups = Number(item.groups_count || 0);
    const countries = Number(item.countries_count || 0);
    const detail = item.error ? `<p class="rw-source-error">${esc(item.error)}</p>` : "";
    return `<article class="rw-source-card">
      <div class="rw-source-card-head"><b><a href="${def.url}" target="_blank" rel="noopener noreferrer">${def.name} ↗</a></b>${status}</div>
      <p class="rw-source-purpose">${def.description}</p>
      <div class="rw-source-metrics">
        <div><small>Procesadas</small><strong>${processed.toLocaleString("es-CL")}</strong></div>
        <div><small>Filas visibles</small><strong>${rows.toLocaleString("es-CL")}</strong></div>
        <div><small>Grupos</small><strong>${groups.toLocaleString("es-CL")}</strong></div>
        <div><small>Países</small><strong>${countries.toLocaleString("es-CL")}</strong></div>
      </div>${detail}
    </article>`;
  }).join("");
  const stamp = sourceInfo.find(x => x.last_refresh)?.last_refresh;
  $("rwSourceQueryTime").textContent = stamp ? `Última actualización: ${date(stamp)}` : "Sin consulta registrada";
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
    const sourceCounts = country.source_counts || {};
    const rlook = Number(sourceCounts.RansomLook || 0);
    const rlive = Number(sourceCounts["Ransomware.live"] || 0);
    const mixed = rlook > 0 && rlive > 0;
    const fill = mixed ? "#a78bfa" : (rlive > 0 ? "#39c6a0" : "#c94765");
    const marker = L.circleMarker([Number(country.lat), Number(country.lon)], {
      radius, color: fill, weight: 1.5, opacity: .95,
      fillColor: fill, fillOpacity: .76
    });
    marker.bindPopup(`<b>${esc(country.name)}</b><br>Total: ${count} observación(es)<br>RansomLook: ${rlook}<br>Ransomware.live: ${rlive}`);
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
  $("rwCountryList").innerHTML = countries.length ? countries.slice(0, 8).map(country => {
    const sc=country.source_counts||{};
    return `<div class="rw-rank-item rw-rank-item-sources"><span>${esc(country.name)}<small>RansomLook ${Number(sc.RansomLook||0)} · Ransomware.live ${Number(sc["Ransomware.live"]||0)}</small></span><b>${Number(country.count || 0)}</b></div>`;
  }).join("")
    : '<span class="muted">No hay países asociados con confianza suficiente.</span>';
  const groups = data.top_groups || [];
  $("rwGroupList").innerHTML = groups.length ? groups.map(group => {
    const sc=group.source_counts||{};
    return `<div class="rw-rank-item rw-rank-item-sources"><span>${esc(group.name)}<small>RansomLook ${Number(sc.RansomLook||0)} · Ransomware.live ${Number(sc["Ransomware.live"]||0)}</small></span><b>${Number(group.count || 0)}</b></div>`;
  }).join("")
    : '<span class="muted">No hay grupos publicados en este período.</span>';
}

function renderRansomwareRows() {
  const term = $("rwSearch").value.trim().toLowerCase();
  const group = $("rwGroupFilter").value;
  const visible = rwItems.filter(item => {
    const haystack = `${item.victim || ""} ${item.group_name || ""} ${item.country_name || ""}`.toLowerCase();
    const stamp=new Date(item.discovered_at||"").getTime();
    const dateMatch=!rwDateFilter||(Number.isFinite(stamp)&&stamp>=rwDateFilter.start&&stamp<rwDateFilter.end);
    return (!term || haystack.includes(term)) && (!group || item.group_name === group) && dateMatch;
  });
  $("rwVisibleCount").textContent = `${visible.length} de ${Number(rwItems.length).toLocaleString("es-CL")} filas individuales`;
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
  }).join("") : '<tr><td colspan="6" class="rw-empty-cell">No hay publicaciones que coincidan con los filtros. Recuerda que Ransomware.live aporta conteos agregados y sus publicaciones individuales no se muestran aquí.</td></tr>';
  const filterLabel=[$("rwGroupFilter").value?`Grupo: ${$("rwGroupFilter").value}`:"",rwDateFilter?`Fecha: ${new Date(rwDateFilter.start).toLocaleString("es-CL")}`:""].filter(Boolean).join(" · ");
  renderDrillFilter("rwDrillFilter",filterLabel,()=>{$("rwGroupFilter").value="";rwDateFilter=null;renderRansomwareRows();});
}

function renderRansomwareAnalytics(data) {
  $("rwChartWindow").textContent = rwPeriod === "24h" ? "ÚLTIMAS 24 HORAS" : "ÚLTIMOS 7 DÍAS";
  renderTimelineChart("rwTimelineChart",data.timeline||[],{
    stacked:true,filterType:"rw-date",isActive:item=>rwDateFilter&&rwDateFilter.start===Number(item.start||0),empty:"No hay observaciones temporales en el período seleccionado."
  });
  const groups=(data.top_groups||[]).slice(0,8);
  const max=Math.max(1,...groups.map(x=>Number(x.count||0)));
  $("rwGroupChart").innerHTML=groups.length?groups.map(group=>{
    const total=Number(group.count||0), sc=group.source_counts||{};
    const look=Number(sc.RansomLook||0), live=Number(sc["Ransomware.live"]||0);
    const lookWidth=look/max*100, liveWidth=live/max*100;
    return `<button type="button" class="module-horizontal-row module-chart-drilldown${$("rwGroupFilter").value===group.name?" is-active":""}" data-chart-filter="rw-group" data-chart-value="${esc(group.name)}" aria-label="Filtrar publicaciones por grupo ${esc(group.name)}: ${total} observaciones">
      <div class="module-horizontal-label"><span>${esc(group.name)}</span><b>${total.toLocaleString("es-CL")}</b></div>
      <div class="module-horizontal-track module-stacked-track">
       <i class="rlook" title="RansomLook: ${look}" style="width:${lookWidth.toFixed(2)}%"></i>
       <i class="rlive" title="Ransomware.live: ${live}" style="width:${liveWidth.toFixed(2)}%"></i>
      </div>
      <small class="module-row-subtext">RansomLook ${look} · Ransomware.live ${live}</small>
    </button>`;
  }).join(""):'<span class="module-chart-empty">No hay grupos identificados en el período.</span>';
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
  renderRansomwareAnalytics(data);
  renderRansomwareMap(data.countries || []);
  renderRansomwareRows();
  renderRansomwareSources(data.source_stats || []);
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
  button.textContent = "Consultando ambas fuentes…";
  $("rwMapStatus").textContent = "Actualizando indicadores de ambas fuentes…";
  $("rwItems").innerHTML = '<tr><td colspan="6" class="rw-empty-cell">Consultando la fuente pública. Puede tardar unos segundos…</td></tr>';
  try {
    const response = await fetch("/api/threat-intel/ransomware/refresh", {
      method: "POST", cache: "no-store", headers: { "Accept": "application/json" }
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
    const loaded = await loadRansomware();
    await loadExecutiveDashboard();
    if (!loaded) throw new Error("La fuente respondió, pero no se pudo recuperar la caché local.");
    if (result.skipped) {
      toast(result.message || "Se reutilizó la caché reciente.");
    } else if (result.ok) {
      const sourceCounts = (result.sources || []).map(x => `${x.source}: ${Number(x.items || 0)} procesadas${x.ok ? "" : " (error)"}`).join(" · ");
      toast(`Actualización terminada. ${sourceCounts || "Revisa el estado de las fuentes."}`);
    } else {
      const reason = result.sources?.find(x => !x.ok)?.error || "La fuente no respondió correctamente.";
      $("rwMapStatus").textContent = "Última consulta con error; caché conservada";
      toast("No se pudo actualizar una o más fuentes: " + reason);
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
    rwPeriod = button.dataset.rwPeriod;rwDateFilter=null;
    loadRansomware();
  });
});
$("rwSearch").addEventListener("input", renderRansomwareRows);
$("rwGroupFilter").addEventListener("change", renderRansomwareRows);
loadRansomware();


// ---------------------------------------------------------------------------
// Fase 3 — interacción y navegación desde gráficos a registros
// ---------------------------------------------------------------------------
document.addEventListener("click",event=>{
 const clear=event.target.closest("[data-clear-drill]");
 if(clear){const node=$(clear.dataset.clearDrill);node?._clearDrill?.();return;}
 const control=event.target.closest("[data-chart-filter]");
 if(!control)return;
 const type=control.dataset.chartFilter,value=control.dataset.chartValue||"";
 if(type==="platform-status"){$("state").value=$("state").value===value?"":value;$("freshFilter").value="";render();renderPlatformAnalytics(cache,eventCache);document.querySelector("#services")?.scrollIntoView({behavior:"smooth",block:"start"});}
 else if(type==="platform-category"){$("category").value=$("category").value===value?"":value;render();renderPlatformAnalytics(cache,eventCache);document.querySelector("#services")?.scrollIntoView({behavior:"smooth",block:"start"});}
 else if(type==="platform-event-date"){platformEventDateFilter=platformEventDateFilter===value?"":value;renderPlatformEvents();document.querySelector("#events")?.closest(".table-wrap")?.scrollIntoView({behavior:"smooth",block:"start"});}
 else if(type==="intel-category"){intelCategory=intelCategory===value?"all":value;renderIntelNews();$("intelNewsList")?.scrollIntoView({behavior:"smooth",block:"start"});}
 else if(type==="intel-source"){intelSource=intelSource===value?"all":value;$("intelSourceFilter").value=intelSource;renderIntelNews();$("intelNewsList")?.scrollIntoView({behavior:"smooth",block:"start"});}
 else if(type==="intel-date"){
  const start=Number(control.dataset.chartStart||0),end=Number(control.dataset.chartEnd||0);
  const next=start&&end?{start,end}:{key:value};
  intelDateFilter=intelDateFilter&&((next.key&&intelDateFilter.key===next.key)||(next.start&&intelDateFilter.start===next.start))?null:next;
  renderIntelNews();$("intelNewsList")?.scrollIntoView({behavior:"smooth",block:"start"});
 }
 else if(type==="rw-group"){
  if(!rwItems.some(item=>item.group_name===value)){toast(`El grupo ${value} aparece en el agregado de fuentes, pero no tiene publicaciones individuales visibles en la tabla RansomLook.`);return;}
  $("rwGroupFilter").value=$("rwGroupFilter").value===value?"":value;renderRansomwareRows();$("rwItems")?.closest(".rw-table-wrap")?.scrollIntoView({behavior:"smooth",block:"start"});
 }
 else if(type==="rw-date"){
  const key=value;const providedStart=Number(control.dataset.chartStart||0),providedEnd=Number(control.dataset.chartEnd||0);const start=providedStart||Date.parse(key);
  if(Number.isFinite(start)&&start>0){const width=providedEnd>start?providedEnd-start:(rwPeriod==="24h"?4*60*60*1000:24*60*60*1000);rwDateFilter=rwDateFilter?.start===start?null:{start,end:start+width};renderRansomwareRows();$("rwItems")?.closest(".rw-table-wrap")?.scrollIntoView({behavior:"smooth",block:"start"});}
 }
 else if(type==="vuln-severity"||type==="vuln-epss"||type==="vuln-kev"){
  const filterType=type==="vuln-severity"?"severity":type==="vuln-epss"?"epss":"kev";
  vulnDrillFilter=vulnDrillFilter?.type===filterType&&vulnDrillFilter.value===value?null:{type:filterType,value};
  renderVulnerabilityTable();renderVulnerabilityAnalytics(vulnRowsCache);$("vulnRows")?.closest(".vuln-table-wrap")?.scrollIntoView({behavior:"smooth",block:"start"});
 }
});

// Vulnerability intelligence: CISA KEV, NVD and FIRST EPSS
let vulnRowsCache = [];
let vulnDrillFilter = null;
function renderVulnerabilityAnalytics(items) {
  const period=$("vulnPeriod").value||"30d";
  $("vulnChartWindow").textContent=period==="all"?"TODOS LOS ALMACENADOS":period==="7d"?"ÚLTIMOS 7 DÍAS + KEV":"30 DÍAS + KEV";
  const severityOrder=[
    {key:"CRITICAL",label:"Crítica",color:"#ef777d"},
    {key:"HIGH",label:"Alta",color:"#efaa67"},
    {key:"MEDIUM",label:"Media",color:"#e7c75d"},
    {key:"LOW",label:"Baja",color:"#55b9a0"},
    {key:"NONE",label:"Sin clasificación",color:"#7d91a8"}
  ];
  const severityCounts=Object.fromEntries(severityOrder.map(x=>[x.key,0]));
  const epss={low:0,medium:0,high:0,unknown:0};
  let kev=0;
  (items||[]).forEach(item=>{
    const key=String(item.severity||"NONE").toUpperCase();
    severityCounts[severityCounts[key]===undefined?"NONE":key]+=1;
    if(Number(item.kev))kev+=1;
    if(item.epss===null||item.epss===undefined||item.epss==="")epss.unknown+=1;
    else if(Number(item.epss)<0.1)epss.low+=1;
    else if(Number(item.epss)<0.5)epss.medium+=1;
    else epss.high+=1;
  });
  renderHorizontalChart("vulnSeverityChart",severityOrder.map(x=>({
    label:x.label,filterValue:x.key,value:severityCounts[x.key],color:x.color
  })),{filterType:"vuln-severity",isActive:item=>vulnDrillFilter?.type==="severity"&&vulnDrillFilter.value===item.filterValue,empty:"No hay CVE visibles para clasificar."});
  renderHorizontalChart("vulnEpssChart",[
    {label:"Alta · ≥ 50%",filterValue:"high",value:epss.high,color:"#ed8b82"},
    {label:"Media · 10–49,99%",filterValue:"medium",value:epss.medium,color:"#e9bb63"},
    {label:"Baja · < 10%",filterValue:"low",value:epss.low,color:"#55b9a0"},
    {label:"Sin puntaje EPSS",filterValue:"unknown",value:epss.unknown,color:"#7d91a8"}
  ],{filterType:"vuln-epss",isActive:item=>vulnDrillFilter?.type==="epss"&&vulnDrillFilter.value===item.filterValue,empty:"No hay puntajes EPSS en los registros visibles."});
  const known=(items||[]).length-kev;
  const ratio=(items||[]).length?kev/items.length*100:0;
  $("vulnKevChart").innerHTML=(items||[]).length?`
    <div class="kev-split-summary">
     <button type="button" class="kev-drill-card module-chart-drilldown${vulnDrillFilter?.type==="kev"&&vulnDrillFilter.value==="yes"?" is-active":""}" data-chart-filter="vuln-kev" data-chart-value="yes" aria-label="Filtrar CVE incluidas en CISA KEV"><strong>${kev.toLocaleString("es-CL")}</strong><span>Incluidas en CISA KEV · ${(ratio).toFixed(1)}%</span></button>
     <button type="button" class="kev-drill-card module-chart-drilldown${vulnDrillFilter?.type==="kev"&&vulnDrillFilter.value==="no"?" is-active":""}" data-chart-filter="vuln-kev" data-chart-value="no" aria-label="Filtrar CVE no incluidas en CISA KEV"><strong>${known.toLocaleString("es-CL")}</strong><span>No incluidas en KEV · ${(100-ratio).toFixed(1)}%</span></button>
    </div>
    <div class="kev-split-track"><i style="width:${ratio.toFixed(2)}%"></i></div>`
    :'<span class="module-chart-empty">No hay registros para comparar.</span>';
  $("vulnChartNote").textContent=`Distribución calculada sobre ${Number((items||[]).length).toLocaleString("es-CL")} registros visibles con el filtro actual. KEV significa que CISA incluyó la CVE en su catálogo de explotación conocida; no estar en KEV no prueba ausencia de explotación.`;
}

function getFilteredVulnerabilities(){
 if(!vulnDrillFilter)return vulnRowsCache;
 return vulnRowsCache.filter(item=>{
  if(vulnDrillFilter.type==="severity")return String(item.severity||"NONE").toUpperCase()===vulnDrillFilter.value;
  if(vulnDrillFilter.type==="kev")return Boolean(Number(item.kev))===(vulnDrillFilter.value==="yes");
  if(vulnDrillFilter.type==="epss"){
   if(item.epss===null||item.epss===undefined||item.epss==="")return vulnDrillFilter.value==="unknown";
   const value=Number(item.epss);
   return vulnDrillFilter.value==="low"?value<0.1:vulnDrillFilter.value==="medium"?value>=0.1&&value<0.5:value>=0.5;
  }
  return true;
 });
}
function renderVulnerabilityTable(){
 const visible=getFilteredVulnerabilities();
 const rows=visible.map(v=>{
  const cvss=v.cvss==null?"—":`${Number(v.cvss).toFixed(1)} · ${esc(v.severity||"")}`;
  const epss=v.epss==null?"—":`${(Number(v.epss)*100).toFixed(2)}%`;
  const kev=Number(v.kev)?`<span class="vuln-kev">Sí · ${esc(v.ransomware_use||"Unknown")}</span>`:"No";
  const publishedDate=v.published?new Date(v.published).toLocaleDateString("es-CL"):"—";
  const modifiedDate=v.modified?new Date(v.modified).toLocaleString("es-CL"):"No informada";
  const kevDate=v.kev_date?new Date(v.kev_date).toLocaleDateString("es-CL"):"—";
  return `<tr class="vuln-click-row" data-cve="${esc(v.cve)}" tabindex="0" role="button" aria-label="Abrir detalle de ${esc(v.cve)}"><td><button type="button" class="vuln-open" data-cve="${esc(v.cve)}">${esc(v.cve)}</button></td><td><b>${esc(v.title||v.cve)}</b><small>${esc([v.vendor,v.product].filter(Boolean).join(" · "))}</small><p>${esc(v.description||"")}</p><span class="vuln-row-hint">Ver ficha técnica y mitigaciones ↗</span></td><td>${cvss}</td><td>${epss}</td><td>${kev}</td><td>${esc(publishedDate)}</td><td><time datetime="${esc(v.modified||"")}">${esc(modifiedDate)}</time></td><td>${esc(kevDate)}</td><td><a href="${esc(v.source_url)}" target="_blank" rel="noopener" data-no-vuln-detail>NVD ↗</a></td></tr>`;
 }).join("");
 $("vulnRows").innerHTML=rows||'<tr><td colspan="9">No hay CVE que coincidan con el filtro del gráfico.</td></tr>';
 $("vulnCount").textContent=`${visible.length} / ${vulnRowsCache.length}`;
 const filterLabels={severity:`Severidad: ${vulnDrillFilter?.value||""}`,epss:`EPSS: ${vulnDrillFilter?.value||""}`,kev:`CISA KEV: ${vulnDrillFilter?.value==="yes"?"Sí":"No"}`};
 renderDrillFilter("vulnDrillFilter",vulnDrillFilter?filterLabels[vulnDrillFilter.type]:"",()=>{vulnDrillFilter=null;renderVulnerabilityTable();renderVulnerabilityAnalytics(vulnRowsCache);});
}

function renderVulnerabilities(data) {
  vulnRowsCache = data.items || [];
  renderVulnerabilityAnalytics(vulnRowsCache);
  $("vulnKevCount").textContent = data.kev_count || "—";
  $("vulnNvdCount").textContent = data.nvd_count || "—";
  $("vulnLastRefresh").textContent = data.last_refresh ? new Date(data.last_refresh).toLocaleString("es-CL") : "Pendiente";
  renderVulnerabilityTable();
}

function detailCell(value) {
  if (value === null || value === undefined || value === "") return "No informado";
  return esc(String(value).replaceAll("_", " "));
}
function renderVulnerabilityDetail(payload) {
  const v=payload.item||{}, d=payload.details||{}, nvd=d.nvd||{}, cisa=d.cisa||{}, cvss=nvd.cvss||{};
  const pct=x=>x==null?"No disponible":`${(Number(x)*100).toFixed(2)}%`;
  const kv=(label,value)=>`<tr><th>${esc(label)}</th><td>${detailCell(value)}</td></tr>`;
  const affected=(nvd.affected_products||[]).map(x=>{
    const limits=[
      x.version_start_including&&`desde ${x.version_start_including} (incl.)`,
      x.version_start_excluding&&`desde ${x.version_start_excluding} (excl.)`,
      x.version_end_including&&`hasta ${x.version_end_including} (incl.)`,
      x.version_end_excluding&&`hasta ${x.version_end_excluding} (excl.)`
    ].filter(Boolean).join(" · ");
    return `<tr><td><code>${esc(x.criteria||"Producto no identificado")}</code></td><td>${esc(limits||"Rango según CPE")}</td><td>${x.vulnerable?"Afectado":"Contexto"}</td></tr>`;
  }).join("");
  const weaknesses=(nvd.weaknesses||[]).concat(Array.isArray(cisa.cwes)?cisa.cwes:(cisa.cwes?[cisa.cwes]:[])).filter((x,i,a)=>a.indexOf(x)===i);
  const references=(nvd.references||[]).map(r=>`<li><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.source||r.url)}</a>${r.tags?.length?`<small>${esc(r.tags.join(" · "))}</small>`:""}</li>`).join("");
  const guidance=(d.workaround_guidance||[]).map(g=>{
    const extra=g.steps?.length?`<ol>${g.steps.map(x=>`<li>${esc(x)}</li>`).join("")}</ol>`:"";
    const links=g.references?.length?`<ul>${g.references.map(r=>`<li><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.source||r.url)}</a></li>`).join("")}</ul>`:"";
    return `<article class="vuln-guidance ${esc(g.kind)}"><h4>${esc(g.title)}</h4><p>${esc(g.text||"")}</p>${extra}${links}${g.source?`<small>Fuente: ${esc(g.source)}</small>`:""}</article>`;
  }).join("");
  $("vulnDetailTitle").textContent=`${v.cve||"Detalle de vulnerabilidad"} · ${v.title||""}`;
  $("vulnDetailSubtitle").textContent=[v.vendor,v.product].filter(Boolean).join(" · ")||"Ficha técnica de fuentes públicas";
  const kevBadge=Number(v.kev)?'<span class="vuln-tag danger">Incluida en CISA KEV</span>':'<span class="vuln-tag neutral">No figura en CISA KEV</span>';
  $("vulnDetailBody").innerHTML=`
    <div class="vuln-detail-top"><div><div class="vuln-tags"><span class="vuln-tag severity">${esc(v.severity||"Severidad no informada")}${v.cvss!=null?` · CVSS ${Number(v.cvss).toFixed(1)}`:""}</span>${kevBadge}</div><p>${esc(v.description||cisa.short_description||"La fuente no publicó una descripción.")}</p><div class="vuln-detail-date">Publicación: ${esc(v.published?new Date(v.published).toLocaleString("es-CL"):"No informada")} · Modificación: ${esc(v.modified?new Date(v.modified).toLocaleString("es-CL"):"No informada")}</div></div><a class="portal-btn" href="${esc(v.source_url||`https://nvd.nist.gov/vuln/detail/${encodeURIComponent(v.cve||"")}`)}" target="_blank" rel="noopener noreferrer">Abrir ficha NVD ↗</a></div>
    <div class="vuln-detail-kpis">
      <div><small>CVSS · Severidad técnica</small><b>${v.cvss==null?"—":Number(v.cvss).toFixed(1)}</b><span>${esc(v.severity||"Sin puntuación")}</span></div>
      <div><small>EPSS · Probabilidad 30 días</small><b>${pct(v.epss)}</b><span>Percentil ${pct(v.epss_percentile)}</span></div>
      <div><small>Explotación conocida</small><b>${Number(v.kev)?"Sí · KEV":"No registrada"}</b><span>Ransomware: ${esc(v.ransomware_use||"No informado")}</span></div>
    </div>
    ${d.lookup_note?`<div class="vuln-detail-lookup-note">${esc(d.lookup_note)}</div>`:""}
    <section class="vuln-detail-section"><h3>Indicadores técnicos</h3><div class="vuln-detail-table-wrap"><table class="vuln-detail-table"><tbody>
      ${kv("Versión CVSS",cvss.version)}${kv("Vector CVSS",cvss.vector)}${kv("Vector de ataque",cvss.attack_vector)}${kv("Complejidad",cvss.attack_complexity)}${kv("Privilegios requeridos",cvss.privileges_required)}${kv("Interacción del usuario",cvss.user_interaction)}${kv("Alcance",cvss.scope)}${kv("Impacto confidencialidad",cvss.confidentiality_impact)}${kv("Impacto integridad",cvss.integrity_impact)}${kv("Impacto disponibilidad",cvss.availability_impact)}${kv("Debilidades CWE",weaknesses.join(", "))}${kv("Estado NVD",nvd.cve_status)}${kv("Fecha alta KEV",cisa.date_added||v.kev_date)}${kv("Fecha límite CISA",cisa.due_date)}${kv("Uso en campañas ransomware",cisa.known_ransomware_campaign_use||v.ransomware_use)}
    </tbody></table></div></section>
    <section class="vuln-detail-section"><h3>Productos y versiones afectadas</h3>${affected?`<div class="vuln-detail-table-wrap"><table class="vuln-detail-table"><thead><tr><th>CPE / Producto</th><th>Rango de versión</th><th>Tipo</th></tr></thead><tbody>${affected}</tbody></table></div>`:'<p class="muted">NVD no entregó configuraciones CPE para esta CVE. Revisa el aviso del fabricante para confirmar las versiones afectadas.</p>'}</section>
    ${cisa.required_action||cisa.notes?`<section class="vuln-detail-section"><h3>Información CISA KEV</h3>${cisa.required_action?`<div class="vuln-official-action"><b>Acción requerida</b><p>${esc(cisa.required_action)}</p></div>`:""}${cisa.notes?`<p>${esc(cisa.notes)}</p>`:""}</section>`:""}
    <section class="vuln-detail-section"><h3>Mitigación y posibles workaround</h3>${guidance||'<p class="muted">No hay recomendaciones disponibles en caché. Actualiza las fuentes y revisa las referencias oficiales.</p>'}</section>
    <section class="vuln-detail-section"><h3>Referencias y advisories</h3><ul class="vuln-reference-list">${references||"<li>No hay referencias adicionales publicadas por NVD.</li>"}</ul></section>
    <div class="vuln-detail-disclaimer">La ficha resume información pública de NVD, CISA KEV y FIRST EPSS. EPSS estima probabilidad, no confirma explotación. Las medidas orientativas no sustituyen las instrucciones del fabricante ni una validación del entorno.</div>`;
}
async function openVulnerabilityDetail(cve){
  $("vulnDetailDialog").showModal();
  $("vulnDetailTitle").textContent="Consultando ficha técnica…";
  $("vulnDetailSubtitle").textContent=cve;
  $("vulnDetailBody").innerHTML='<div class="loading">Recuperando indicadores NVD, CISA KEV y EPSS…</div>';
  try{
    const response=await fetch(`/api/threat-intel/vulnerabilities/${encodeURIComponent(cve)}`,{cache:"no-store"});
    const payload=await response.json();
    if(!response.ok)throw new Error(payload.detail||`HTTP ${response.status}`);
    renderVulnerabilityDetail(payload);
  }catch(e){$("vulnDetailBody").innerHTML=`<div class="vuln-detail-error">No se pudo recuperar la ficha: ${esc(e.message)}. Actualiza las fuentes públicas e inténtalo otra vez.</div>`;}
}
$("closeVulnDetail").addEventListener("click",()=>$("vulnDetailDialog").close());
$("vulnDetailDialog").addEventListener("click",event=>{if(event.target===$("vulnDetailDialog"))$("vulnDetailDialog").close();});
async function loadVulnerabilities() {
  const period = $("vulnPeriod").value;
  const search = $("vulnSearch").value.trim();
  const sort = $("vulnSort").value || "modified_desc";
  try {
    const response = await fetch(`/api/threat-intel/vulnerabilities?period=${encodeURIComponent(period)}&search=${encodeURIComponent(search)}&sort=${encodeURIComponent(sort)}`, {cache:"no-store"});
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
    await loadExecutiveDashboard();
    const partialNote = result.partial ? " · Resultado parcial: revisa el diagnóstico de fuentes." : "";
    $("vulnMessage").textContent = `${result.partial ? "Actualización parcial" : "Actualizado"}: ${result.kev_count} registros CISA KEV · ${result.nvd_count} CVE NVD · ${result.epss_enriched} enriquecidas con EPSS.${partialNote}`;
    toast(result.partial ? "Actualización parcial de vulnerabilidades. Consulta el diagnóstico de fuentes." : "Inteligencia de vulnerabilidades actualizada.");
  } catch(e) {
    $("vulnMessage").textContent = "Error al actualizar: " + e.message + ". Se conserva la caché anterior.";
    toast("No se pudo actualizar vulnerabilidades: " + e.message);
  } finally { button.disabled = false; button.textContent = "↻ Actualizar vulnerabilidades"; }
});
$("vulnPeriod").addEventListener("change", () => {vulnDrillFilter=null;loadVulnerabilities();});
$("vulnSort").addEventListener("change", loadVulnerabilities);
let vulnSearchTimer;
$("vulnSearch").addEventListener("input", () => { clearTimeout(vulnSearchTimer); vulnSearchTimer = setTimeout(loadVulnerabilities, 250); });
document.addEventListener("click",event=>{
  const button=event.target.closest(".vuln-open");
  const row=event.target.closest(".vuln-click-row");
  if(event.target.closest("[data-no-vuln-detail]"))return;
  const cve=button?.dataset.cve||row?.dataset.cve;
  if(cve)openVulnerabilityDetail(cve);
});
document.addEventListener("keydown",event=>{
  if((event.key==="Enter"||event.key===" ")&&event.target.classList?.contains("vuln-click-row")){
    event.preventDefault();openVulnerabilityDetail(event.target.dataset.cve);
  }
});
loadVulnerabilities();

// v1.8.1: módulo de inicio y navegación por tarjetas
const moduleTitles={platforms:"Estado de plataformas",news:"Ataques y amenazas publicados",ransomware:"Ransomware tracker y mapa geográfico",vulns:"Vulnerability Intelligence"};
function setActiveNavigation(name){
  document.querySelectorAll(".soc-nav-item[data-nav]").forEach(item=>{
    const active=item.dataset.nav===name;
    item.classList.toggle("active",active);
    if(active)item.setAttribute("aria-current","page");
    else item.removeAttribute("aria-current");
  });
}
function closeMobileSidebar(){
  $("appShell").classList.remove("mobile-sidebar-open");
  $("mobileMenuToggle").setAttribute("aria-expanded","false");
}
function showHome(){
  $("moduleHome").hidden=false;
  $("moduleNav").hidden=true;
  document.querySelectorAll(".module-view").forEach(v=>v.hidden=true);
  setActiveNavigation("home");
  closeMobileSidebar();
  window.scrollTo({top:0,behavior:"smooth"});
}
function showModule(name){
  if(!moduleTitles[name])return;
  $("moduleHome").hidden=true;
  $("moduleNav").hidden=false;
  document.querySelectorAll(".module-view").forEach(v=>v.hidden=true);
  const view=$("view-"+name); if(view) view.hidden=false;
  $("activeModuleName").textContent=moduleTitles[name];
  setActiveNavigation(name);
  closeMobileSidebar();
  window.scrollTo({top:0,behavior:"smooth"});
  if(name==="ransomware" && rwMapInstance) setTimeout(()=>rwMapInstance.invalidateSize(),220);
  if(name==="ransomware" && !rwItems.length) loadRansomware();
}
document.querySelectorAll(".soc-nav-item[data-nav]").forEach(item=>{
  item.addEventListener("click",()=>{
    const target=item.dataset.nav;
    if(target==="home")showHome();
    else showModule(target);
  });
});
$("sidebarCollapse").addEventListener("click",()=>{
  $("appShell").classList.toggle("sidebar-collapsed");
});
$("mobileMenuToggle").addEventListener("click",()=>{
  const opened=$("appShell").classList.toggle("mobile-sidebar-open");
  $("mobileMenuToggle").setAttribute("aria-expanded",String(opened));
});
$("sidebarScrim").addEventListener("click",closeMobileSidebar);
document.addEventListener("keydown",event=>{
  if(event.key==="Escape")closeMobileSidebar();
});
async function runGlobalRefresh() {
  const button = $("homeRefresh");
  const summary = $("homeRefreshSummary");
  if (button.disabled) return;
  button.disabled = true;
  button.textContent = "Actualizando los cuatro módulos…";
  summary.textContent = "Consultando plataformas, noticias, ransomware y vulnerabilidades en paralelo.";

  const jobs = [
    { key: "platforms", label: "Plataformas", url: "/api/poll" },
    { key: "news", label: "Noticias", url: "/api/threat-intel/news/refresh" },
    { key: "ransomware", label: "Ransomware", url: "/api/threat-intel/ransomware/refresh" },
    { key: "vulnerabilities", label: "Vulnerabilidades", url: "/api/threat-intel/vulnerabilities/refresh" }
  ];

  const results = await Promise.all(jobs.map(async job => {
    try {
      const response = await fetch(job.url, {
        method: "POST",
        cache: "no-store",
        headers: { "Accept": "application/json" }
      });
      let payload;
      try { payload = await response.json(); }
      catch { throw new Error(`HTTP ${response.status}: respuesta no válida`); }
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      const successful = payload.ok !== false;
      const failureMessage = job.key === "platforms"
        ? "Ninguna fuente automática de plataformas respondió correctamente."
        : job.key === "news"
          ? "Ninguna fuente RSS respondió correctamente."
          : job.key === "ransomware"
            ? (payload.sources?.find(source => !source.ok)?.error || "Ninguna fuente ransomware respondió correctamente.")
            : "La actualización no se completó.";
      return { ...job, ok: successful, error: successful ? null : failureMessage, payload };
    } catch (error) {
      return { ...job, ok: false, error: error.message };
    }
  }));

  // Each view is refreshed from its own cache, even if another source failed.
  const reloads = await Promise.allSettled([
    load(),
    loadIntelNews(),
    loadRansomware(),
    loadVulnerabilities()
  ]);

  const byKey = Object.fromEntries(results.map(item => [item.key, item]));
  const platform = byKey.platforms;
  const news = byKey.news;
  const ransom = byKey.ransomware;
  const vulns = byKey.vulnerabilities;

  const platformErrors = Number(platform.payload?.errors || 0);
  const platformText = platform.ok
    ? `${Number(platform.payload.success || 0)} con respuesta · ${platformErrors} con error · ${Number(platform.payload.manual || 0)} manuales`
    : `Error: ${platform.error || "sin respuesta válida"}`;
  const platformState = !platform.ok ? "error" : (platformErrors ? "parcial" : "completo");
  const newsTotal = Number(news.payload?.sources?.length || 0);
  const newsGood = Number(news.payload?.successful_sources || 0);
  const newsText = news.ok
    ? `${newsGood}/${newsTotal} fuentes RSS respondieron`
    : `Error: ${news.error || "ninguna fuente respondió"}`;
  const newsState = !news.ok || !newsGood ? "error" : (newsGood < newsTotal ? "parcial" : "completo");
  const ransomGood = Number(ransom.payload?.successful_sources || 0);
  const ransomTotal = Number(ransom.payload?.sources?.length || 0);
  const ransomText = ransom.ok
    ? (ransom.payload?.skipped
        ? `Caché reutilizada · ${ransomGood}/${ransomTotal} fuentes disponibles`
        : `${ransomGood}/${ransomTotal} fuentes respondieron`)
    : `Error: ${ransom.error || "ninguna fuente respondió"}`;
  const ransomState = !ransom.ok || !ransomGood ? "error" : (ransomGood < ransomTotal ? "parcial" : "completo");
  const vulnText = vulns.ok
    ? `${Number(vulns.payload.kev_count || 0)} CISA KEV · ${Number(vulns.payload.nvd_count || 0)} NVD · ${Number(vulns.payload.epss_enriched || 0)} EPSS`
    : `Error: ${vulns.error || "fuentes no disponibles"}`;
  const vulnState = !vulns.ok ? "error" : (vulns.payload?.partial ? "parcial" : "completo");

  const states = [platformState, newsState, ransomState, vulnState];
  await loadExecutiveDashboard();
  const reloadErrors = reloads.filter(item => item.status === "rejected").length;
  const summaryParts = [
    `Plataformas: ${platformText} [${platformState}]`,
    `Noticias: ${newsText} [${newsState}]`,
    `Ransomware: ${ransomText} [${ransomState}]`,
    `Vulnerabilidades: ${vulnText} [${vulnState}]`
  ];
  const completedCount = states.filter(state => state === "completo").length;
  const partialCount = states.filter(state => state === "parcial").length;
  const failedCount = states.filter(state => state === "error").length;
  const completedAt = new Date().toLocaleTimeString("es-CL");
  summary.textContent = `Última actualización global (${completedAt}) · ${completedCount}/4 completos · ${partialCount} parciales · ${failedCount} con error. ${summaryParts.join(" | ")}`;
  summary.classList.toggle("has-errors", partialCount > 0 || failedCount > 0 || reloadErrors > 0);
  if (partialCount || failedCount || reloadErrors) {
    toast(`Actualización finalizada con resultados parciales. ${completedCount} completos, ${partialCount} parciales y ${failedCount} con error.`);
  } else {
    toast("Actualización global completada. Los cuatro módulos y sus fuentes respondieron.");
  }

  button.disabled = false;
  button.textContent = "↻ Actualizar todos los módulos";
}
$("homeRefresh").addEventListener("click", runGlobalRefresh);


// ---------------------------------------------------------------------------
// v1.9.0 Phase 1 — SOC Executive Dashboard (cache-backed summary)
// ---------------------------------------------------------------------------
const execStatusLabels = {
  operational: "Operativas", info: "Avisos", degraded: "Degradadas",
  outage: "Indisponibles", maintenance: "Mantenimiento",
  manual: "Consulta manual", unknown: "Sin información"
};
const execStatusColors = {
  operational: "#35c99a", info: "#5daaf5", degraded: "#efbd5d",
  outage: "#ef777d", maintenance: "#9b8be9", manual: "#8796aa",
  unknown: "#56677b"
};
const execCategoryLabels = {
  ransomware: "Ransomware", espionage: "Espionaje", leaks: "Filtraciones",
  ddos: "DDoS", malware: "Malware", vulnerabilities: "Vulnerabilidades"
};
const execNumber = value => Number(value || 0).toLocaleString("es-CL");
const execTime = value => value ? date(value) : "Sin actualización";

function renderExecPlatformChart(platforms) {
  const counts = platforms.counts || {};
  const keys = ["operational","info","degraded","outage","maintenance","manual","unknown"];
  const total = Number(platforms.total || 0);
  $("execPlatformDonutTotal").textContent = execNumber(total);
  if (!total) {
    $("execPlatformDonut").style.background = "conic-gradient(#27384c 0 100%)";
    $("execPlatformLegend").innerHTML = '<span class="exec-empty">No hay estados almacenados. Actualiza el módulo de plataformas.</span>';
    $("execPlatformNote").textContent = "El catálogo está disponible, pero todavía no hay resultados de consulta.";
    return;
  }
  let cursor = 0;
  const segments = [];
  keys.forEach(key => {
    const value = Number(counts[key] || 0);
    if (!value) return;
    const start = cursor;
    cursor += value / total * 100;
    segments.push(`${execStatusColors[key]} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`);
  });
  $("execPlatformDonut").style.background = `conic-gradient(${segments.join(",")})`;
  $("execPlatformLegend").innerHTML = keys.map(key => {
    const value = Number(counts[key] || 0);
    if (!value) return "";
    const pct = (value / total * 100).toFixed(0);
    return `<div class="exec-legend-row"><i style="background:${execStatusColors[key]}"></i><span>${execStatusLabels[key]}</span><b>${execNumber(value)}</b><small>${pct}%</small></div>`;
  }).join("");
  $("execPlatformNote").textContent =
    `${execNumber(platforms.stale)} plataformas automáticas con datos de 60 minutos o más · ${execNumber(platforms.manual)} requieren revisión manual.`;
}

function renderExecBars(targetId, values, labels, color) {
  const node = $(targetId);
  const entries = Object.entries(values || {})
    .map(([key,value]) => ({key, label:labels[key] || key, count:Number(value || 0)}))
    .sort((a,b) => b.count - a.count);
  const max = Math.max(1, ...entries.map(x => x.count));
  const nonzero = entries.filter(x => x.count > 0);
  if (!nonzero.length) {
    node.innerHTML = '<span class="exec-empty">Sin registros en la ventana consultada.</span>';
    return;
  }
  node.innerHTML = nonzero.map(item => {
    const width = Math.max(2, item.count / max * 100);
    return `<div class="exec-bar-row">
      <div class="exec-bar-label"><span>${esc(item.label)}</span><b>${execNumber(item.count)}</b></div>
      <div class="exec-bar-track"><i style="width:${width.toFixed(1)}%;background:${color}"></i></div>
    </div>`;
  }).join("");
}

function renderExecRankList(targetId, items, keyName) {
  const node = $(targetId);
  if (!items || !items.length) {
    node.innerHTML = '<span class="exec-empty">Sin ubicaciones identificadas.</span>';
    return;
  }
  node.innerHTML = items.slice(0,5).map(item => {
    const label = item.name || item.country_name || item[keyName] || "No identificado";
    const count = Number(item.count || 0);
    return `<div class="exec-rank-row"><span>${esc(label)}</span><b>${execNumber(count)}</b></div>`;
  }).join("");
}

function renderExecModuleStatus(data) {
  const entries = [
    {name:"Estado de plataformas", stamp:data.platforms.latest_check, detail:`${execNumber(data.platforms.total)} servicios · ${execNumber(data.platforms.stale)} datos antiguos`, state:data.platforms.latest_check?"Datos disponibles":"Pendiente"},
    {name:"Ataques y amenazas", stamp:data.news.last_refresh, detail:`${execNumber(data.news.sources_ok)}/${execNumber(data.news.sources_total)} fuentes RSS respondieron`, state:data.news.last_refresh?"Caché disponible":"Pendiente"},
    {name:"Ransomware tracker", stamp:data.ransomware.last_refresh, detail:`${execNumber(data.ransomware.sources_ok)}/${execNumber(data.ransomware.sources_total)} fuentes consultadas`, state:data.ransomware.last_refresh?"Caché disponible":"Pendiente"},
    {name:"Vulnerability Intelligence", stamp:data.vulnerabilities.last_refresh, detail:`${execNumber(data.vulnerabilities.kev_count)} registros KEV · ${execNumber(data.vulnerabilities.nvd_count)} NVD`, state:data.vulnerabilities.last_refresh?"Caché disponible":"Pendiente"}
  ];
  $("execModuleStatus").innerHTML = entries.map(item => `
    <div class="exec-status-item">
      <div class="exec-status-name"><i class="${item.stamp?"is-ready":"is-pending"}"></i><b>${esc(item.name)}</b></div>
      <span>${esc(item.detail)}</span>
      <small>${esc(item.stamp ? execTime(item.stamp) : item.state)}</small>
    </div>`).join("");
}

function renderExecutiveDashboard(data) {
  const p = data.platforms || {}, n = data.news || {}, r = data.ransomware || {}, v = data.vulnerabilities || {};
  $("execSnapshot").textContent = `Resumen consultado: ${execTime(data.generated_at)}`;
  $("execGeneratedAt").textContent = `Actualizado: ${execTime(data.generated_at)}`;

  $("execPlatformsTotal").textContent = execNumber(p.total);
  $("execPlatformsFoot").textContent = `${execNumber(p.counts?.operational || 0)} operativas · ${execNumber(p.counts?.degraded || 0)} degradadas · ${execNumber(p.counts?.outage || 0)} indisponibles`;
  $("execNewsTotal").textContent = execNumber(n.count);
  $("execNewsFoot").textContent = `${execNumber(n.sources_ok)}/${execNumber(n.sources_total)} fuentes respondieron · 7 días`;
  $("execRansomTotal").textContent = execNumber(r.processed);
  $("execRansomFoot").textContent = `${execNumber(r.groups_count)} grupos · ${execNumber(r.countries_count)} países identificados`;
  $("execKevTotal").textContent = execNumber(v.kev_count);
  $("execKevFoot").textContent = `${execNumber(v.visible)} registros en vista 30 días + KEV`;

  renderExecPlatformChart(p);
  renderExecBars("execThreatBars", n.categories, execCategoryLabels, "#5daaf5");
  $("execThreatNote").textContent = `${execNumber(n.count)} noticias publicadas en los últimos 7 días. Una noticia puede tener varias etiquetas.`;

  $("execRansomCountries").textContent = execNumber(r.countries_count);
  $("execRansomGroups").textContent = execNumber(r.groups_count);
  $("execRansomVisible").textContent = execNumber(r.listed);
  renderExecRankList("execTopGroups", r.top_groups, "name");
  renderExecRankList("execTopCountries", r.top_countries, "name");
  $("execRansomNote").textContent = `${execNumber(r.processed)} observaciones procesadas por las fuentes; ${execNumber(r.listed)} filas individuales visibles. Son publicaciones, no incidentes confirmados.`;

  renderExecBars("execVulnBars", v.severity, {
    CRITICAL:"Crítica", HIGH:"Alta", MEDIUM:"Media", LOW:"Baja", OTHER:"Otra / sin clasificación"
  }, "#b18af0");
  $("execEpssHigh").textContent = execNumber(v.epss_50_plus);
  $("execNvdCount").textContent = execNumber(v.nvd_count);
  renderExecModuleStatus(data);
}

function healthStateLabel(state) {
  return ({healthy:"Correcto",partial:"Parcial",error:"Error",stale:"Antiguo",pending:"Pendiente",warning:"Última consulta falló"})[state] || "Sin estado";
}
function healthTime(value) {
  return value ? new Date(value).toLocaleString("es-CL") : "Sin consulta exitosa";
}
function renderHealthDiagnostics(data) {
  const labels = {platforms:"Plataformas",news:"Noticias",ransomware:"Ransomware",vulnerabilities:"Vulnerabilidades"};
  const overall = data.overall || "pending";
  const badge = $("execHealthBadge");
  badge.textContent = healthStateLabel(overall);
  badge.className = `health-badge ${overall}`;
  const modules = data.modules || {};
  const allSources = Object.values(modules).flatMap(module => module.sources || []);
  const healthy = allSources.filter(x => x.status === "healthy").length;
  const failed = allSources.filter(x => x.status === "error").length;
  const stale = allSources.filter(x => x.status === "stale").length;
  const warnings = allSources.filter(x => x.status === "warning").length;
  const pending = allSources.filter(x => x.status === "pending").length;
  $("execHealthSummary").innerHTML = [
    [healthy,"Fuentes correctas","healthy"],[warnings+failed,"Con errores recientes","error"],
    [stale,"Datos antiguos","stale"],[pending,"Pendientes","pending"]
  ].map(([value,label,state]) => `<div class="exec-health-kpi ${state}"><b>${execNumber(value)}</b><span>${label}</span></div>`).join("");
  $("execHealthModules").innerHTML = Object.entries(labels).map(([key,label]) => {
    const module = modules[key] || {};
    const sources = module.sources || [];
    const sourceRows = sources.map(source => `<div class="exec-health-source">
      <span class="health-dot ${esc(source.status || "pending")}"></span>
      <span class="exec-health-source-name">${esc(source.source || source.name || "Fuente")}</span>
      <span class="exec-health-source-state">${esc(healthStateLabel(source.status))}</span>
      <small>${esc(source.last_success ? healthTime(source.last_success) : (source.checked_at ? `Intento: ${healthTime(source.checked_at)}` : "Sin consulta registrada"))}</small>
      ${source.error ? `<em title="${esc(source.error)}">${esc(source.error)}</em>` : ""}
    </div>`).join("");
    return `<details class="exec-health-module"><summary><span>${esc(label)}</span><b class="health-badge ${esc(module.status || "pending")}">${esc(healthStateLabel(module.status))}</b><small>${execNumber(module.healthy)}/${execNumber(sources.length)} fuentes correctas${module.manual ? ` · ${execNumber(module.manual)} manuales` : ""}</small></summary>
      <div class="exec-health-source-list">${sourceRows || '<span class="exec-empty">Todavía no existen resultados de consulta.</span>'}</div></details>`;
  }).join("");
  const runs = data.recent_refreshes || [];
  $("execRefreshHistory").innerHTML = runs.length ? runs.map(run => `<div class="exec-refresh-run"><span class="health-dot ${run.ok ? "healthy" : "error"}"></span><b>${esc(labels[run.module] || run.module)}</b><span>${esc(run.summary || "")}</span><small>${esc(healthTime(run.attempted_at))}</small></div>`).join("") : '<span class="exec-empty">Todavía no hay actualizaciones manuales registradas.</span>';
  $("execPersistenceWarning").textContent = data.database?.warning || "No fue posible determinar la persistencia de los datos.";
}

async function loadExecutiveDashboard() {
  const [summaryResult, healthResult] = await Promise.allSettled([
    fetch("/api/executive-summary", {cache:"no-store"}),
    fetch("/api/health", {cache:"no-store"})
  ]);
  let loaded = false;
  try {
    if (summaryResult.status !== "fulfilled") throw summaryResult.reason;
    const response = summaryResult.value;
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    renderExecutiveDashboard(data);
    loaded = true;
  } catch (error) {
    $("execSnapshot").textContent = `No se pudo cargar el resumen: ${error.message}`;
    $("execModuleStatus").innerHTML = '<span class="exec-empty">El resumen ejecutivo no está disponible. Los módulos individuales siguen funcionando.</span>';
  }
  try {
    if (healthResult.status !== "fulfilled") throw healthResult.reason;
    const response = healthResult.value;
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    renderHealthDiagnostics(data);
  } catch (error) {
    $("execHealthBadge").textContent = "No disponible";
    $("execHealthBadge").className = "health-badge error";
    $("execHealthSummary").innerHTML = `<span class="exec-empty">No se pudo consultar el diagnóstico: ${esc(error.message)}</span>`;
    $("execHealthModules").innerHTML = "";
  }
  return loaded;
}

loadExecutiveDashboard();
