let currentMapVar = 'humidity';

function setVar(v, el) {
  currentMapVar = v;
  document.querySelectorAll('.map-var-btn').forEach((b) => b.classList.remove('active'));
  if (el) el.classList.add('active');
  drawMap();
}

function labelForMode() {
  return { humidity:t('mapHumidity'), ph:t('mapPh'), temp:t('mapTemp'), ec:t('mapEc') }[currentMapVar] || t('map');
}

function valueLabel(z) {
  if (!z) return t('unmeasured');
  if (currentMapVar === 'humidity') return `${z.humidity}%`;
  if (currentMapVar === 'ph') return `pH ${z.ph}`;
  if (currentMapVar === 'temp') return `${z.temp}°C`;
  if (currentMapVar === 'ec') return `${z.ec ?? '—'} mS/cm`;
  return '';
}

function legendForMode() {
  // Légende sémantique CONSTANTE (mêmes couleurs = même sens partout).
  const c = MAP_STATUS_COLORS;
  return (
    `<div class="leg-item"><span class="leg-dot" style="background:${c.good}"></span>${t('correct')}</div>` +
    `<div class="leg-item"><span class="leg-dot" style="background:${c.warn}"></span>${t('borderline')}</div>` +
    `<div class="leg-item"><span class="leg-dot" style="background:${c.bad}"></span>${t('outRange')}</div>` +
    `<div class="leg-item"><span class="leg-dot" style="background:${c.none}"></span>${t('unmeasured')}</div>`
  );
}

// PRNG déterministe (mulberry32) — texture de sol stable entre les rendus.
function _rng(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Fond « vue aérienne du sol » : dégradé terreux + taches organiques + sillons
// de labour + vignette, le tout clippé dans un coin arrondi.
function drawSoil(ctx, W, H, rad) {
  ctx.save();
  roundRect(ctx, 0, 0, W, H, rad);
  ctx.clip();

  const g = ctx.createLinearGradient(0, 0, W * 0.4, H);
  g.addColorStop(0, '#867b3f');
  g.addColorStop(0.45, '#6d5e34');
  g.addColorStop(1, '#4d3b22');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);

  // taches organiques (humus, parcelles de terre nue, zones cultivées)
  const rnd = _rng(20240529);
  const tones = ['58,44,24', '120,96,52', '110,118,60', '150,140,80'];
  for (let i = 0; i < 20; i++) {
    const px = rnd() * W, py = rnd() * H, pr = 26 + rnd() * 90;
    const base = tones[(rnd() * tones.length) | 0];
    const rg = ctx.createRadialGradient(px, py, 0, px, py, pr);
    rg.addColorStop(0, `rgba(${base},${(0.18 + rnd() * 0.14).toFixed(3)})`);
    rg.addColorStop(1, `rgba(${base},0)`);
    ctx.fillStyle = rg;
    ctx.beginPath(); ctx.arc(px, py, pr, 0, Math.PI * 2); ctx.fill();
  }

  // sillons de labour (lignes parallèles légèrement diagonales)
  const step = Math.max(12, H / 20);
  for (let y = -W; y < H + W; y += step) {
    ctx.globalAlpha = 0.14;
    ctx.strokeStyle = '#2a2414'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y + W * 0.10); ctx.stroke();
    ctx.globalAlpha = 0.07;
    ctx.strokeStyle = 'rgba(220,210,170,1)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, y + 2); ctx.lineTo(W, y + 2 + W * 0.10); ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // vignette douce
  const vg = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.32, W / 2, H / 2, Math.max(W, H) * 0.72);
  vg.addColorStop(0, 'rgba(0,0,0,0)');
  vg.addColorStop(1, 'rgba(0,0,0,0.30)');
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, W, H);
  ctx.restore();

  ctx.strokeStyle = 'rgba(255,255,255,0.10)';
  ctx.lineWidth = 1;
  roundRect(ctx, 0.5, 0.5, W - 1, H - 1, rad);
  ctx.stroke();
}

function _planBounds(plan) {
  const xs = plan.map((p) => p.x), ys = plan.map((p) => p.y);
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
}

// Place les points en préservant les distances réelles (échelle UNIFORME x/y),
// centrés dans la parcelle. Renvoie aussi mètres↔pixels pour l'échelle.
function _layoutField(plan, W, H, pad) {
  const b = _planBounds(plan);
  const spanX = b.maxX - b.minX, spanY = b.maxY - b.minY;
  const usableW = W * (1 - 2 * pad), usableH = H * (1 - 2 * pad);
  let s;
  if (spanX < 1e-6 && spanY < 1e-6) s = 1;                 // point unique
  else s = Math.min(usableW / Math.max(spanX, 1e-6), usableH / Math.max(spanY, 1e-6));
  const drawnW = spanX * s, drawnH = spanY * s;
  const ox = (W - drawnW) / 2, oy = (H - drawnH) / 2;
  const placed = plan.map((p) => ({
    label: p.label,
    x: spanX < 1e-6 ? W / 2 : ox + (p.x - b.minX) * s,
    y: spanY < 1e-6 ? H / 2 : oy + (p.y - b.minY) * s,
  }));
  return { placed, pxPerM: s, span: Math.max(spanX, spanY) };
}

// Rayon des marqueurs adapté au nombre de points.
function _markerRadius(n) { return Math.max(7, Math.min(24, 42 / Math.sqrt(n))); }

// Barre d'échelle réelle (mètres), coin bas-gauche.
function _drawScaleBar(ctx, W, H, pxPerM, span) {
  if (!pxPerM || span < 1e-6) return;
  const target = W * 0.22;                       // longueur visée ~22 % largeur
  let meters = target / pxPerM;
  const pow = Math.pow(10, Math.floor(Math.log10(meters)));
  const n = meters / pow;
  meters = (n >= 5 ? 5 : n >= 2 ? 2 : 1) * pow;  // arrondi « joli » (1/2/5)
  const px = meters * pxPerM;
  const x0 = 16, y0 = H - 18;
  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.9)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x0, y0 - 4); ctx.lineTo(x0, y0); ctx.lineTo(x0 + px, y0); ctx.lineTo(x0 + px, y0 - 4);
  ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,0.95)';
  ctx.font = '700 11px DM Sans';
  ctx.textAlign = 'center';
  const lbl = meters >= 1 ? `${meters} m` : `${meters.toFixed(1)} m`;
  ctx.fillText(lbl, x0 + px / 2, y0 - 7);
  ctx.restore();
}

function drawMap() {
  const canvas = document.getElementById('fieldMap');
  if (!canvas) return;

  const W = canvas.offsetWidth || 360;
  canvas.width = W;
  canvas.height = Math.round(W * 0.66);
  const H = canvas.height;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, W, H);

  // 1) Fond : vue aérienne du sol
  drawSoil(ctx, W, H, 18);

  // 2) Disposition réelle (distances préservées) — calculée une seule fois
  const plan = currentPlan();
  const n = Math.max(1, plan.length);
  const pad = 0.12;
  const { placed, pxPerM, span } = _layoutField(plan, W, H, pad);
  const r = _markerRadius(n);

  // 3) Marqueurs « capteurs » : disque coloré (statut), anneau, label, valeur
  placed.forEach((pt) => {
    const data = APP_STATE.fieldData[pt.label];
    const sel = pt.label === APP_STATE.selectedZone;
    const color = colorForVariable(data, currentMapVar);

    if (sel) {
      ctx.beginPath(); ctx.arc(pt.x, pt.y, r + 7, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fill();
    }
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.40)'; ctx.shadowBlur = 8; ctx.shadowOffsetY = 3;
    ctx.beginPath(); ctx.arc(pt.x, pt.y, r, 0, Math.PI * 2);
    ctx.fillStyle = data ? color : 'rgba(220,228,220,0.35)';
    ctx.fill();
    ctx.restore();

    ctx.beginPath(); ctx.arc(pt.x, pt.y, r, 0, Math.PI * 2);
    ctx.strokeStyle = sel ? '#ffffff' : 'rgba(255,255,255,0.75)';
    ctx.lineWidth = sel ? 3 : 2;
    if (!data) ctx.setLineDash([3, 3]);
    ctx.stroke();
    ctx.setLineDash([]);

    // label au-dessus (si peu de points ou sélectionné)
    if (n <= 14 || sel) {
      ctx.fillStyle = '#fff';
      ctx.textAlign = 'center';
      ctx.font = `800 ${Math.max(9, Math.min(13, r * 0.8))}px DM Sans`;
      ctx.fillText(pt.label, pt.x, pt.y - r - 6);
    }
    // valeur en pastille sous le point (si peu de points ou sélectionné)
    if ((n <= 8 || sel) && data) {
      const txt = valueLabel(data);
      ctx.font = '700 10px DM Sans';
      const w = ctx.measureText(txt).width + 12;
      const cx = pt.x - w / 2, cy = pt.y + r + 4;
      ctx.fillStyle = 'rgba(15,25,18,0.80)';
      roundRect(ctx, cx, cy, w, 16, 8); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.textAlign = 'center';
      ctx.fillText(txt, pt.x, cy + 11.5);
    }
  });

  // 4) Robot sur le point actif
  const robotPt = placed.find((p) => p.label === APP_STATE.robot.activePoint);
  if (robotPt) {
    ctx.font = '22px serif';
    ctx.textAlign = 'center';
    ctx.fillText('🤖', robotPt.x, robotPt.y - r - 16);
  }

  // 5) Échelle réelle + rose des vents
  _drawScaleBar(ctx, W, H, pxPerM, span);
  ctx.fillStyle = 'rgba(255,255,255,0.85)';
  ctx.font = '700 11px DM Sans';
  ctx.textAlign = 'center';
  ctx.fillText('N', W - 18, 20);
  ctx.beginPath(); ctx.moveTo(W - 18, 24); ctx.lineTo(W - 21, 30); ctx.lineTo(W - 15, 30); ctx.closePath();
  ctx.fillStyle = 'rgba(255,255,255,0.85)'; ctx.fill();

  const labelEl = document.getElementById('mapVarLabel');
  const legendEl = document.getElementById('mapLegend');
  const barEl = document.getElementById('mapScaleBar');
  const scaleEl = document.getElementById('mapScaleLabels');
  if (labelEl) labelEl.textContent = labelForMode();
  if (legendEl) legendEl.innerHTML = legendForMode();
  if (barEl) barEl.style.background = `linear-gradient(90deg,${MAP_STATUS_COLORS.good},${MAP_STATUS_COLORS.warn},${MAP_STATUS_COLORS.bad})`;
  if (scaleEl) scaleEl.innerHTML = `<span>${t('correct')}</span><span>${t('outRange')}</span>`;

  // Hit-test sur les positions déjà calculées (pas de recalcul O(n²)).
  const zoneAt = (e) => {
    const rect = canvas.getBoundingClientRect();
    const sx = W / rect.width, sy = H / rect.height;
    const x = (e.clientX - rect.left) * sx, y = (e.clientY - rect.top) * sy;
    return placed.map((p) => ({ z: p.label, d: Math.hypot(x - p.x, y - p.y) }))
      .sort((a, b) => a.d - b.d)[0].z;
  };

  canvas.onclick = (e) => {
    selectZone(zoneAt(e));
    showPage('reco', document.querySelector('[onclick*=reco]'));
  };

  const tip = document.getElementById('mapTooltip');
  if (tip) {
    canvas.onmousemove = (e) => {
      const rect = canvas.getBoundingClientRect();
      const z = zoneAt(e);
      const data = APP_STATE.fieldData[z];
      const status = { good:t('correct'), warn:t('borderline'), bad:t('outRange'), none:t('unmeasured') }[variableStatus(data, currentMapVar)];
      tip.innerHTML = `<strong>${z}</strong> · ${valueLabel(data)}<br><span style="opacity:.8">${status}</span>`;
      tip.style.left = (e.clientX - rect.left + 12) + 'px';
      tip.style.top = (e.clientY - rect.top + 12) + 'px';
      tip.classList.add('show');
    };
    canvas.onmouseleave = () => tip.classList.remove('show');
  }
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x+r, y);
  ctx.arcTo(x+w, y, x+w, y+h, r);
  ctx.arcTo(x+w, y+h, x, y+h, r);
  ctx.arcTo(x, y+h, x, y, r);
  ctx.arcTo(x, y, x+w, y, r);
  ctx.closePath();
}
