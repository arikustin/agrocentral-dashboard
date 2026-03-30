import psycopg2
import psycopg2.extras
import os
from flask import Flask, jsonify, make_response, redirect, request, Response
import db

app = Flask(__name__)

USERS = {
    "ariel":    os.environ.get("PASS_ARIEL",  "agrocentral2026"),
    "jere":     os.environ.get("PASS_JERE",   "jere2026"),
    "ale":      os.environ.get("PASS_ALE",    "ale2026"),
}

DASH_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AGROCENTRAL — Dashboard Competencia</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,sans-serif;background:#f0f4f0;color:#222}
.hdr{background:linear-gradient(135deg,#1a5c30,#2e7d32);color:#fff;
  padding:14px 24px;display:flex;align-items:center;
  justify-content:space-between;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.hdr h1{font-size:1.2rem}
.hdr .sub{font-size:.78rem;opacity:.8;margin-top:2px}
.btn-upd{background:#fff;color:#1a5c30;border:none;padding:9px 20px;
  border-radius:6px;font-size:.88rem;font-weight:bold;cursor:pointer;transition:all .2s}
.btn-upd:hover{background:#e8f5e9;transform:translateY(-1px)}
.btn-upd:disabled{opacity:.5;cursor:not-allowed;transform:none}
.prog-wrap{background:#c8e6c9;height:4px;display:none}
.prog-bar{background:#1a5c30;height:4px;transition:width .4s}
.prog-msg{background:#e8f5e9;padding:7px 24px;font-size:.78rem;color:#2e7d32;display:none}
.kpis{display:flex;gap:12px;padding:16px 24px 0;flex-wrap:wrap}
.kpi{background:#fff;border-radius:10px;padding:12px 18px;flex:1;min-width:130px;
  box-shadow:0 1px 4px rgba(0,0,0,.08);border-left:4px solid #ccc}
.kpi.t{border-color:#1565c0}.kpi.v{border-color:#2e7d32}
.kpi.a{border-color:#f9a825}.kpi.r{border-color:#c62828}.kpi.g{border-color:#9e9e9e}
.kv{font-size:1.9rem;font-weight:bold;line-height:1}
.kl{font-size:.72rem;color:#666;margin-top:3px}
.kpi.t .kv{color:#1565c0}.kpi.v .kv{color:#2e7d32}
.kpi.a .kv{color:#f9a825}.kpi.r .kv{color:#c62828}.kpi.g .kv{color:#9e9e9e}
.filters{padding:12px 24px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.filters input,.filters select{padding:7px 11px;border:1px solid #ccc;
  border-radius:6px;font-size:.83rem;outline:none}
.filters input{width:260px}
.filters input:focus,.filters select:focus{border-color:#2e7d32}
.tw{padding:0 24px 24px;overflow-x:auto}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
  overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);font-size:.81rem}
thead tr{background:#2e7d32;color:#fff}
th{padding:10px 11px;text-align:left;font-weight:600;white-space:nowrap;
  cursor:pointer;user-select:none}
th:hover{background:#1a5c30}
td{padding:8px 11px;border-bottom:1px solid #f0f0f0;vertical-align:middle}
tr:hover td{background:#f9fbf9}
tr:last-child td{border-bottom:none}
.dot{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:middle}
.dot.verde{background:#2e7d32}.dot.amarillo{background:#f9a825}
.dot.rojo{background:#c62828}.dot.gris{background:#9e9e9e}
.tag{display:inline-block;padding:2px 7px;border-radius:11px;font-size:.7rem;font-weight:bold;white-space:nowrap}
.me2c{background:#e8f5e9;color:#1b5e20}.me2f{background:#c8e6c9;color:#1b5e20}
.me1{background:#fff9c4;color:#f57f17}.me2fu{background:#a5d6a7;color:#1b5e20}
.cust{background:#ffe0b2;color:#e65100}
.dp{color:#2e7d32;font-weight:bold}.dn{color:#c62828;font-weight:bold}
.dy{color:#f9a825;font-weight:bold}
.bdet{background:#e8f5e9;color:#1a5c30;border:1px solid #a5d6a7;
  padding:4px 9px;border-radius:5px;font-size:.73rem;cursor:pointer;white-space:nowrap}
.bdet:hover{background:#c8e6c9}
.btab{background:#e3f2fd;color:#1565c0;border:1px solid #90caf9;
  padding:4px 9px;border-radius:5px;font-size:.73rem;cursor:pointer;white-space:nowrap}
.btab:hover{background:#bbdefb}
.ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);
  z-index:1000;align-items:center;justify-content:center}
.ov.open{display:flex}
.modal{background:#fff;border-radius:12px;width:90%;max-width:880px;
  max-height:86vh;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,.3)}
.mhdr{background:#1a5c30;color:#fff;padding:15px 20px;border-radius:12px 12px 0 0;
  display:flex;justify-content:space-between;align-items:flex-start}
.mhdr h2{font-size:.95rem;max-width:88%}
.mcls{background:none;border:none;color:#fff;font-size:1.3rem;cursor:pointer}
.mbdy{padding:18px}
.mpbox{background:#e8f5e9;border:1px solid #a5d6a7;border-radius:8px;padding:13px 15px;margin-bottom:16px}
.mpbox h3{color:#1a5c30;font-size:.82rem;margin-bottom:8px}
.mpgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:7px}
.mplbl{font-size:.7rem;color:#666}.mpval{font-size:.92rem;font-weight:bold;color:#1a5c30}
.csec h3{font-size:.82rem;color:#555;margin-bottom:9px;
  border-bottom:1px solid #eee;padding-bottom:5px}
.cc{border:1px solid #e0e0e0;border-radius:8px;padding:11px 13px;margin-bottom:9px}
.cc.exacto{border-left:4px solid #1565c0}.cc.equivalente{border-left:4px solid #f9a825}
.cc.mas-barato{background:#fff8e1;border:2px solid #f9a825}
.cc.mucho-mas-barato{background:#ffebee;border:2px solid #c62828}
.cc.mas-caro{background:#f1f8e9;border-left:4px solid #2e7d32}
.precio-alerta{background:#c62828;color:#fff;padding:2px 8px;border-radius:10px;
  font-size:.72rem;font-weight:bold;margin-left:6px}
.precio-ok{background:#2e7d32;color:#fff;padding:2px 8px;border-radius:10px;
  font-size:.72rem;font-weight:bold;margin-left:6px}
.cct{font-size:.8rem;font-weight:bold;margin-bottom:5px}
.cct a{color:#1565c0;text-decoration:none}
.cct a:hover{text-decoration:underline}
.cmeta{display:flex;gap:12px;flex-wrap:wrap;align-items:center;font-size:.77rem;color:#555}
.cprice{font-size:.98rem;font-weight:bold;color:#1a5c30}
.crep{font-size:.73rem;margin-top:5px}
.rd{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:3px}
.r5{background:#2e7d32}.r4{background:#7cb342}.r3{background:#f9a825}
.r2{background:#ef6c00}.r1{background:#c62828}
.empty{text-align:center;padding:50px 20px;color:#999}
.empty .ic{font-size:2.8rem;margin-bottom:10px}
.ftr{text-align:center;padding:10px;font-size:.73rem;color:#aaa}
</style>
</head>
<body>
<div class="hdr">
  <div>
    <h1>🌿 AGROCENTRAL — Dashboard de Competencia</h1>
    <div class="sub">Comparacion de precios y calidad vs competidores · MercadoLibre Argentina
  &nbsp;·&nbsp; <span id="current-user" style="opacity:.8;font-size:.75rem"></span>
  &nbsp;<a href="/logout" style="color:#a5d6a7;font-size:.73rem;text-decoration:none">[salir]</a>
</div>
  </div>
  <div style="text-align:right">
    <div id="lu" style="font-size:.73rem;opacity:.7;margin-bottom:5px"></div>
    <button class="btn-upd" id="bup" onclick="handleUpdateBtn()">🔄 Actualizar ahora</button>
  <button class="btn-upd" id="bpause" onclick="triggerPause()"
    style="display:none;background:#fff3cd;color:#856404;margin-left:8px">
    ⏸ Pausar y guardar</button>
  </div>
</div>
<div class="prog-wrap" id="pw"><div class="prog-bar" id="pb" style="width:0%"></div></div>
<div class="prog-msg" id="pm"></div>
<div class="kpis">
  <div class="kpi t"><div class="kv" id="kt">—</div><div class="kl">Publicaciones</div></div>
  <div class="kpi v"><div class="kv" id="kv">—</div><div class="kl">🟢 Precio competitivo</div></div>
  <div class="kpi a"><div class="kv" id="ka">—</div><div class="kl">🟡 Precio similar</div></div>
  <div class="kpi r"><div class="kv" id="kr">—</div><div class="kl">🔴 Precio alto</div></div>
  <div class="kpi g"><div class="kv" id="kg">—</div><div class="kl">⚪ Sin competidores</div></div>
</div>
<div class="filters">
  <input type="text" id="sq" placeholder="Buscar producto o SKU..." oninput="ft()">
  <select id="fsem" onchange="ft()">
    <option value="">Todos los estados</option>
    <option value="verde">🟢 Competitivo</option>
    <option value="amarillo">🟡 Similar</option>
    <option value="rojo">🔴 Precio alto</option>
    <option value="gris">⚪ Sin datos</option>
  </select>
  <select id="fenv" onchange="ft()">
    <option value="">Todos los envios</option>
    <option value="ME2 Colecta">ME2 Colecta</option>
    <option value="ME2 Flex">ME2 Flex</option>
    <option value="ME2 Full">ME2 Full</option>
    <option value="ME1">ME1</option>
  </select>
  <button id="btnGroup" onclick="toggleGroup()"
    style="background:#e8f5e9;color:#1a5c30;border:1px solid #a5d6a7;
           padding:7px 14px;border-radius:6px;font-size:.83rem;cursor:pointer">
    📁 Agrupar por SKU</button>
  <button onclick="exportExcel()"
    style="background:#1a5c30;color:#fff;border:none;
           padding:7px 14px;border-radius:6px;font-size:.83rem;cursor:pointer">
    📥 Exportar Excel</button>
  <label id="lc" style="margin-left:auto;color:#888;font-size:.78rem"></label>
</div>
<div class="tw">
<table id="mt">
  <thead><tr>
    <th onclick="st('semaforo')">Estado</th>
    <th onclick="st('sku')">SKU</th>
    <th onclick="st('title')">Publicacion</th>
    <th onclick="st('price')">Mi Precio</th>
    <th onclick="st('min_comp')">Min Comp.</th>
    <th onclick="st('diff_vs_min')">Dif %</th>
    <th onclick="st('envio_tipo')">Envio</th>
    <th onclick="st('quien_paga')">Paga envio</th>
    <th onclick="st('comision')">Comision</th>
    <th onclick="st('sold_quantity')">Vendidos</th>
    <th>Detalle</th>
  </tr></thead>
  <tbody id="tb">
    <tr><td colspan="11"><div class="empty">
      <div class="ic">📊</div>
      <p id="empty-msg">Cargando datos...</p>
      <script>fetch('/api/status').then(r=>r.json()).then(s=>{
        if(s.cloud_mode) document.getElementById('empty-msg').textContent='Los datos se actualizan desde la PC de Ariel.';
        else document.getElementById('empty-msg').innerHTML='Presiona <strong>Actualizar ahora</strong> para cargar los datos.';
      });</script>
    </div></td></tr>
  </tbody>
</table>
</div>
<div class="ov" id="ov">
  <div class="modal">
    <div class="mhdr"><h2 id="mt2">Detalle</h2>
      <button class="mcls" onclick="cm()">✕</button></div>
    <div class="mbdy" id="mb"></div>
  </div>
</div>
<div class="ftr" id="ftr"></div>

<script>
let items=[],sk='diff_vs_min',sd=1,poll=null;
const fp=(n,d=0)=>n==null?'—':new Intl.NumberFormat('es-AR',{minimumFractionDigits:d,maximumFractionDigits:d}).format(n);
const fpp=n=>n==null?'—':'$ '+fp(n,2);
function etag(t){
  const m={'ME2 Colecta':'me2c','ME2 Flex':'me2f','ME2 Full':'me2fu','ME1':'me1','Custom (Axado)':'cust'};
  return `<span class="tag ${m[t]||'cust'}">${t}</span>`;
}
function rdot(l){
  const m={'5_green':'5','4_light_green':'4','3_yellow':'3','2_orange':'2','1_red':'1'};
  return `<span class="rd r${m[l]||'3'}"></span>`;
}
function diffH(p){
  if(p==null) return '—';
  const c=p<-5?'dp':p>5?'dn':'dy', s=p>0?'+':'';
  return `<span class="${c}">${s}${p.toFixed(1)}%</span>`;
}
async function loadData(){
  const r=await fetch('/api/data'); const d=await r.json();
  if(!d.items||!d.items.length) return;
  items=d.items.map(it=>({...it,
    diff_vs_min:(it.price&&it.min_comp)?((it.price-it.min_comp)/it.min_comp*100):null,
    revisado: it.competidores!==undefined && it.competidores!==null}));
  if(d.last_update)
    document.getElementById('lu').textContent=
      'Ultima actualizacion: '+new Date(d.last_update).toLocaleString('es-AR');
  updKPI(); render();
}
function updKPI(){
  const c={verde:0,amarillo:0,rojo:0,gris:0};
  items.forEach(i=>c[i.semaforo||'gris']++);
  document.getElementById('kt').textContent=items.length;
  document.getElementById('kv').textContent=c.verde;
  document.getElementById('ka').textContent=c.amarillo;
  document.getElementById('kr').textContent=c.rojo;
  document.getElementById('kg').textContent=c.gris;
}
function gf(){
  const q=document.getElementById('sq').value.toLowerCase();
  const fs=document.getElementById('fsem').value;
  const fe=document.getElementById('fenv').value;
  return items.filter(it=>
    (!q||it.title.toLowerCase().includes(q)||(it.sku||'').toLowerCase().includes(q))&&
    (!fs||it.semaforo===fs)&&(!fe||(it.envio_tipo||'').includes(fe)));
}
function st(k){if(sk===k)sd*=-1;else{sk=k;sd=1;}render();}
function ft(){render();}

// P2: agrupamiento por SKU
let groupBySKU = false;
function toggleGroup(){
  groupBySKU=!groupBySKU;
  const btn=document.getElementById('btnGroup');
  btn.textContent=groupBySKU?'📂 Desagrupar SKU':'📁 Agrupar por SKU';
  btn.style.background=groupBySKU?'#e3f2fd':'#e8f5e9';
  btn.style.color=groupBySKU?'#1565c0':'#1a5c30';
  render();
}

function render(){
  const its=gf();
  document.getElementById('lc').textContent=`${its.length} de ${items.length} publicaciones`;
  its.sort((a,b)=>{
    if(groupBySKU){
      const sa=(a.sku||'').localeCompare(b.sku||'');
      if(sa!==0) return sa;
    }
    let va=a[sk],vb=b[sk];
    if(va==null)return 1;if(vb==null)return -1;
    return(typeof va==='string'?va.localeCompare(vb):va-vb)*sd;
  });
  const tb=document.getElementById('tb');
  if(!its.length){
    tb.innerHTML=`<tr><td colspan="11"><div class="empty">
      <div class="ic">🔍</div><p>Sin resultados.</p></div></td></tr>`;
    return;
  }
  // P2: renderizar con grupos de SKU
  let html='', lastSKU='';
  its.forEach(it=>{
    const rev=reviews[it.id];
    const revIcon=rev
      ?`<div style="font-size:.68rem;color:#1a5c30;line-height:1.2">
          ✅ ${rev.usuario}<br>
          <span style="color:#888">${rev.fecha}</span>
        </div>`
      :'<span title="Sin revisar" style="color:#f9a825;font-size:.8rem">⏳</span>';
    if(groupBySKU && it.sku && it.sku!==lastSKU){
      const grp=its.filter(x=>x.sku===it.sku);
      lastSKU=it.sku;
      html+=`<tr style="background:#e8f5e9;cursor:pointer"
        onclick="toggleSKUGroup('${it.sku}')">
        <td colspan="11" style="padding:6px 12px;font-weight:bold;color:#1a5c30;font-size:.82rem">
          📁 SKU: ${it.sku} &nbsp;·&nbsp; ${grp.length} publicaci${grp.length===1?'ón':'ones'}
          &nbsp;<span style="font-size:.75rem;color:#666">(clic para expandir/colapsar)</span>
        </td>
      </tr>`;
    }
    const rowStyle=groupBySKU?`class="sku-row sku-${(it.sku||'noskU').replace(/[^a-zA-Z0-9]/g,'_')}" style="display:none"`:''
    html+=`<tr ${rowStyle}>
      <td data-item-id="${it.id}">${revIcon}${!rev?` <span class="dot ${it.semaforo||'gris'}"></span>`:'' }</td>
      <td style="font-family:monospace;font-size:.73rem;color:#555">${it.sku||'—'}</td>
      <td style="max-width:250px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
          title="${it.title}">${it.title}</td>
      <td style="text-align:right;font-weight:bold;color:#1a5c30">${fpp(it.price)}</td>
      <td style="text-align:right;color:#555">${it.min_comp?fpp(it.min_comp):'—'}</td>
      <td style="text-align:center">${diffH(it.diff_vs_min)}</td>
      <td>${etag(it.envio_tipo)}</td>
      <td style="font-size:.76rem;color:${it.quien_paga==='Vendedor'?'#c62828':'#2e7d32'}">${it.quien_paga}</td>
      <td style="text-align:right;color:#555;font-size:.76rem">${it.comision?fpp(it.comision):'—'}</td>
      <td style="text-align:center;color:#555">${it.sold_quantity||0}</td>
      <td><button class="bdet" onclick="openM('${it.id}')">Ver competidores</button></td>
    </tr>`;
  });
  tb.innerHTML=html;
  // Si no agrupado, mostrar todo
  if(!groupBySKU){
    tb.querySelectorAll('tr').forEach(r=>r.style.display='');
  }
}
async function openM(id){
  const r=await fetch('/api/item/'+id); const it=await r.json();
  if(!it.id) return;
  document.getElementById('mt2').textContent=it.title;

  // Registrar revisión
  await fetch('/api/review/'+id, {method:'POST'});
  reviews[id] = {
    usuario: currentUser,
    fecha: new Date().toLocaleString('es-AR')
  };
  // Actualizar ícono en la tabla
  const revCells = document.querySelectorAll(`[data-item-id="${id}"]`);
  revCells.forEach(cell=>{
    cell.innerHTML = `✅ <span class="dot ${it.semaforo||'gris'}"></span>
      <div style="font-size:.65rem;color:#1a5c30;line-height:1.1">
        ${currentUser}<br>${new Date().toLocaleString('es-AR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}
      </div>`;
  });
  const semL={verde:'🟢 Precio competitivo',amarillo:'🟡 Precio similar',
               rojo:'🔴 Hay competidores mas baratos',gris:'⚪ Sin datos'};
  let h=`<div class="mpbox">
    <h3>📦 Mi publicacion — ${it.listing_name||it.listing_type_id}</h3>
    <div class="mpgrid">
      <div><div class="mplbl">Precio</div><div class="mpval">${fpp(it.price)}</div></div>
      <div><div class="mplbl">Tipo envio</div><div class="mpval">${it.envio_tipo}</div></div>
      <div><div class="mplbl">Paga envio</div>
        <div class="mpval" style="color:${it.quien_paga==='Vendedor'?'#c62828':'#2e7d32'}">${it.quien_paga}</div></div>
      <div><div class="mplbl">Costo envio</div>
        <div class="mpval">${it.costo_envio!=null?fpp(it.costo_envio):'Pendiente'}</div></div>
      <div><div class="mplbl">Comision ML</div><div class="mpval">${fpp(it.comision)}</div></div>
      <div><div class="mplbl">Vendidos</div><div class="mpval">${it.sold_quantity||0}</div></div>
    </div>
    <div style="margin-top:9px;font-size:.79rem;font-weight:bold">
      Estado: ${semL[it.semaforo]||'—'}</div>
  </div>
  <div class="csec">
    <h3>🏪 Top ${it.competidores?.length||0} competidores</h3>`;

  // Verificar si hay algun competidor EXACTO
  const hayExacto = it.competidores && it.competidores.some(c=>c.match_type==='exacto');
  const hayMasBarato = it.competidores && it.competidores.some(c=>(c.diff_pct||0)<0);

  if(!it.competidores||!it.competidores.length){
    h+=`<div class="empty" style="padding:25px">
      <p>No se encontraron competidores para este producto.</p></div>`;
  } else {
    // Banner "SOS EL MAS BARATO" si no hay exacto mas barato
    if(!hayExacto&&!hayMasBarato){
      h+=`<div style="background:linear-gradient(135deg,#1a5c30,#2e7d32);
            color:#fff;border-radius:10px;padding:14px 18px;margin-bottom:14px;
            text-align:center;font-weight:bold;font-size:.95rem;">
        🏆 SOS EL PRECIO MÁS BARATO en marca y modelo
        <div style="font-size:.78rem;opacity:.85;margin-top:4px;font-weight:normal">
          No hay ningún competidor exacto con precio inferior al tuyo
        </div>
      </div>`;
    } else if(!hayExacto&&hayMasBarato){
      h+=`<div style="background:#fff8e1;border:2px solid #f9a825;
            border-radius:10px;padding:12px 16px;margin-bottom:14px;
            text-align:center;font-size:.88rem;">
        ⚠️ <strong>No hay competidores exactos</strong>, pero hay productos equivalentes más baratos
      </div>`;
    }

    it.competidores.forEach((c,i)=>{
       const inf=c.seller_info||{};
       const dp=c.diff_pct;
       let ccClass=c.match_type;
       let priceBadge='';
       if(dp!=null){
         if(dp<=-20){ccClass+=' mucho-mas-barato';priceBadge=`<span class="precio-alerta">⚠️ ${dp}% más barato</span>`;}
         else if(dp<0){ccClass+=' mas-barato';priceBadge=`<span class="precio-alerta">${dp}% más barato</span>`;}
         else if(dp>0){ccClass+=' mas-caro';priceBadge=`<span class="precio-ok">+${dp}% más caro que vos</span>`;}
       }
       const ml=c.match_type==='exacto'
         ?'<span style="color:#1565c0;font-size:.7rem;font-weight:bold">● Mismo producto</span>'
         :'<span style="color:#f9a825;font-size:.7rem">◐ Producto equivalente</span>';
       const nivel=inf.level||'';
       const nivelLabel={'5_green':'🟢 Excelente','4_light_green':'🟢 Muy bueno',
         '3_yellow':'🟡 Bueno','2_orange':'🟠 Regular','1_red':'🔴 Bajo'}[nivel]||nivel||'Sin nivel';
       const ps=inf.power_seller;
       const psLabel=ps==='platinum'?'⭐ ML Platinum':ps==='gold'?'🥇 ML Gold':ps==='silver'?'🥈 ML Silver':'Sin ML';
       const califPos=inf.calif_positiva!=null?inf.calif_positiva+'% pos':'—';
       const califNeg=inf.calif_negativa!=null&&inf.calif_negativa>0?' / '+inf.calif_negativa+'% neg':'';
       const tiendaOf=inf.tienda_oficial?'🏪 Tienda Oficial &nbsp;·&nbsp; ':''
       const ventasTot=inf.ventas_completadas||inf.ventas_totales||0;
       const reg=inf.registrado?`Desde ${inf.registrado.substring(0,7)}`:''; 
       // Boton tablero: solo si el competidor es mas barato que yo
       const tabBtn=dp!=null&&dp<0
         ?`<button class="btab" style="float:right;margin-top:4px"
             onclick="sendToBoard('${c.id}','${it.id}',${c.price})"
             title="Enviar precio de este competidor al tablero">
             📋 Enviar al tablero</button>`
         :'';
       h+=`<div class="cc ${ccClass}">
         <div class="cct">
           ${i+1}. <a href="${c.link}" target="_blank">${c.title}</a>
           &nbsp;${ml}&nbsp;${priceBadge}
           <span style="float:right;font-size:.7rem;color:#aaa">Similitud: ${c.similarity}%</span>
         </div>
         <div class="cmeta" style="margin:6px 0">
           <span class="cprice">${fpp(c.price)}</span>
           ${dp!=null?`<span class="${dp<0?'dp':dp>0?'dn':'dy'}">${dp>0?'+':''} ${dp}% vs mi precio</span>`:''}
           <span>${etag(c.logistic_type||'—')}</span>
           <span style="color:${c.free_shipping?'#2e7d32':'#555'}">
             ${c.free_shipping?'✅ Envío gratis':'📦 Comprador paga'}</span>
           <span>🛒 <strong>${c.sold_quantity||0}</strong> vendidos</span>
           ${c.available_quantity!=null?`<span>📦 <strong>${c.available_quantity}</strong> en stock</span>`:''}
         </div>
         <div class="crep" style="margin-top:6px;padding-top:6px;border-top:1px solid #eee">
           ${tabBtn}
           <strong>${c.seller_name||'—'}</strong>&nbsp;
           <span style="font-size:.75rem">${tiendaOf}${nivelLabel} &nbsp;·&nbsp; ${psLabel}</span><br>
           <span style="font-size:.73rem;color:#555">
             👍 ${califPos}${califNeg}
             &nbsp;·&nbsp; 📦 ${fp(ventasTot)} ventas
             ${reg?'&nbsp;·&nbsp; 📅 '+reg:''}
           </span>
         </div>
       </div>`;
     });
  }
  h+=`</div>`;
  document.getElementById('mb').innerHTML=h;
  document.getElementById('ov').classList.add('open');
}
function cm(){document.getElementById('ov').classList.remove('open');}
function toggleSKUGroup(sku){
  const safe=sku.replace(/[^a-zA-Z0-9]/g,'_');
  const rows=document.querySelectorAll('.sku-'+safe);
  const visible=rows.length>0&&rows[0].style.display!=='none';
  rows.forEach(r=>r.style.display=visible?'none':'');
}
function sendToBoard(compId, myItemId, compPrice){
  // Funcionalidad pendiente: enviar precio de competencia al tablero
  const msg = `Precio de competidor enviado al tablero:\\n` +
    `Competidor ID: ${compId}\\n` +
    `Mi publicacion: ${myItemId}\\n` +
    `Precio competidor: $${compPrice}`;
  alert(msg);
  // TODO: implementar envío real al tablero
}
document.getElementById('ov').addEventListener('click',e=>{
  if(e.target===document.getElementById('ov'))cm();});
function handleUpdateBtn(){
  fetch('/api/status').then(r=>r.json()).then(s=>{
    if(s.cloud_mode){
      const lu = s.last_update ? new Date(s.last_update).toLocaleString('es-AR') : 'desconocida';
      alert('Modo nube activo\\n\\nUltima actualizacion: ' + lu + '\\n\\nPara actualizar, ejecutar en la PC de Ariel:\\n1. agrocentral_dashboard.py\\n2. agrocentral_uploader.py');
    } else {
      triggerUpdate();
    }
  });
}

async function triggerUpdate(){
  const b=document.getElementById('bup');
  const bp=document.getElementById('bpause');
  b.disabled=true; b.textContent='⏳ Actualizando...';
  bp.style.display='inline-block';
  await fetch('/api/update',{method:'POST'});
  startPoll();
}
async function triggerPause(){
  const r=await fetch('/api/pause',{method:'POST'});
  const d=await r.json();
  if(d.ok){
    document.getElementById('bpause').textContent='⏳ Pausando...';
    document.getElementById('bpause').disabled=true;
  }
}
function startPoll(){
  clearInterval(poll);
  document.getElementById('pw').style.display='block';
  document.getElementById('pm').style.display='block';
  poll=setInterval(pollSt,1500);
}
async function pollSt(){
  const r=await fetch('/api/status'); const s=await r.json();
  document.getElementById('pb').style.width=s.progress+'%';
  document.getElementById('pm').textContent=s.message;
  if(s.status==='done'||s.status==='paused'){
    clearInterval(poll);
    document.getElementById('pw').style.display='none';
    document.getElementById('pm').style.display='none';
    document.getElementById('bup').disabled=false;
    document.getElementById('bup').textContent=s.status==='paused'?'🔄 Reanudar':'🔄 Actualizar ahora';
    document.getElementById('bpause').style.display='none';
    document.getElementById('bpause').disabled=false;
    document.getElementById('bpause').textContent='⏸ Pausar y guardar';
    loadData();
  } else if(s.status==='error'){
    clearInterval(poll);
    document.getElementById('pm').textContent='❌ '+s.message;
    document.getElementById('bup').disabled=false;
    document.getElementById('bup').textContent='🔄 Reintentar';
    document.getElementById('bpause').style.display='none';
  }
}
let currentUser = "";
let reviews = {};

async function loadReviews(){
  const r = await fetch('/api/reviews');
  if(r.ok) reviews = await r.json();
}

// ── Exportar a Excel ──────────────────────────────────────────
function exportExcel(){
  const its = gf(); // respetar filtros activos
  if(!its.length){ alert('No hay publicaciones para exportar.'); return; }

  // Encabezados
  const headers = [
    'SKU','Publicacion','Estado','Mi Precio','Min Competidor',
    'Dif %','Tipo Envio','Paga Envio','Comision ML','Vendidos',
    'Competidores Exactos','Competidores Equiv','Mejor Competidor',
    'Precio Mejor Comp','Seller Mejor Comp','Nivel Mejor Comp',
    'Revisado Por','Fecha Revision'
  ];

  const rows = its.map(it=>{
    const comps   = it.competidores || [];
    const exactos = comps.filter(c=>c.match_type==='exacto');
    const equivs  = comps.filter(c=>c.match_type==='equivalente');
    const mejor   = comps.length ? comps.reduce((a,b)=>a.price<b.price?a:b) : null;
    const rev     = reviews[it.id];
    const semMap  = {verde:'Competitivo',amarillo:'Similar',rojo:'Precio alto',gris:'Sin datos'};
    return [
      it.sku||'',
      it.title||'',
      semMap[it.semaforo]||'',
      it.price||'',
      it.min_comp||'',
      it.diff_vs_min!=null ? it.diff_vs_min.toFixed(1)+'%' : '',
      it.envio_tipo||'',
      it.quien_paga||'',
      it.comision||'',
      it.sold_quantity||0,
      exactos.length,
      equivs.length,
      mejor ? mejor.title : '',
      mejor ? mejor.price : '',
      mejor ? (mejor.seller_name||'') : '',
      mejor ? ((mejor.seller_info||{}).level||'') : '',
      rev ? rev.usuario : '',
      rev ? rev.fecha   : '',
    ];
  });

  // Construir CSV con BOM para que Excel lo abra bien en español
  const BOM = '﻿';
  const sep = ';'; // punto y coma para Excel en español/AR
  const escape = v => {
    const s = String(v==null?'':v).replace(/"/g,'""');
    return s.includes(sep)||s.includes('
')||s.includes('"') ? `"${s}"` : s;
  };
  const csv = BOM +
    [headers, ...rows]
    .map(row => row.map(escape).join(sep))
    .join('
');

  // Descargar
  const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  const date = new Date().toLocaleDateString('es-AR').replace(/\\//g,'-');
  a.href     = url;
  a.download = `AGROCENTRAL_competencia_${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// Auto-refresh de revisiones cada 30 segundos
let _reviewPoll = null;
function startReviewPoll(){
  if(_reviewPoll) clearInterval(_reviewPoll);
  _reviewPoll = setInterval(async()=>{
    const prev = JSON.stringify(reviews);
    await loadReviews();
    if(JSON.stringify(reviews) !== prev){
      render(); // re-renderizar solo si hubo cambios
    }
  }, 30000);
}

window.onload=async()=>{
  // Cargar usuario actual
  const me = await fetch('/api/me').then(r=>r.json());
  currentUser = me.username || "";
  if(currentUser){
    document.getElementById('current-user').textContent =
      '👤 ' + currentUser.charAt(0).toUpperCase() + currentUser.slice(1);
  }

  // Cargar revisiones y datos
  await loadReviews();
  loadData();
  startReviewPoll(); // iniciar auto-refresh de revisiones

  fetch('/api/status').then(r=>r.json()).then(s=>{
    if(s.status==='running')startPoll();
    if(s.last_update)
      document.getElementById('lu').textContent=
        'Ultima actualizacion: '+new Date(s.last_update).toLocaleString('es-AR');
    if(s.cloud_mode){
      const b=document.getElementById('bup');
      b.textContent='☁️ Info actualización';
      b.style.background='#455a64';
      b.style.opacity='1';
    }
    if(s.cloud_mode && s.has_data) loadData();
  });
};
</script>
</body></html>"""

LOGIN_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>AGROCENTRAL</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:Arial,sans-serif;background:#f0f4f0;display:flex;align-items:center;justify-content:center;min-height:100vh}.box{background:#fff;border-radius:12px;padding:40px 48px;box-shadow:0 4px 24px rgba(0,0,0,.12);text-align:center;width:340px}.logo{font-size:2.5rem;margin-bottom:8px}h2{color:#1a5c30;margin-bottom:6px}p{color:#888;font-size:.85rem;margin-bottom:24px}input{width:100%;padding:10px 14px;border:1px solid #ccc;border-radius:6px;font-size:.95rem;margin-bottom:12px;outline:none}input:focus{border-color:#2e7d32}button{width:100%;padding:11px;background:#1a5c30;color:#fff;border:none;border-radius:6px;font-size:.95rem;font-weight:bold;cursor:pointer}button:hover{background:#2e7d32}.err{color:#c62828;font-size:.82rem;margin-top:10px}</style></head><body><div class="box"><div class="logo">&#127807;</div><h2>AGROCENTRAL</h2><p>Dashboard de Competencia</p><form method="POST" action="/login"><input type="text" name="username" placeholder="Usuario" autofocus><input type="password" name="password" placeholder="Contrasena"><button type="submit">Ingresar</button>{error}</form></div></body></html>"""

def make_token(u):
    return u + ":" + str(abs(hash(USERS[u] + u)))[:12]

def get_user(req):
    t = req.cookies.get("agro_session", "")
    if ":" not in t: return None
    u, s = t.split(":", 1)
    if u in USERS and s == str(abs(hash(USERS[u] + u)))[:12]: return u
    return None

def auth(req): return get_user(req) is not None

@app.route("/login", methods=["GET","POST"])
def login():
    err = ""
    if request.method == "POST":
        u = request.form.get("username","").strip().lower()
        p = request.form.get("password","").strip()
        if u in USERS and USERS[u] == p:
            resp = make_response(redirect("/"))
            resp.set_cookie("agro_session", make_token(u), max_age=86400*30, httponly=True)
            return resp
        err = '<div class="err">Usuario o contrasena incorrectos</div>'
    return LOGIN_HTML.replace("{error}", err)

@app.route("/logout")
def logout():
    r = make_response(redirect("/login"))
    r.delete_cookie("agro_session")
    return r

@app.route("/")
def index():
    if not auth(request): return redirect("/login")
    return Response(DASH_HTML, mimetype="text/html")

@app.route("/api/me")
def api_me(): return jsonify({"username": get_user(request) or ""})

@app.route("/api/data")
def api_data():
    if not auth(request): return jsonify({}), 401
    try:
        # get_all_items con manejo robusto de JSONB
        items = []
        meta  = {}
        import psycopg2.extras as _extras
        url = os.environ.get("DATABASE_URL","")
        if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
        with psycopg2.connect(url, sslmode="require") as conn:
            with conn.cursor(cursor_factory=_extras.RealDictCursor) as cur:
                cur.execute("SELECT data FROM items ORDER BY updated_at DESC")
                for row in cur.fetchall():
                    d = row["data"]
                    if isinstance(d, str):
                        import json as _json
                        d = _json.loads(d)
                    items.append(d)
                cur.execute("SELECT key, value FROM sync_meta")
                meta = {r["key"]: r["value"] for r in cur.fetchall()}
        return jsonify({"items": items, "last_update": meta.get("last_update",""), "total": len(items)})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(), "items": []}), 500

@app.route("/api/item/<iid>")
def api_item(iid):
    if not auth(request): return jsonify({}), 401
    try:
        import psycopg2.extras as _extras
        url = os.environ.get("DATABASE_URL","")
        if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
        with psycopg2.connect(url, sslmode="require") as conn:
            with conn.cursor(cursor_factory=_extras.RealDictCursor) as cur:
                cur.execute("SELECT data FROM items WHERE id=%s",(iid,))
                row = cur.fetchone()
        if not row: return jsonify({})
        d = row["data"]
        if isinstance(d,str): import json as _j; d=_j.loads(d)
        return jsonify(d)
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.route("/api/reviews")
def api_reviews():
    if not auth(request): return jsonify({}), 401
    try:
        import psycopg2.extras as _extras
        url = os.environ.get("DATABASE_URL","")
        if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
        with psycopg2.connect(url, sslmode="require") as conn:
            with conn.cursor(cursor_factory=_extras.RealDictCursor) as cur:
                cur.execute("SELECT item_id, username, fecha FROM reviews")
                rows = cur.fetchall()
        return jsonify({r["item_id"]:{"usuario":r["username"],"fecha":r["fecha"]} for r in rows})
    except: return jsonify({})

@app.route("/api/review/<iid>", methods=["POST"])
def api_review(iid):
    u = get_user(request)
    if not u: return jsonify({"ok":False}), 401
    try:
        from datetime import datetime as _dt
        fecha = _dt.now().strftime("%d/%m/%Y %H:%M")
        url = os.environ.get("DATABASE_URL","")
        if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
        with psycopg2.connect(url, sslmode="require") as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO reviews (item_id,username,fecha,timestamp)
                    VALUES (%s,%s,%s,NOW())
                    ON CONFLICT (item_id) DO UPDATE SET
                    username=EXCLUDED.username,fecha=EXCLUDED.fecha,timestamp=NOW()
                """,(iid,u,fecha))
            conn.commit()
        return jsonify({"ok":True,"review":{"usuario":u,"fecha":fecha}})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}), 500

@app.route("/api/status")
def api_status():
    if not auth(request): return jsonify({}), 401
    try:
        meta = db.get_sync_meta()
        return jsonify({"status":"done","progress":100,"cloud_mode":True,"has_data":True,"last_update":meta.get("last_update",""),"message":"Datos disponibles"})
    except: return jsonify({"status":"idle","cloud_mode":True})

@app.route("/api/update", methods=["POST"])
def api_update(): return jsonify({"ok":False,"msg":"Actualizar desde la PC de Ariel."})

@app.route("/api/pause", methods=["POST"])
def api_pause(): return jsonify({"ok":False})

if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
