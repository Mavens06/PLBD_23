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
function _injectPlanStyles() {
  if (document.getElementById('planEditorStyles')) return;
  const s = document.createElement('style');
  s.id = 'planEditorStyles';
  s.textContent = `
  .plan-editor{background:#fff;border-radius:16px;padding:14px 16px;margin:0 0 14px;box-shadow:0 2px 10px rgba(0,0,0,.06)}
  .plan-title{font-weight:800;display:flex;align-items:center;gap:8px;margin-bottom:10px}
  .plan-head,.plan-row{display:grid;grid-template-columns:1fr 90px 90px 34px;gap:8px;align-items:center}
  .plan-head{font-size:11px;opacity:.6;margin-bottom:4px;padding:0 2px}
  .plan-row{margin-bottom:6px}
  .plan-in{width:100%;padding:7px 8px;border:1px solid #dde5dd;border-radius:9px;font:inherit}
  .plan-del{border:none;background:#f5e3e1;color:#c0392b;border-radius:9px;height:34px;cursor:pointer;font-weight:700}
  .plan-actions{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}`;
  document.head.appendChild(s);
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
      <input class="plan-in" value="${p.label}" data-i="${i}" data-k="label"/>
      <input class="plan-in" type="number" step="0.1" value="${p.x}" data-i="${i}" data-k="x"/>
      <input class="plan-in" type="number" step="0.1" value="${p.y}" data-i="${i}" data-k="y"/>
      <button class="plan-del" onclick="removePlanRow(${i})" title="${t('planRemove')}">✕</button>
    </div>`).join('');
  host.innerHTML = `
    <div class="plan-title">🗺️ ${t('missionPlanTitle')} <span class="mini-badge">${APP_STATE.plan.length} ${t('planPoints')}</span></div>
    <div class="plan-head"><span>${t('planCol')}</span><span>X (m)</span><span>Y (m)</span><span></span></div>
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
  APP_STATE.plan.push({ label: 'P' + (APP_STATE.plan.length + 1), x: 0, y: 0 });
  renderPlanEditor();
}

function removePlanRow(i) {
  if (APP_STATE.plan.length <= 1) { showToast(t('planMin')); return; }
  APP_STATE.plan.splice(i, 1);
  renderPlanEditor();
}

function applyPlanFromEditor() {
  const labels = APP_STATE.plan.map((p) => String(p.label).trim());
  if (labels.some((l) => !l) || new Set(labels).size !== labels.length) {
    showToast(t('planInvalid'));
    return;
  }
  applyPlanPoints(APP_STATE.plan);
  showToast(t('planApplied', { n: APP_STATE.plan.length }));
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
