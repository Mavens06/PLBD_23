function showPage(id, btn) {
  document.querySelectorAll('.page').forEach((p) => p.classList.remove('active'));
  document.querySelectorAll('.bnav-item').forEach((b) => b.classList.remove('active'));
  const page = document.getElementById(`page-${id}`);
  if (page) page.classList.add('active');
  if (btn) btn.classList.add('active');
  if (id === 'map') setTimeout(drawMap, 60);
  if (id === 'reco') renderAdvice();
}

function showAdviceMode() { renderAdvice(); }

function populateCropSelects() {
  const opts = cropNames().map((n) => `<option value="${n}">${getCrop(n).emoji} ${cropLabel(n)}</option>`).join('');
  const global = document.getElementById('globalCropSelect');
  if (global) {
    global.innerHTML = opts;
    global.value = APP_STATE.selectedCrop;
  }
  const zone = document.getElementById('zoneCropSelect');
  if (zone) {
    zone.innerHTML = opts;
    zone.value = APP_STATE.zoneCropPlan[APP_STATE.selectedZone] || APP_STATE.selectedCrop;
  }
}

function setGlobalCrop(name) {
  APP_STATE.selectedCrop = name;
  const m = document.getElementById('missionCropValue');
  if (m) m.textContent = cropLabel(name);
  renderAll();
}

function applyCropEverywhere() {
  planLabels().forEach((z) => { APP_STATE.zoneCropPlan[z] = APP_STATE.selectedCrop; });
  showToast(t('cropApplied', { crop: cropLabel(APP_STATE.selectedCrop) }));
  renderAll();
}

function setZoneCrop(name) {
  APP_STATE.zoneCropPlan[APP_STATE.selectedZone] = name;
  renderAll();
}

function selectZone(zone) {
  APP_STATE.selectedZone = zone;
  renderAll();
}

function renderMission() {
  const r = APP_STATE.robot;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set('missionStateBadge', trStatus(r.status));
  set('missionPoint', r.activePoint);
  set('missionProgressValue', `${Math.round(r.progress)}%`);
  set('missionMeasuredValue', `${r.measuredPoints}/${r.totalPoints}`);
  set('missionCropValue', cropLabel(APP_STATE.selectedCrop));
  set('missionProgressTxt', `${r.measuredPoints} ${t('measuredSing')}`);
  const bar = document.getElementById('missionProgressBar');
  if (bar) bar.style.width = `${Math.max(0, Math.min(100, r.progress))}%`;
  const robotPill = document.getElementById('mapRobotPill');
  const progressPill = document.getElementById('mapProgressPill');
  if (robotPill) robotPill.textContent = `🤖 ${t('robot')} : ${r.activePoint}`;
  if (progressPill) progressPill.textContent = `${r.measuredPoints} / ${r.totalPoints} ${t('measuredZones')}`;
}

function renderGauges() {
  const avg = averageField(APP_STATE.fieldData);
  [
    ['water', 'humidity', '%'],
    ['ph',    'ph',       ''],
    ['temp',  'temp',     '°C'],
    ['ec',    'ec',       ' mS/cm'],
  ].forEach(([id, key, unit]) => {
    const el = document.getElementById(`stat-${id}`);
    if (!el) return;
    const val = avg[key];
    el.textContent = val ? `${val}${unit} · ${t('fieldAverage')}` : t('waiting');

    // Coloration de la carte jauge
    const card = document.getElementById(`card-${id}`);
    if (!card || !val) return;
    card.classList.remove('bad', 'warn', 'good');
    let state = 'good';
    if (id === 'water')  state = val < 45 ? 'warn' : val > 82 ? 'warn' : 'good';
    if (id === 'ph')     state = (val < 5.8 || val > 7.8) ? 'bad' : (val < 6.2 || val > 7.2) ? 'warn' : 'good';
    if (id === 'temp')   state = (val < 14 || val > 32) ? 'warn' : 'good';
    if (id === 'ec')     state = val > 2.5 ? 'bad' : val > 1.5 ? 'warn' : 'good';
    card.classList.add(state);
    el.classList.remove('bad', 'warn', 'good');
    el.classList.add(state);
  });
}

function renderZoneGrid() {
  const grid = document.getElementById('zoneGrid');
  if (!grid) return;
  grid.innerHTML = planLabels().map((z) => {
    const crop = APP_STATE.zoneCropPlan[z] || APP_STATE.selectedCrop;
    const ev = evaluateZoneForCrop(APP_STATE.fieldData[z], crop);
    return `<button class="zone-card ${ev.type} ${APP_STATE.selectedZone === z ? 'active' : ''}" style="--crop-color:${cropColor(crop)}" onclick="selectZone('${z}')">
      <div class="zone-name">${z}</div>
      <div class="zone-crop">${getCrop(crop).emoji} ${cropLabel(crop)}</div>
      <div class="zone-action">${ev.label} · ${ev.detail}</div>
    </button>`;
  }).join('');
}

function renderSelectedZone() {
  const z = APP_STATE.selectedZone;
  const data = APP_STATE.fieldData[z];
  const crop = APP_STATE.zoneCropPlan[z] || APP_STATE.selectedCrop;
  const ev = evaluateZoneForCrop(data, crop);

  const title = document.getElementById('selectedZoneTitle');
  if (title) title.textContent = `${t('selectedZone')} ${z}`;
  const zoneSelect = document.getElementById('zoneCropSelect');
  if (zoneSelect) zoneSelect.value = crop;

  // Rendu local immédiat (fonctionne hors-ligne et identique dans les deux
  // frontends), puis enrichissement par le backend si fetchCorrection existe.
  renderDiagnostic(diagnoseZoneForCrop(data, crop), recommendActionsForZone(data, crop));
  if (data && typeof window.fetchCorrection === 'function') {
    window.fetchCorrection(z, crop)
      .then((diag) => { if (diag && APP_STATE.selectedZone === z) renderDiagnostic(diag.local, diag.actions); })
      .catch(() => {});
  }

  const zt = document.getElementById('zoneDetailTitle');
  const zg = document.getElementById('zoneDetailTags');
  if (zt && zg) {
    zt.textContent = `${t('selectedZone')} ${z}`;
    zg.innerHTML = `<span class="zone-tag" style="background:${ev.color};color:white">${ev.label}</span><span class="zone-tag" style="background:${cropColor(crop)};color:white">${cropLabel(crop)}</span>`;
  }
}

// Affichage premium du diagnostic d'une zone pour la culture cible :
// anneau de compatibilité + pastilles par variable + actions + "mieux adapté".
function renderDiagnostic(diag, actions) {
  const measures = document.getElementById('selectedZoneMeasures');
  const practices = document.getElementById('selectedZonePractices');

  if (!diag) {
    if (measures) measures.innerHTML = `<div class="zone-measure-card"><div class="zone-measure-label">${t('measure')}</div><div class="zone-measure-value">${t('waiting')}</div></div>`;
    if (practices) practices.innerHTML = '';
    return;
  }

  const score = diag.compatibility;
  const ringColor = score >= 70 ? 'var(--green-light)' : score >= 45 ? 'var(--orange)' : 'var(--red)';
  const emoji = getCrop(diag.crop).emoji;

  if (measures) {
    const pills = diag.items.map((it) => {
      const cls = it.status === 'good' ? 'good' : 'off';
      const icon = it.status === 'good' ? '✓' : it.status === 'low' ? '↓' : '↑';
      const v = (it.val ?? '—') + (it.unit || '');
      return `<div class="diag-pill ${cls}">
        <div class="diag-pill-top"><span class="diag-pill-label">${it.label}</span><span class="diag-pill-icon">${icon}</span></div>
        <div class="diag-pill-val">${v}</div>
        <div class="diag-pill-range">${t('target')} ${it.range[0]}–${it.range[1]}${it.unit||''}</div>
      </div>`;
    }).join('');
    measures.innerHTML = `
      <div class="diag-head">
        <div class="diag-ring" style="background:conic-gradient(${ringColor} ${score*3.6}deg, #eef3ee 0deg)">
          <div class="diag-ring-inner"><span class="diag-ring-pct">${score}%</span></div>
        </div>
        <div class="diag-head-txt">
          <div class="diag-head-crop">${emoji} ${cropLabel(diag.crop)}</div>
          <div class="diag-head-sub">${t('compatibility')}</div>
        </div>
      </div>
      <div class="diag-pill-grid">${pills}</div>`;
  }

  if (practices) {
    const actionCards = (actions || []).map((a) => `
      <div class="practice-card ${a.type}">
        <div class="practice-title">${a.title}</div>
        <div class="practice-detail"><strong>${a.value}</strong> · ${a.detail}</div>
      </div>`).join('');
    let better = '';
    if (diag.betterSuited && diag.betterSuited.length) {
      const chips = diag.betterSuited.map((b) =>
        `<span class="better-chip" style="--crop-color:${cropColor(b.name)}">${getCrop(b.name).emoji} ${cropLabel(b.name)} · ${b.score}%</span>`
      ).join('');
      better = `<div class="better-suited"><div class="better-suited-title">🌱 ${t('betterSuited')}</div><div class="better-chips">${chips}</div></div>`;
    }
    practices.innerHTML = actionCards + better;
  }
}

function renderAdvice() {
  populateCropSelects();
  renderZoneGrid();
  renderSelectedZone();
}

// ---------------------------------------------------------------------------
// Éditeur de plan de mission (points de mesure par coordonnées x/y)
// Injecté en JS au-dessus de la carte mission → présent dans toutes les
// variantes HTML sans les modifier. N points définis → N blocs sur la carte.
// ---------------------------------------------------------------------------
// Espacement minimal entre deux points (prototype). On suppose le sol homogène
// dans un petit rayon : inutile (et irréaliste) de mesurer trop rapproché.
const MIN_SPACING_M = 0.5;

function _injectPlanStyles() {
  if (document.getElementById('planEditorStyles')) return;
  const s = document.createElement('style');
  s.id = 'planEditorStyles';
  s.textContent = `
  .plan-editor{background:linear-gradient(180deg,#ffffff,#f6faf5);border:1px solid #e7efe7;border-radius:18px;padding:16px;margin:0 0 14px;box-shadow:0 6px 20px rgba(22,45,22,.07)}
  .plan-hd{display:flex;align-items:center;justify-content:space-between;gap:8px}
  .plan-hd-title{font-weight:800;display:flex;align-items:center;gap:8px;font-size:15px}
  .plan-hd-badge{background:#e8f3e8;color:#2f7a3a;border-radius:20px;padding:3px 11px;font-size:12px;font-weight:700;white-space:nowrap}
  .plan-sub{font-size:11.5px;color:#7c887c;margin:5px 0 13px}
  .plan-row{display:grid;grid-template-columns:30px 1fr 86px 86px 32px;gap:8px;align-items:center;margin-bottom:8px}
  .plan-idx{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:11px;color:#fff;background:linear-gradient(135deg,#52a85d,#3b7a44);box-shadow:0 2px 5px rgba(59,122,68,.35)}
  .plan-field{position:relative}
  .plan-field .unit{position:absolute;right:9px;top:50%;transform:translateY(-50%);font-size:10px;color:#9aa79a;pointer-events:none}
  .plan-in{width:100%;padding:8px 9px;border:1px solid #dde5dd;border-radius:10px;font:inherit;font-size:13px;background:#fff;transition:border-color .15s,box-shadow .15s}
  .plan-field .plan-in{padding-right:22px}
  .plan-in:focus{outline:none;border-color:#4a9c55;box-shadow:0 0 0 3px rgba(74,156,85,.16)}
  .plan-del{border:none;background:#fbeceb;color:#c0392b;border-radius:9px;height:32px;width:32px;cursor:pointer;font-weight:700;font-size:13px;transition:background .15s,transform .1s}
  .plan-del:hover{background:#f3d4d2}.plan-del:active{transform:scale(.92)}
  .plan-actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
  .plan-actions>button{flex:1;min-width:140px}`;
  document.head.appendChild(s);
}

function _nextPlanLabel() {
  const used = new Set(APP_STATE.plan.map((p) => p.label));
  let i = 1;
  while (used.has('P' + i)) i++;
  return 'P' + i;
}

function renderPlanEditor() {
  _injectPlanStyles();
  let host = document.getElementById('planEditor');
  if (!host) {
    const card = document.querySelector('.mission-card') || document.getElementById('page-farmer');
    if (!card) return;
    host = document.createElement('div');
    host.id = 'planEditor';
    host.className = 'plan-editor';
    (card.parentNode || card).insertBefore(host, card);
  }
  const rows = APP_STATE.plan.map((p, i) => `
    <div class="plan-row">
      <span class="plan-idx">${i + 1}</span>
      <input class="plan-in" value="${p.label}" data-i="${i}" data-k="label" aria-label="${t('planCol')}"/>
      <span class="plan-field"><input class="plan-in" type="number" step="0.1" value="${p.x}" data-i="${i}" data-k="x"/><span class="unit">m</span></span>
      <span class="plan-field"><input class="plan-in" type="number" step="0.1" value="${p.y}" data-i="${i}" data-k="y"/><span class="unit">m</span></span>
      <button class="plan-del" onclick="removePlanRow(${i})" title="${t('planRemove')}">✕</button>
    </div>`).join('');
  host.innerHTML = `
    <div class="plan-hd">
      <span class="plan-hd-title">🛰️ ${t('missionPlanTitle')}</span>
      <span class="plan-hd-badge">${APP_STATE.plan.length} ${t('planPoints')}</span>
    </div>
    <div class="plan-sub">${t('planSpacingNote', { d: MIN_SPACING_M })}</div>
    <div class="plan-rows">${rows}</div>
    <div class="plan-actions">
      <button class="btn-soft" onclick="addPlanRow()">＋ ${t('planAdd')}</button>
      <button class="btn-primary" onclick="applyPlanFromEditor()">✓ ${t('planApply')}</button>
    </div>`;
  host.querySelectorAll('.plan-in').forEach((inp) => {
    inp.onchange = () => {
      const i = +inp.dataset.i, k = inp.dataset.k;
      APP_STATE.plan[i][k] = (k === 'label') ? inp.value : Number(inp.value);
    };
  });
}

function addPlanRow() {
  // Décale le nouveau point de l'espacement min depuis le dernier (jamais superposé).
  const last = APP_STATE.plan[APP_STATE.plan.length - 1] || { x: 0, y: 0 };
  APP_STATE.plan.push({ label: _nextPlanLabel(), x: Math.round((last.x + 1) * 10) / 10, y: last.y });
  renderPlanEditor();
}

function removePlanRow(i) {
  if (APP_STATE.plan.length <= 1) { showToast(t('planMin')); return; }
  APP_STATE.plan.splice(i, 1);
  renderPlanEditor();
}

function applyPlanFromEditor() {
  const pts = APP_STATE.plan;
  const labels = pts.map((p) => String(p.label).trim());
  if (labels.some((l) => !l) || new Set(labels).size !== labels.length) {
    showToast(t('planInvalid'));
    return;
  }
  if (pts.some((p) => !isFinite(p.x) || !isFinite(p.y))) {
    showToast(t('planInvalid'));
    return;
  }
  // Distance minimale entre points (sol homogène sur un petit rayon).
  for (let i = 0; i < pts.length; i++) {
    for (let j = i + 1; j < pts.length; j++) {
      if (Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y) < MIN_SPACING_M) {
        showToast(t('planTooClose', { a: pts[i].label, b: pts[j].label, d: MIN_SPACING_M }));
        return;
      }
    }
  }
  applyPlanPoints(pts);
  showToast(t('planApplied', { n: pts.length }));
  renderAll();
}

function renderAll() {
  applyLanguage();
  renderPlanEditor();
  renderMission();
  renderGauges();
  renderAdvice();
  drawMap();
}

document.addEventListener('DOMContentLoaded', () => {
  populateCropSelects();
  renderAll();
});
window.addEventListener('resize', drawMap);
