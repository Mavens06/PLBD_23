// ======== ORGANIC TERRAIN MAP ========
let currentVar = 'humidity';
const mapData = {};
const ZONE_SEEDS = [];
const ZONE_NAMES_ARR = [];
const ZONE_COUNT = 24;
const robotZoneIdx = 14;

const mapConfigs = {
  humidity:{
    label:'💧 Humidité du sol', unit:'%',
    gen:()=>20+Math.random()*55,
    colorFn:v=>interpColor(v,20,75,['#c0392b','#f5eed8','#a8d5ae','#1a6b3a']),
    scaleGrad:'linear-gradient(90deg,#c0392b,#f5eed8,#a8d5ae,#1a6b3a)',
    scaleMin:'20% Sec', scaleMax:'75% Humide',
    legend:[{c:'#1a6b3a',l:'Très humide'},{c:'#4a9c55',l:'Humide'},{c:'#a8d5ae',l:'Modéré'},{c:'#f5eed8',l:'Sec'},{c:'#c0392b',l:'Critique'}]
  },
  ph:{
    label:'🧪 pH du sol', unit:'',
    gen:()=>4.5+Math.random()*3.5,
    colorFn:v=>v>=6&&v<=7?interpColor(v,6,7,['#2d9c55','#1a6b3a']):v<6?interpColor(v,4.5,6,['#c0392b','#f9c74f']):interpColor(v,7,8,['#f4a261','#c0392b']),
    scaleGrad:'linear-gradient(90deg,#c0392b,#f9c74f,#1a6b3a,#f4a261,#c0392b)',
    scaleMin:'4.5 Acide', scaleMax:'8.0 Basique',
    legend:[{c:'#1a6b3a',l:'6-7 Optimal'},{c:'#f9c74f',l:'Légèrement acide'},{c:'#f4a261',l:'Légèrement basique'},{c:'#c0392b',l:'Hors norme'}]
  },
  ec:{
    label:'⚡ Conductivité (Salinité)', unit:'mS/cm',
    gen:()=>0.3+Math.random()*3.2,
    colorFn:v=>interpColor(v,0.3,3.5,['#e8f5e9','#4a9c55','#f9c74f','#c0392b']),
    scaleGrad:'linear-gradient(90deg,#e8f5e9,#4a9c55,#f9c74f,#c0392b)',
    scaleMin:'0.3 Faible', scaleMax:'3.5 Critique',
    legend:[{c:'#4a9c55',l:'1-2 Normal'},{c:'#f9c74f',l:'2-3 Élevé'},{c:'#c0392b',l:'>3 Critique'}]
  },
  temp:{
    label:'🌡️ Température du sol', unit:'°C',
    gen:()=>8+Math.random()*25,
    colorFn:v=>interpColor(v,8,33,['#aee4f0','#a8d5ae','#4a9c55','#f4a261','#c0392b']),
    scaleGrad:'linear-gradient(90deg,#aee4f0,#4a9c55,#f4a261,#c0392b)',
    scaleMin:'8°C Froid', scaleMax:'33°C Chaud',
    legend:[{c:'#4a9c55',l:'15-25°C Optimal'},{c:'#a8d5ae',l:'10-15°C Frais'},{c:'#f4a261',l:'25-30°C Chaud'},{c:'#c0392b',l:'Extrême'}]
  },
  npk:{
    label:'🌿 NPK Global', unit:'',
    gen:()=>10+Math.random()*90,
    colorFn:v=>interpColor(v,10,100,['#c0392b','#f9c74f','#4a9c55','#1a6b3a']),
    scaleGrad:'linear-gradient(90deg,#c0392b,#f9c74f,#4a9c55,#1a6b3a)',
    scaleMin:'Déficit', scaleMax:'Excellent',
    legend:[{c:'#1a6b3a',l:'>75 Excellent'},{c:'#4a9c55',l:'50-75 Bon'},{c:'#f9c74f',l:'30-50 Faible'},{c:'#c0392b',l:'<30 Déficit'}]
  },
  reco:{
    label:'💡 Recommandations', unit:'',
    gen:()=>Math.random(),
    colorFn:v=>v<0.25?'#4a9c55':v<0.5?'#a8d5ae':v<0.75?'#f9c74f':'#c0392b',
    scaleGrad:'linear-gradient(90deg,#4a9c55,#a8d5ae,#f9c74f,#c0392b)',
    scaleMin:'Optimal', scaleMax:'Urgent',
    legend:[{c:'#4a9c55',l:'Optimal'},{c:'#a8d5ae',l:'Surveiller'},{c:'#f9c74f',l:'Action requise'},{c:'#c0392b',l:'Urgent'}]
  }
};

function interpColor(v,min,max,stops){
  const t=Math.max(0,Math.min(1,(v-min)/(max-min)));
  const seg=(stops.length-1)*t;
  const i=Math.min(Math.floor(seg),stops.length-2);
  return lerpColor(stops[i],stops[i+1],seg-i);
}
function lerpColor(a,b,t){
  const ah=a.replace('#',''),bh=b.replace('#','');
  const ar=parseInt(ah.slice(0,2),16),ag=parseInt(ah.slice(2,4),16),ab2=parseInt(ah.slice(4,6),16);
  const br=parseInt(bh.slice(0,2),16),bg=parseInt(bh.slice(2,4),16),bb=parseInt(bh.slice(4,6),16);
  const r=Math.round(ar+(br-ar)*t),g=Math.round(ag+(bg-ag)*t),bl=Math.round(ab2+(bb-ab2)*t);
  return '#'+[r,g,bl].map(x=>x.toString(16).padStart(2,'0')).join('');
}
function hexToRgb(hex){
  const h=hex.replace('#','');
  return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];
}

Object.keys(mapConfigs).forEach(k=>{
  mapData[k]=Array.from({length:ZONE_COUNT},()=>mapConfigs[k].gen());
});

function initSeeds(W,H){
  ZONE_SEEDS.length=0; ZONE_NAMES_ARR.length=0;
  const cols=6,rows=4;
  for(let r=0;r<rows;r++){
    for(let c=0;c<cols;c++){
      const jx=(Math.random()-0.5)*W*0.13;
      const jy=(Math.random()-0.5)*H*0.13;
      ZONE_SEEDS.push({x:(c+0.5)/cols*W+jx, y:(r+0.5)/rows*H+jy});
      ZONE_NAMES_ARR.push(String.fromCharCode(65+r)+(c+1));
    }
  }
}

/* ── IDW interpolation ─────────────────────────────────────────────────
   Inverse Distance Weighting: value at pixel (px,py) =
   Σ(v_i / d_i^p) / Σ(1 / d_i^p)  with power p=2
   Falls back to nearest seed if cursor is exactly on a seed.
─────────────────────────────────────────────────────────────────────── */
const IDW_POWER = 2;
function idwValue(wx, wy, values) {
  let wSum = 0, vSum = 0;
  for (let i = 0; i < ZONE_SEEDS.length; i++) {
    const dx = wx - ZONE_SEEDS[i].x;
    const dy = wy - ZONE_SEEDS[i].y;
    const d2 = dx*dx + dy*dy;
    if (d2 < 1) return values[i];
    const w = 1 / Math.pow(d2, IDW_POWER / 2);
    wSum += w;
    vSum += w * values[i];
  }
  return vSum / wSum;
}

/* ── Voronoi edge detection ─────────────────────────────────────────────
   A pixel is a Voronoi edge when its nearest seed differs from any of
   its 4 direct neighbours → draws thin contour borders between zones.
─────────────────────────────────────────────────────────────────────── */
function nearestSeedIdx(wx, wy) {
  let minD = Infinity, n = 0;
  for (let s = 0; s < ZONE_SEEDS.length; s++) {
    const dx = wx - ZONE_SEEDS[s].x, dy = wy - ZONE_SEEDS[s].y;
    const d = dx*dx + dy*dy;
    if (d < minD) { minD = d; n = s; }
  }
  return n;
}
function nearestSeed(wx, wy) { return nearestSeedIdx(wx, wy); }

function buildVoronoiEdgeMap(oW, oH, sc) {
  const grid = new Int16Array(oW * oH);
  for (let py = 0; py < oH; py++)
    for (let px = 0; px < oW; px++)
      grid[py * oW + px] = nearestSeedIdx(px * sc + sc/2, py * sc + sc/2);
  const edge = new Uint8Array(oW * oH);
  for (let py = 1; py < oH - 1; py++) {
    for (let px = 1; px < oW - 1; px++) {
      const c = grid[py * oW + px];
      if (grid[py * oW + px - 1] !== c ||
          grid[py * oW + px + 1] !== c ||
          grid[(py-1) * oW + px] !== c ||
          grid[(py+1) * oW + px] !== c) {
        edge[py * oW + px] = 1;
      }
    }
  }
  return edge;
}

function drawOrganicMap(){
  const canvas = document.getElementById('fieldMap');
  if (!canvas) return;
  const W = canvas.offsetWidth || 340;
  canvas.width = W; canvas.height = Math.round(W * 0.68);
  const H = canvas.height;
  const ctx = canvas.getContext('2d');
  const cfg = mapConfigs[currentVar];

  if (ZONE_SEEDS.length === 0) initSeeds(W, H);

  /* ── 1. IDW heatmap at 1/4 resolution ── */
  const sc = 4;
  const oW = Math.ceil(W / sc), oH = Math.ceil(H / sc);
  const off = document.createElement('canvas');
  off.width = oW; off.height = oH;
  const octx = off.getContext('2d');
  const img = octx.createImageData(oW, oH);
  const d = img.data;
  const values = mapData[currentVar];

  for (let py = 0; py < oH; py++) {
    for (let px = 0; px < oW; px++) {
      const wx = px * sc + sc / 2, wy = py * sc + sc / 2;
      const val = idwValue(wx, wy, values);
      const hex = cfg.colorFn(val);
      const [r2, g2, b2] = hexToRgb(hex);
      const ii = (py * oW + px) * 4;
      d[ii] = r2; d[ii+1] = g2; d[ii+2] = b2; d[ii+3] = 255;
    }
  }
  octx.putImageData(img, 0, 0);

  /* ── 2. Voronoi edge overlay ── */
  const edges = buildVoronoiEdgeMap(oW, oH, sc);
  const eImg = octx.createImageData(oW, oH);
  const ed = eImg.data;
  for (let i = 0; i < edges.length; i++) {
    if (edges[i]) {
      ed[i*4] = 255; ed[i*4+1] = 255; ed[i*4+2] = 255; ed[i*4+3] = 85;
    }
  }
  octx.putImageData(eImg, 0, 0);

  /* ── 3. Upscale with smooth interpolation ── */
  ctx.save();
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(off, 0, 0, W, H);
  ctx.restore();

  /* ── 4. Organic noise texture ── */
  const imgFull = ctx.getImageData(0, 0, W, H);
  const fd = imgFull.data;
  for (let i = 0; i < fd.length; i += 4) {
    const n = (Math.random() - 0.5) * 12;
    fd[i]   = Math.max(0, Math.min(255, fd[i]   + n));
    fd[i+1] = Math.max(0, Math.min(255, fd[i+1] + n));
    fd[i+2] = Math.max(0, Math.min(255, fd[i+2] + n));
  }
  ctx.putImageData(imgFull, 0, 0);

  /* ── 5. Soft vignette ── */
  const vig = ctx.createRadialGradient(W/2, H/2, H*0.3, W/2, H/2, H*0.85);
  vig.addColorStop(0, 'rgba(0,0,0,0)');
  vig.addColorStop(1, 'rgba(0,0,0,0.22)');
  ctx.fillStyle = vig; ctx.fillRect(0, 0, W, H);

  /* ── 6. Sensor point markers ── */
  ZONE_SEEDS.forEach((s, i) => {
    if (s.x < 12 || s.x > W-12 || s.y < 12 || s.y > H-12) return;
    const val = values[i];
    const color = cfg.colorFn(val);
    // Glow ring
    const grd = ctx.createRadialGradient(s.x, s.y, 2, s.x, s.y, 10);
    grd.addColorStop(0, color + 'cc');
    grd.addColorStop(1, color + '00');
    ctx.beginPath(); ctx.arc(s.x, s.y, 10, 0, Math.PI*2);
    ctx.fillStyle = grd; ctx.fill();
    // White dot
    ctx.beginPath(); ctx.arc(s.x, s.y, 4, 0, Math.PI*2);
    ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.fill();
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
    // Zone label pill
    ctx.save();
    ctx.font = 'bold 9px DM Sans,sans-serif';
    const nw = ctx.measureText(ZONE_NAMES_ARR[i]).width + 8;
    ctx.fillStyle = 'rgba(0,0,0,0.45)';
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(s.x - nw/2, s.y + 6, nw, 13, 4);
    else ctx.rect(s.x - nw/2, s.y + 6, nw, 13);
    ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.95)';
    ctx.textAlign = 'center'; ctx.fillText(ZONE_NAMES_ARR[i], s.x, s.y + 16);
    // Value
    const txt = typeof val === 'number' ? (val % 1 === 0 ? String(val) : val.toFixed(1)) : '';
    if (txt) {
      ctx.font = '8px DM Sans,sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      ctx.fillText(txt + (cfg.unit ? cfg.unit : ''), s.x, s.y + 28);
    }
    ctx.restore();
  });

  /* ── 7. Robot marker ── */
  const rs = ZONE_SEEDS[robotZoneIdx];
  if (rs) {
    const rx = rs.x, ry = rs.y - 18;
    const grd = ctx.createRadialGradient(rx, ry, 2, rx, ry, 26);
    grd.addColorStop(0, 'rgba(255,220,0,0.6)');
    grd.addColorStop(1, 'rgba(255,220,0,0)');
    ctx.beginPath(); ctx.arc(rx, ry, 26, 0, Math.PI*2);
    ctx.fillStyle = grd; ctx.fill();
    ctx.beginPath(); ctx.arc(rx, ry, 13, 0, Math.PI*2);
    ctx.fillStyle = 'rgba(255,210,0,0.95)'; ctx.fill();
    ctx.strokeStyle = '#7a5800'; ctx.lineWidth = 2; ctx.stroke();
    ctx.font = '12px serif'; ctx.textAlign = 'center';
    ctx.fillText('🤖', rx, ry + 5);
  }

  /* ── UI updates ── */
  const leg = document.getElementById('mapLegend');
  if (leg) leg.innerHTML = cfg.legend.map(l =>
    `<div class="leg-item"><div class="leg-dot" style="background:${l.c}"></div>${l.l}</div>`
  ).join('') + `<div class="leg-item"><div class="leg-dot" style="background:rgba(255,210,0,0.9);border:1px solid #7a5800"></div>🤖 Robot</div>`;
  const bar = document.getElementById('mapScaleBar');
  const lbl = document.getElementById('mapScaleLabels');
  const varLbl = document.getElementById('mapVarLabel');
  if (bar) bar.style.background = cfg.scaleGrad;
  if (lbl) lbl.innerHTML = `<span>${cfg.scaleMin}</span><span style="font-size:9px;opacity:0.6">IDW + Voronoi</span><span>${cfg.scaleMax}</span>`;
  if (varLbl) varLbl.textContent = cfg.label;

  /* ── Interaction ── */
  const tip = document.getElementById('mapTooltip');
  const getPos = (e) => {
    const rect = canvas.getBoundingClientRect();
    const cx = e.touches ? e.touches[0].clientX : e.clientX;
    const cy = e.touches ? e.touches[0].clientY : e.clientY;
    return { x: (cx - rect.left) * W / rect.width,
             y: (cy - rect.top)  * H / rect.height,
             cx: cx - rect.left, cy: cy - rect.top };
  };
  canvas.onmousemove = canvas.ontouchmove = (e) => {
    const p = getPos(e);
    const val = idwValue(p.x, p.y, values);
    const idx = nearestSeed(p.x, p.y);
    const vs = val.toFixed(2);
    tip.textContent = `${ZONE_NAMES_ARR[idx]} — IDW: ${vs}${cfg.unit ? ' ' + cfg.unit : ''}`;
    tip.style.left = Math.min(p.cx + 10, canvas.offsetWidth - 150) + 'px';
    tip.style.top  = Math.max(p.cy - 38, 0) + 'px';
    tip.classList.add('show');
  };
  canvas.onmouseleave = canvas.ontouchend = () => tip.classList.remove('show');
  canvas.onclick = (e) => {
    const p = getPos(e);
    const idx = nearestSeed(p.x, p.y);
    const rawVal = values[idx];
    const idwVal = idwValue(p.x, p.y, values);
    const color = cfg.colorFn(rawVal);
    const det = document.getElementById('zoneDetail');
    document.getElementById('zoneDetailTitle').textContent =
      'Zone ' + ZONE_NAMES_ARR[idx] + ' — ' + cfg.label.replace(/^[^ ]+ /, '');
    document.getElementById('zoneDetailTags').innerHTML =
      `<span class="zone-tag" style="background:${color}22;color:${color};border:1px solid ${color}80">` +
        `📍 Sonde: ${typeof rawVal==='number'?(rawVal%1===0?rawVal:rawVal.toFixed(2)):rawVal}${cfg.unit?' '+cfg.unit:''}` +
      `</span>` +
      `<span class="zone-tag" style="background:#1565c022;color:#1565c0;border:1px solid #1565c040">` +
        `〰️ IDW: ${idwVal.toFixed(2)}${cfg.unit?' '+cfg.unit:''}` +
      `</span>` +
      (idx === robotZoneIdx
        ? `<span class="zone-tag" style="background:#fff8e1;color:#7a5800;border:1px solid #f9c74f80">🤖 Robot ici</span>`
        : '');
    det.classList.add('visible');
  };
}

function setVar(v,el){
  currentVar=v;
  document.querySelectorAll('.map-var-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('zoneDetail').classList.remove('visible');
  drawOrganicMap();
}

function drawMap(){ drawOrganicMap(); }


