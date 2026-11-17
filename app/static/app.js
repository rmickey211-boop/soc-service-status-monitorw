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
 const comps=(live.components||[]).map(c=>`<div class="detail-row"><div><b>${esc(c.name)}</b>${c.description?`<small>${esc(c.description)}</small>`:""}</div><span class="pill ${esc(c.status)}">${esc(prettyStatus(c.status))}</span></div>`).join("");
 const incidents=(live.incidents||[]).map(i=>`<article class="detail-incident"><div class="detail-row"><b>${esc(i.name||"Incidente")}</b><span class="pill ${esc(i.impact||i.status||"unknown")}">${esc(prettyStatus(i.impact||i.status||"unknown"))}</span></div><small>Inicio: ${esc(detailDate(i.created_at))} · Actualización: ${esc(detailDate(i.updated_at))}</small>${i.locations?`<p><b>Ubicaciones:</b> ${esc(i.locations)}</p>`:""}${i.body?`<p>${esc(i.body)}</p>`:""}${(i.updates||[]).map(u=>`<div class="detail-update"><b>${esc(u.status||"Actualización")}</b> · ${esc(detailDate(u.created_at||u.display_at))}<p>${esc(u.body||"")}</p></div>`).join("")}</article>`).join("");
 const maint=(live.maintenances||[]).map(m=>`<article class="detail-incident"><b>${esc(m.name)}</b><small>${esc(m.status)} · ${esc(detailDate(m.scheduled_for))} – ${esc(detailDate(m.scheduled_until))}</small>${(m.updates||[]).map(u=>`<p>${esc(u.body)}</p>`).join("")}</article>`).join("");
 const screenshotUrl="https://s.wordpress.com/mshots/v1/"+encodeURIComponent(s.base_url)+"?w=1400&v="+Date.now();
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
  <section class="detail-section screenshot-section"><div class="screenshot-heading"><div><h3>Imagen actual del portal oficial</h3><p>Captura generada bajo demanda mediante un servicio externo. Puede tardar unos segundos o no estar disponible si el portal bloquea capturas.</p></div><a class="portal-btn" href="${esc(s.base_url)}" target="_blank" rel="noopener noreferrer">Abrir portal ↗</a></div>
   <div class="screenshot-frame"><div class="screenshot-loading" id="screenshotLoading">Generando captura del portal…</div><img id="portalScreenshot" src="${esc(screenshotUrl)}" alt="Captura reciente del portal ${esc(s.name)}" loading="lazy" referrerpolicy="no-referrer"><div id="screenshotError" class="screenshot-error" hidden>No fue posible generar la imagen del portal. Utiliza el botón «Abrir portal» para consultar la fuente original.</div></div>
  </section>
  <div class="detail-footer"><span>Los estados corresponden a fuentes públicas y no necesariamente reflejan el tenant o instancia particular de tu organización.</span><a class="portal-btn" href="${esc(s.base_url)}" target="_blank" rel="noopener noreferrer">${esc(s.portal_label||"Abrir portal oficial")} ↗</a></div>`;
 const img=$("portalScreenshot"), loading=$("screenshotLoading"), err=$("screenshotError");
 img.addEventListener("load",()=>{loading.hidden=true;img.classList.add("loaded")},{once:true});
 img.addEventListener("error",()=>{loading.hidden=true;err.hidden=false;img.hidden=true},{once:true});
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

async function load(){try{const [sr,er,cr,kr]=await Promise.all([fetch("/api/status"),fetch("/api/events?limit=100"),fetch("/api/config"),fetch("/api/checklist?limit=50")]);if(!sr.ok||!er.ok||!cr.ok||!kr.ok)throw new Error("API no disponible");const data=await sr.json(),events=await er.json(),config=await cr.json(),runs=await kr.json();cache=data.services;catalog=config.services;
 for(const k of ["operational","info","degraded","outage","maintenance","manual","unknown"])$(k).textContent=data.counts[k]??0;
 const automatic=cache.filter(s=>s.status!=="manual"&&s.checked_at);const stale=automatic.filter(s=>ageInfo(s).kind==="stale").length;$("stale").textContent=stale;
 const checks=automatic.map(s=>s.checked_at).filter(Boolean).sort();$("updated").textContent=checks.length?date(checks[checks.length-1]):"Aún no consultado";
 $("freshSummary").textContent=`${automatic.length} fuentes con consulta registrada · ${stale} con datos de 60 min o más · ${cache.filter(s=>s.status==="manual").length} requieren revisión manual`;
 const cats=[...new Set(config.services.map(s=>s.category||"General"))].sort(),old=$("category").value;$("category").innerHTML='<option value="">Todas las categorías</option>'+cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join("");$("category").value=cats.includes(old)?old:"";render();renderChecklistOptions();
 $("events").innerHTML=events.length?events.map(e=>`<tr><td>${date(e.occurred_at)}</td><td><b>${esc(e.service_name)}</b></td><td class="change">${labels[e.old_status]||e.old_status} → ${labels[e.new_status]||e.new_status}</td><td>${esc(e.description)}</td></tr>`).join(""):'<tr><td colspan="4">Sin cambios de estado registrados.</td></tr>';
 $("checkHistory").innerHTML=runs.length?runs.map(r=>{let ids=[];try{ids=JSON.parse(r.checked_services)}catch{};const names=ids.map(id=>catalog.find(s=>s.id===id)?.name||id);const cp={inicio:"Inicio",intermedio:"Intermedio",termino:"Término"}[r.checkpoint]||r.checkpoint;return `<tr><td>${date(r.created_at)}</td><td>${esc(r.analyst)}</td><td>${esc(r.shift_name)}</td><td>${esc(cp)}</td><td>${esc(names.slice(0,6).join(", ")+(names.length>6?` y ${names.length-6} más`:"")||"—")}</td><td>${esc(r.notes||"—")}</td></tr>`}).join(""):'<tr><td colspan="6">Sin revisiones registradas.</td></tr>';
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