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

  // Hiérarchie des boutons : ▶ Démarrer seul en avant tant que rien ne tourne ;
  // Pause / Arrêter / Synchroniser n'apparaissent QUE pendant la mission
  // (le rafraîchissement est de toute façon automatique toutes les 1,5 s).
  const running = ['requested', 'running', 'moving', 'measuring', 'paused'].includes(r.status);
  // Pause / Arrêter : seulement pendant la mission. Synchroniser (= remise à
  // zéro) reste TOUJOURS visible pour pouvoir réinitialiser et reprendre.
  [['btnPauseReal', running], ['btnStopReal', running]]
    .forEach(([id, show]) => { const el = document.getElementById(id); if (el) el.style.display = show ? '' : 'none'; });
  const syncBtn = document.getElementById('btnSyncReal');
  if (syncBtn) syncBtn.style.display = '';

  updateCoach();
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
    // Bandeau météo : explique pourquoi l'irrigation a été ajustée (pluie prévue).
    let weatherBanner = '';
    const w = (typeof weatherInfo === 'function') ? weatherInfo() : null;
    if (w) {
      const f = weatherIrrigationFactor();
      const tone = f === 0 ? '#2c6e8f' : f < 1 ? '#7a6a1f' : '#3b7a44';
      const bg = f === 0 ? '#e7f1f8' : f < 1 ? '#f7f1dd' : '#eaf4ea';
      const tip = f === 0 ? t('irrigDeferred') : f < 1 ? t('irrigReduced') : t('weatherNoRain');
      const tmax = (w.tmax != null) ? ` · ${Math.round(w.tmax)}°C` : '';
      weatherBanner = `<div style="background:${bg};border:1px solid rgba(0,0,0,.06);border-radius:10px;padding:8px 11px;font-size:12px;margin-bottom:8px;color:${tone};font-weight:600">☁️ ${t('weatherTitle')} · ${t('weatherRain', { mm: w.rain3d })}${tmax} → ${tip}</div>`;
    }
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
    practices.innerHTML = weatherBanner + actionCards + better;
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
// Espacement minimal entre deux points (mètres « terrain »). Avec
// ROBOT_WORLD_SCALE=0.15, 1.7 m terrain ≈ 25 cm physiques — la résolution
// réelle du robot (le virage en arc avale déjà ~20 cm). En dessous, deux points
// sont indistinguables sur la parcelle de 1 m².
const MIN_SPACING_M = 1.7;
// Plafond de points de MESURE pour la parcelle prototype (1 m²) : au-delà,
// dérive du dead-reckoning + empreinte robot rendent les mesures non fiables.
// (Le point de départ ne compte pas — il n'est pas mesuré.)
const MAX_PLAN_POINTS = 5;
// Espacement des plans prédéfinis (~27 cm physiques à l'échelle 0.15).
const PRESET_SPACING_M = 1.8;
// Étendue MAX de la parcelle (mètres « terrain ») : les coordonnées x/y des
// points sont bornées à [0, FIELD_MAX_M] dans l'éditeur.
const FIELD_MAX_M = 3.6;
// Valeurs de coordonnées AUTORISÉES (mètres « terrain »). L'éditeur n'expose que
// ces positions discrètes (menus déroulants) : la grille de mesure est calée sur
// un quadrillage fixe et la carte s'adapte dynamiquement aux points choisis.
// Grille uniforme à 1,8 m (≈ 27 cm physiques) ≥ MIN_SPACING_M : espacement au-dessus
// de l'empreinte du virage en arc → déplacement fiable du robot, max 3,6 m.
const ALLOWED_COORDS = [0, 1.8, 3.6];
// Ramène une coordonnée quelconque à la valeur AUTORISÉE la plus proche.
function _snapCoord(v) {
  const n = Number(v) || 0;
  return ALLOWED_COORDS.reduce((best, c) =>
    Math.abs(c - n) < Math.abs(best - n) ? c : best, ALLOWED_COORDS[0]);
}
// Conservé pour compat : borne dans [0, FIELD_MAX_M] PUIS cale sur la grille.
function _clampCoord(v) {
  return _snapCoord(Math.max(0, Math.min(FIELD_MAX_M, Number(v) || 0)));
}

// Génère un plan en SERPENTIN par colonnes (montée/descente), sens validé sur
// le robot — déplacement continu sans saut diagonal. Le 1er point est DÉCALÉ
// d'un pas du coin de départ (0,0) : le robot ROULE jusqu'à lui avant de
// mesurer (pas de mesure « à l'arrêt » sur la position de parking).
function _serpentinePlan(n) {
  // Grille calée sur les valeurs AUTORISÉES bien espacées (0, 1.8, 3.6 m) —
  // toutes à ≥ MIN_SPACING_M l'une de l'autre. Parcours en serpentin par colonne.
  const G = [0, PRESET_SPACING_M, 2 * PRESET_SPACING_M];   // 0, 1.8, 3.6
  const seq = [];
  G.forEach((x, ci) => {
    const ys = ci % 2 === 0 ? G : [...G].reverse();        // alterne ↑ / ↓
    ys.forEach((y) => seq.push({ x, y }));
  });
  // On ne mesure pas sur le coin de parking (0,0) : le robot y démarre.
  const pts = seq.filter((p) => !(p.x === 0 && p.y === 0));
  return pts.slice(0, n).map((p, i) => ({ label: 'P' + (i + 1), x: p.x, y: p.y }));
}

function applyPreset(n) {
  applyPlanPoints(_serpentinePlan(Math.min(n, MAX_PLAN_POINTS)));
  _planApplied = true;
  showToast(t('planApplied', { n }));
  renderAll();
}

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
  .plan-row{display:grid;grid-template-columns:30px 1fr 86px 86px 32px 32px;gap:8px;align-items:center;margin-bottom:8px}
  .plan-idx{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:11px;color:#fff;background:linear-gradient(135deg,#52a85d,#3b7a44);box-shadow:0 2px 5px rgba(59,122,68,.35)}
  .plan-field{position:relative}
  .plan-field .unit{position:absolute;right:9px;top:50%;transform:translateY(-50%);font-size:10px;color:#9aa79a;pointer-events:none}
  .plan-in{width:100%;padding:8px 9px;border:1px solid #dde5dd;border-radius:10px;font:inherit;font-size:13px;background:#fff;transition:border-color .15s,box-shadow .15s}
  .plan-field .plan-in{padding-right:22px}
  .plan-in:focus{outline:none;border-color:#4a9c55;box-shadow:0 0 0 3px rgba(74,156,85,.16)}
  .plan-field .plan-sel{-webkit-appearance:none;-moz-appearance:none;appearance:none;cursor:pointer;padding:8px 30px 8px 11px;font-weight:600;color:#2f4030;text-align:left;background-color:#fff;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath fill='none' stroke='%233b7a44' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round' d='M1 1l4 4 4-4'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 11px center;background-size:10px 6px}
  .plan-field .plan-sel:hover{border-color:#bcd6bd}
  .plan-del{border:none;background:#fbeceb;color:#c0392b;border-radius:9px;height:32px;width:32px;cursor:pointer;font-weight:700;font-size:13px;transition:background .15s,transform .1s}
  .plan-del:hover{background:#f3d4d2}.plan-del:active{transform:scale(.92)}
  .plan-ins{border:none;background:#e7f3e9;color:#2f7a3c;border-radius:9px;height:32px;width:32px;cursor:pointer;font-weight:700;font-size:15px;line-height:1;transition:background .15s,transform .1s}
  .plan-ins:hover{background:#d4ebd8}.plan-ins:active{transform:scale(.92)}
  .plan-label{font-weight:700;color:#3b7a44;background:#f3f8f3;text-align:center;cursor:default}
  .plan-actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
  .plan-actions>button{flex:1;min-width:140px}
  .plan-presets{display:flex;align-items:center;gap:8px;margin:0 0 13px;flex-wrap:wrap}
  .plan-preset-lbl{font-size:12px;font-weight:700;color:#3b7a44}
  .plan-preset-btn{min-width:40px;height:32px;border:1px solid #cfe3cf;background:#fff;color:#2f7a3a;border-radius:9px;font-weight:800;font-size:13px;cursor:pointer;transition:background .15s,transform .1s,border-color .15s}
  .plan-preset-btn:hover{background:#eaf5ea;border-color:#4a9c55}.plan-preset-btn:active{transform:scale(.92)}`;
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
  // Garantit que le modèle reste sur la grille autorisée (plan importé/périmé inclus).
  APP_STATE.plan.forEach((p) => { p.x = _snapCoord(p.x); p.y = _snapCoord(p.y); });
  const coordOpts = (sel) => ALLOWED_COORDS.map((v) =>
    `<option value="${v}"${_snapCoord(sel) === v ? ' selected' : ''}>${v} m</option>`).join('');
  const rows = APP_STATE.plan.map((p, i) => `
    <div class="plan-row">
      <span class="plan-idx">${i + 1}</span>
      <input class="plan-in plan-label" value="${p.label}" readonly tabindex="-1" aria-label="${t('planCol')}"/>
      <span class="plan-field"><select class="plan-in plan-sel" data-i="${i}" data-k="x">${coordOpts(p.x)}</select></span>
      <span class="plan-field"><select class="plan-in plan-sel" data-i="${i}" data-k="y">${coordOpts(p.y)}</select></span>
      <button class="plan-ins" onclick="insertPlanRowAfter(${i})" title="${t('planInsert')}">＋</button>
      <button class="plan-del" onclick="removePlanRow(${i})" title="${t('planRemove')}">✕</button>
    </div>`).join('');
  host.innerHTML = `
    <div class="plan-hd">
      <span class="plan-hd-title">🛰️ ${t('missionPlanTitle')}</span>
      <span class="plan-hd-badge">${APP_STATE.plan.length} ${t('planPoints')}</span>
    </div>
    <div class="plan-sub">${t('planSpacingNote', { d: MIN_SPACING_M })} · ${t('planAllowedNote', { vals: ALLOWED_COORDS.join(' / ') })}</div>
    <div class="plan-presets">
      <span class="plan-preset-lbl">⚡ ${t('planQuick')} :</span>
      <button class="plan-preset-btn" onclick="applyPreset(3)">3</button>
      <button class="plan-preset-btn" onclick="applyPreset(5)">5</button>
    </div>
    <div class="plan-rows">${rows}</div>
    <div class="plan-actions">
      <button class="btn-soft" onclick="addPlanRow()">＋ ${t('planAdd')}</button>
      <button class="btn-primary" onclick="applyPlanFromEditor()">✓ ${t('planApply')}</button>
    </div>`;
  host.querySelectorAll('.plan-in').forEach((inp) => {
    inp.onchange = () => {
      const k = inp.dataset.k;
      if (!k) return;                       // libellé en lecture seule (auto-numéroté)
      const v = _snapCoord(inp.value);      // cale sur une valeur autorisée
      APP_STATE.plan[+inp.dataset.i][k] = v;
      inp.value = v;                        // reflète la valeur calée dans le champ
    };
  });
}

// Renumérote tous les points dans l'ordre courant : P1, P2, … Pn. Appelée après
// tout ajout / insertion / suppression pour que la numérotation suive l'ordre
// réel du parcours (labels = clés côté backend/mesures).
function _renumberPlan() {
  APP_STATE.plan.forEach((p, i) => { p.label = 'P' + (i + 1); });
  APP_STATE.missionRoute = planLabels();
}

function addPlanRow() {
  if (APP_STATE.plan.length >= MAX_PLAN_POINTS) {
    showToast(t('planMax', { n: MAX_PLAN_POINTS }));
    return;
  }
  // Décale le nouveau point de l'espacement min depuis le dernier (jamais superposé).
  const last = APP_STATE.plan[APP_STATE.plan.length - 1] || { x: 0, y: 0 };
  APP_STATE.plan.push({ label: '', x: _clampCoord(last.x + PRESET_SPACING_M), y: _clampCoord(last.y) });
  _renumberPlan();
  renderPlanEditor();
}

// Insère un NOUVEAU point juste APRÈS la ligne i (donc « au milieu » de la liste)
// puis renumérote tout. Position par défaut : milieu du segment i→i+1 ; si ce
// milieu tomberait trop près d'un voisin (points déjà à l'espacement minimal),
// on l'écarte perpendiculairement de MIN_SPACING_M pour rester valide. Le dernier
// point (pas de suivant) se décale comme un ajout simple. L'utilisateur ajuste
// ensuite les coordonnées ; la validation finale a lieu à « Appliquer ».
function insertPlanRowAfter(i) {
  if (APP_STATE.plan.length >= MAX_PLAN_POINTS) {
    showToast(t('planMax', { n: MAX_PLAN_POINTS }));
    return;
  }
  const a = APP_STATE.plan[i] || { x: 0, y: 0 };
  const b = APP_STATE.plan[i + 1];
  let nx, ny;
  if (b) {
    nx = (a.x + b.x) / 2; ny = (a.y + b.y) / 2;
    const tooClose = (px, py) =>
      Math.hypot(px - a.x, py - a.y) < MIN_SPACING_M ||
      Math.hypot(px - b.x, py - b.y) < MIN_SPACING_M;
    if (tooClose(nx, ny)) {
      const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
      nx += (-dy / len) * MIN_SPACING_M;       // écart perpendiculaire au segment
      ny += (dx / len) * MIN_SPACING_M;
    }
  } else {
    nx = a.x + PRESET_SPACING_M; ny = a.y;     // insertion après le dernier point
  }
  APP_STATE.plan.splice(i + 1, 0, {
    label: '', x: _clampCoord(nx), y: _clampCoord(ny),
  });
  _renumberPlan();
  renderPlanEditor();
}

function removePlanRow(i) {
  if (APP_STATE.plan.length <= 1) { showToast(t('planMin')); return; }
  APP_STATE.plan.splice(i, 1);
  _renumberPlan();
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
  _planApplied = true;
  showToast(t('planApplied', { n: pts.length }));
  renderAll();
}

// ---------------------------------------------------------------------------
// Assistant IA de guidage — vit DANS le chatbot et LIT l'interface. Il poste
// des messages très brefs (texte + voix) qui disent à l'utilisateur quoi faire
// et quoi appuyer, attend que l'action soit RÉELLEMENT faite avant de passer à
// la suivante (l'étape n'avance que quand l'état de la mission change), et
// commente l'avancement du robot. L'élément à toucher est mis en SURBRILLANCE
// (pulse). Tout est protégé (try/catch) : ne peut jamais casser l'app.
// ---------------------------------------------------------------------------
const _GUIDE_TXT = {
  fr: {
    welcome: '👋 Bonjour, je suis AgriBot, votre assistant Agribotics.',
    plan: '① Choisissez un préréglage (3 ou 5 points), ou ajoutez vos points un à un. Réglez pour chacun ses coordonnées X et Y. Validez ensuite avec « Appliquer le plan ».',
    start: '② Votre plan est prêt. Appuyez sur « Démarrer mission » pour lancer le robot.',
    running: '🤖 Mission en cours. Ouvrez l’onglet « Carte » pour suivre le robot en direct.',
    progress: (z, m, n) => `✅ Zone ${z} mesurée — ${m}/${n}. Le robot poursuit son parcours.`,
    done: '🎉 Mission terminée. Ouvrez l’onglet « Conseils » pour le bilan par zone.',
    seeMap: 'Voir la carte', seeAdvice: 'Voir les conseils',
    summary: (g, n, bad) => `📊 Bilan : ${g}/${n} zone(s) au vert${bad && bad.length ? ` · à surveiller : ${bad.join(', ')}` : ''}.`,
  },
  ar: {
    welcome: '👋 مرحباً! سأرشدك خطوة بخطوة. اتبع تعليماتي.',
    plan: '① اختر نموذجاً (3 أو 5 نقاط)، أو أضف نقاطك واحدة تلو الأخرى. اضبط لكل نقطة إحداثيي X و Y. ثم صادق بـ « ✓ تطبيق ».',
    start: '② كل شيء جاهز. اضغط الزر الأخضر « ▶ ابدأ المهمة ».',
    running: '🤖 انطلقنا! سآخذك إلى الخريطة لمتابعة الروبوت مباشرة.',
    progress: (z, m, n) => `✅ تم قياس المنطقة ${z} — ${m}/${n}. الروبوت يواصل…`,
    done: '🎉 انتهى! إليك الحصيلة، ثم افتح النصائح لكل منطقة.',
    seeMap: 'عرض الخريطة', seeAdvice: 'عرض النصائح',
    summary: (g, n, bad) => `📊 الحصيلة: ${g}/${n} منطقة جيدة${bad && bad.length ? ` · للمراقبة: ${bad.join('، ')}` : ''}.`,
  },
  da: {
    welcome: '👋 سلام! غادي نوجهك خطوة بخطوة. تبّع التعليمات ديالي.',
    plan: '① ختار نموذج (3 ولا 5 نقط)، ولا زيد النقط وحدة بوحدة. ضبط لكل نقطة إحداثيات X و Y. من بعد صادق بـ « ✓ تطبيق ».',
    start: '② كلشي واجد. كليكي على الزر الأخضر « ▶ بدا المهمة ».',
    running: '🤖 بدينا! غادي نديك للخريطة باش تتبّع الروبو مباشرة.',
    progress: (z, m, n) => `✅ تقاست البلاصة ${z} — ${m}/${n}. الروبو كيكمّل…`,
    done: '🎉 سالا! ها الحصيلة، من بعد حلّ النصائح لكل بلاصة.',
    seeMap: 'شوف الخريطة', seeAdvice: 'شوف النصائح',
    summary: (g, n, bad) => `📊 الحصيلة: ${g}/${n} بلاصة مزيانة${bad && bad.length ? ` · خاصها تراقب: ${bad.join('، ')}` : ''}.`,
  },
};
let _planApplied = false;          // passe à true dès qu'un plan est appliqué
let _guideStarted = false;         // bienvenue déjà postée ?
let _guideLastStep = null;         // dernière étape annoncée
let _guideLastMeasured = -1;       // nb de points mesurés déjà commentés

function _injectGuideStyles() {
  if (document.getElementById('guideStyles')) return;
  const s = document.createElement('style');
  s.id = 'guideStyles';
  s.textContent = `
  .coach-target{position:relative;animation:coachPulse 1.2s infinite;border-radius:12px;outline:3px solid #e0922f;outline-offset:3px}
  @keyframes coachPulse{0%{box-shadow:0 0 0 0 rgba(224,146,47,.65)}70%{box-shadow:0 0 0 17px rgba(224,146,47,0)}100%{box-shadow:0 0 0 0 rgba(224,146,47,0)}}
  .chat-bubble.guide{background:linear-gradient(135deg,#eef8ef,#e2f2e5);border-left:3px solid #3b7a44;font-weight:600}
  .guide-actions{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
  .guide-action{background:#3b7a44;color:#fff;border:none;border-radius:10px;padding:7px 12px;font-weight:700;font-size:12.5px;cursor:pointer;font-family:inherit;transition:background .15s,transform .1s}
  .guide-action:hover{background:#2f6437}.guide-action:active{transform:scale(.95)}
  .guide-confetti{position:fixed;top:-30px;z-index:80;pointer-events:none;will-change:transform,opacity;animation:confFall 2.3s ease-in forwards}
  @keyframes confFall{0%{transform:translateY(0) rotate(0);opacity:1}100%{transform:translateY(108vh) rotate(380deg);opacity:.15}}`;
  document.head.appendChild(s);
}

function _coachStepName() {
  const r = APP_STATE.robot || {};
  if (['requested', 'running', 'moving', 'measuring', 'paused'].includes(r.status)) return 'running';
  if ((r.totalPoints || 0) > 0 && (r.measuredPoints || 0) >= r.totalPoints) return 'done';
  if (!_planApplied && (r.measuredPoints || 0) === 0) return 'plan';
  return 'start';
}

// Met en surbrillance (pulse) l'élément exact à toucher pour l'étape courante.
function _guidePulse(step) {
  _injectGuideStyles();
  const sel = {
    plan: '#planEditor',
    start: '#btnStartReal',
    running: '.bottom-nav .bnav-item:nth-child(2)',   // onglet Carte
    done: '.bottom-nav .bnav-item:nth-child(3)',       // onglet Conseils
  }[step];
  document.querySelectorAll('.coach-target').forEach((e) => e.classList.remove('coach-target'));
  const tgt = sel ? document.querySelector(sel) : null;
  if (tgt) tgt.classList.add('coach-target');
}

// Ajoute une bulle "assistant" dans le fil du chatbot. `actions` (optionnel) =
// liste de { label, on } → boutons cliquables one-tap dans la bulle.
function _guideAdd(text, actions) {
  const box = document.getElementById('chatMessages');
  if (!box) return;
  const b = document.createElement('div');
  b.className = 'chat-bubble bot guide';
  b.textContent = text;
  if (actions && actions.length) {
    const row = document.createElement('div');
    row.className = 'guide-actions';
    actions.forEach((a) => {
      const btn = document.createElement('button');
      btn.className = 'guide-action';
      btn.textContent = a.label;
      btn.onclick = a.on;
      row.appendChild(btn);
    });
    b.appendChild(row);
  }
  box.appendChild(b);
  box.scrollTop = box.scrollHeight;
}

// Navigue vers un onglet du bas (1=Terrain, 2=Carte, 3=Conseils) en cliquant
// l'item correspondant (met aussi à jour l'état actif de la barre).
function _guideGoto(n) {
  try {
    const b = document.querySelector('.bottom-nav .bnav-item:nth-child(' + n + ')');
    if (b) b.click();
  } catch (e) { /* navigation impossible : silencieux */ }
}

// Bilan rapide de fin de mission : compte les zones « au vert » vs à surveiller.
function _missionSummary() {
  try {
    const labels = (typeof planLabels === 'function') ? planLabels() : [];
    let good = 0; const bad = [];
    labels.forEach((z) => {
      const data = APP_STATE.fieldData[z];
      if (!data) return;
      const crop = APP_STATE.zoneCropPlan[z] || APP_STATE.selectedCrop;
      const ev = (typeof evaluateZoneForCrop === 'function') ? evaluateZoneForCrop(data, crop) : null;
      if (!ev) return;
      if (ev.type === 'good') good += 1; else bad.push(z);
    });
    return { good, bad, total: labels.length };
  } catch (e) { return null; }
}

// Petite célébration visuelle (confettis emoji) à la fin de la mission.
function _confetti() {
  try {
    _injectGuideStyles();
    const em = ['🎉', '🌱', '✅', '🎊', '⭐'];
    for (let i = 0; i < 14; i++) {
      const s = document.createElement('div');
      s.className = 'guide-confetti';
      s.textContent = em[i % em.length];
      s.style.left = (Math.random() * 98) + 'vw';
      s.style.animationDelay = (Math.random() * 0.5) + 's';
      s.style.fontSize = (16 + Math.random() * 16) + 'px';
      document.body.appendChild(s);
      setTimeout(() => s.remove(), 2800);
    }
  } catch (e) { /* déco non bloquante */ }
}

// Lit le message à voix haute via la vraie voix du chatbot (cloud AR/DA,
// locale FR), en respectant le bouton muet 🔇/🔊 (window.CHATBOT_SPEAK).
function _guideSpeak(text) {
  try {
    if (typeof window.speakBotAnswer === 'function') {
      if (typeof window.stopBotVoice === 'function') window.stopBotVoice();
      window.speakBotAnswer(String(text).replace(/[①②③🤖🗺️💡🎉👋✓▶«»]/g, '').replace(/\s+/g, ' ').trim());
    }
  } catch (e) { /* voix indisponible : silencieux */ }
}

// Ouvre le panneau du chatbot (sans basculer) pour que l'assistant soit visible.
function _openChatForGuide() {
  const p = document.getElementById('chatPanel');
  const f = document.getElementById('chatFab');
  if (p && !p.classList.contains('open')) {
    p.classList.add('open');
    if (f) f.classList.add('active');
  }
}

// Réinitialise l'assistant (appelé au changement de langue → re-bienvenue).
window._resetGuide = function () {
  _guideStarted = false;
  _guideLastStep = null;
  _guideLastMeasured = -1;
  if (window.Assistant && window.Assistant.reset) window.Assistant.reset();  // re-bonjour dans la nouvelle langue
};

function updateCoach(force) {
  try {
    if (window._guideOff) return;
    // Assistant « tête parlante » (assistant.js) : s'il est présent, il prend en
    // charge tout le guidage (lit l'interface + voix + bulle). On lui délègue et
    // on n'utilise plus les bulles dans le chat (sinon double message).
    if (window.Assistant && window.Assistant.update) { window.Assistant.update(force); return; }
    if (!document.getElementById('chatMessages')) return;     // chat pas encore prêt
    const langScr = document.getElementById('lang-screen');
    if (langScr && getComputedStyle(langScr).display !== 'none') return;  // écran langue ouvert
    const L = _GUIDE_TXT[window.currentLang || 'fr'] || _GUIDE_TXT.fr;
    const r = APP_STATE.robot || {};
    const step = _coachStepName();
    _guidePulse(step);

    let welcomeNow = false;
    if (!_guideStarted) {
      _guideStarted = true;
      welcomeNow = true;
      _openChatForGuide();
      _guideAdd(L.welcome);          // message de bienvenue rapide
    }

    if (force || step !== _guideLastStep) {
      // Nouvelle étape : instruction très brève (+ voix). On NE passe à l'étape
      // suivante que lorsque l'utilisateur a réellement agi (l'état change).
      _guideLastStep = step;
      _guideLastMeasured = r.measuredPoints || 0;
      const instr = L[step];
      // Boutons d'action one-tap selon l'étape.
      let actions = null;
      if (step === 'running') actions = [{ label: '🗺️ ' + L.seeMap, on: () => _guideGoto(2) }];
      if (step === 'done') actions = [{ label: '💡 ' + L.seeAdvice, on: () => _guideGoto(3) }];
      _guideAdd(instr, actions);
      _guideSpeak((welcomeNow ? L.welcome + '. ' : '') + instr);
      // La carte est « demandée » pour observer le robot : on y emmène
      // l'utilisateur dès le démarrage de la mission.
      if (step === 'running') setTimeout(() => _guideGoto(2), 800);
      // Fin de mission : bilan chiffré + célébration.
      if (step === 'done') {
        const sum = _missionSummary();
        if (sum) _guideAdd(L.summary(sum.good, sum.total, sum.bad));
        _confetti();
      }
    } else if (step === 'running') {
      // Même étape : on commente chaque NOUVELLE zone mesurée (avancement robot).
      const m = r.measuredPoints || 0;
      if (m > _guideLastMeasured) {
        _guideLastMeasured = m;
        const msg = L.progress(r.activePoint || ('P' + m), m, r.totalPoints || 0);
        _guideAdd(msg);
        _guideSpeak(msg);
      }
    }
  } catch (e) { /* le guidage ne doit jamais casser l'app */ }
}

function renderAll() {
  applyLanguage();
  renderPlanEditor();
  renderMission();
  renderGauges();
  renderAdvice();
  drawMap();
  updateCoach();
}

// ---------------------------------------------------------------------------
// Lanceur de chatbot : remplace la grande barre de chat par une icône
// flottante Agri-Botics (le panneau s'ouvre/se ferme). Injecté en JS pour
// rester présent dans toutes les variantes HTML sans les modifier.
// ---------------------------------------------------------------------------
function _injectChatStyles() {
  if (document.getElementById('chatLauncherStyles')) return;
  const s = document.createElement('style');
  s.id = 'chatLauncherStyles';
  s.textContent = `
  .chat-fab{position:fixed;right:18px;bottom:84px;width:60px;height:60px;border-radius:50%;border:none;cursor:pointer;background:linear-gradient(135deg,#52a85d,#2f7a3a);color:#fff;font-size:27px;box-shadow:0 8px 22px rgba(20,60,25,.42);z-index:60;display:grid;place-items:center;transition:transform .15s}
  .chat-fab:hover{transform:scale(1.06)} .chat-fab.active{transform:scale(.9)}
  .chat-fab::after{content:'';position:absolute;top:7px;right:8px;width:11px;height:11px;border-radius:50%;background:#ffd23f;box-shadow:0 0 0 2px #fff;animation:fabPulse 2s infinite}
  @keyframes fabPulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.25);opacity:.7}}
  .chat-panel{position:fixed;right:18px;bottom:84px;width:min(520px,96vw);height:min(680px,84vh);background:#fff;border-radius:18px;box-shadow:0 16px 44px rgba(0,0,0,.28);display:flex;flex-direction:column;overflow:hidden;z-index:61;transform:translateY(16px) scale(.96);opacity:0;pointer-events:none;transition:transform .2s,opacity .2s}
  .chat-panel.open{transform:none;opacity:1;pointer-events:auto}
  .chat-panel-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 14px;background:linear-gradient(135deg,#3b7a44,#2f6437);color:#fff;font-weight:800;font-size:14px;cursor:move;user-select:none}
  .chat-head-actions{display:flex;gap:6px;align-items:center}
  .chat-close,.chat-icon-btn{background:rgba(255,255,255,.2);border:none;color:#fff;width:28px;height:28px;border-radius:8px;cursor:pointer;font-weight:700;font-size:14px}
  .chat-close:hover,.chat-icon-btn:hover{background:rgba(255,255,255,.34)}
  .chat-panel .chatbot-card{box-shadow:none;border-radius:0;margin:0;flex:1;min-height:0;overflow:auto;display:flex;flex-direction:column}
  /* Dans le panneau flottant (haut), la zone des messages occupe toute la place
     disponible au lieu d'être bridée à 340px → bien plus de texte visible. */
  .chat-panel .chat-messages{max-height:none;flex:1 1 auto;min-height:0}
  /* Poignée de redimensionnement (coin bas-droit) */
  .chat-resize{position:absolute;right:0;bottom:0;width:20px;height:20px;cursor:nwse-resize;z-index:62;background:linear-gradient(135deg,transparent 45%,rgba(59,122,68,.35) 45%,rgba(59,122,68,.6));border-bottom-right-radius:18px}
  /* Suggestions de suivi (texte faible, validables/effaçables) */
  .chat-followups{display:flex;flex-wrap:wrap;gap:6px;padding:8px 4px 2px}
  .chat-followup{background:transparent;border:1px dashed #b9cdb9;color:#7c8a7c;font-size:12px;padding:5px 10px;border-radius:14px;cursor:pointer;opacity:.72;transition:opacity .15s,background .15s,color .15s,border-style .15s;font-family:inherit}
  .chat-followup:hover{opacity:1;background:#eef5ee;color:#2f7a3a;border-style:solid}
  .chat-followup.dismiss{border-color:#e6c9c9;color:#b85c5c;opacity:.6;padding:5px 9px}
  /* Vue historique (conversations archivées) */
  .chat-hist-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 2px 10px;border-bottom:1px solid #eee;margin-bottom:8px;font-weight:800;color:#2f6437;font-size:13px}
  .chat-hist-back{background:#eef5ee;border:1px solid #cfe0cf;color:#2f7a3a;border-radius:8px;padding:4px 10px;cursor:pointer;font-weight:700;font-size:12px}
  .chat-hist-sep{font-size:11px;color:#9aa79a;text-align:center;margin:12px 0 4px;font-weight:700}
  .chat-bubble.archived{opacity:.85}
  /* Bouton voix : indicateur d'état muté (🔇 rouge) vs activé (🔊) */
  #muteBtn{transition:background .15s,color .15s,box-shadow .15s}
  #muteBtn.muted{background:#fbeceb;color:#c0392b;box-shadow:inset 0 0 0 1.5px #e6b3ae}`;
  document.head.appendChild(s);
}

function setupChatLauncher() {
  const card = document.querySelector('.chatbot-card');
  if (!card || document.getElementById('chatFab')) return;
  _injectChatStyles();

  const panel = document.createElement('div');
  panel.id = 'chatPanel';
  panel.className = 'chat-panel';

  const head = document.createElement('div');
  head.className = 'chat-panel-head';
  head.innerHTML = `<span>🚜 Agri-Botics</span>
    <div class="chat-head-actions">
      <button class="chat-icon-btn" onclick="openChatHistory()" title="Historique" aria-label="Historique">🕘</button>
      <button class="chat-close" onclick="toggleChatPanel()" aria-label="Fermer">✕</button>
    </div>`;
  panel.appendChild(head);
  panel.appendChild(card);
  // Le panneau vit au niveau du <body> (position:fixed) et NON dans une page :
  // sinon il est masqué quand on quitte l'onglet Terrain (carte / conseils).
  document.body.appendChild(panel);
  // Déplaçable (drag par l'en-tête) + redimensionnable (poignée bas-droit).
  _enableChatDragResize(panel, head);

  const fab = document.createElement('button');
  fab.id = 'chatFab';
  fab.className = 'chat-fab';
  fab.innerHTML = '🚜';
  fab.title = t('chatTitle');
  fab.onclick = toggleChatPanel;
  document.body.appendChild(fab);

  // Démarre l'assistant de guidage maintenant que le chat existe.
  updateCoach();
}

function toggleChatPanel() {
  const p = document.getElementById('chatPanel');
  const f = document.getElementById('chatFab');
  if (!p) return;
  const open = p.classList.toggle('open');
  if (f) f.classList.toggle('active', open);
  // Ouvrir OU fermer le chat coupe toute lecture vocale en cours (sinon la voix
  // continue après la fermeture du panneau).
  try { if (window.stopBotVoice) window.stopBotVoice(); } catch (_) {}
}

// Rend le panneau chatbot DÉPLAÇABLE (drag par l'en-tête) et REDIMENSIONNABLE
// (poignée bas-droit). Au 1er geste, on "épingle" le panneau en left/top/width/
// height (au lieu de right/bottom ancrés) pour que déplacement et resize soient
// naturels. Compatible souris + tactile.
function _enableChatDragResize(panel, head) {
  let pinned = false;
  function pin() {
    if (pinned) return;
    const r = panel.getBoundingClientRect();
    panel.style.left = r.left + 'px'; panel.style.top = r.top + 'px';
    panel.style.right = 'auto'; panel.style.bottom = 'auto';
    panel.style.width = r.width + 'px'; panel.style.height = r.height + 'px';
    pinned = true;
  }
  const clampX = (x) => Math.max(4, Math.min(window.innerWidth - 60, x));
  const clampY = (y) => Math.max(4, Math.min(window.innerHeight - 60, y));

  function startDrag(cx, cy, isTouch) {
    pin();
    const r = panel.getBoundingClientRect();
    const ox = cx - r.left, oy = cy - r.top;
    const move = (ev) => {
      const pt = isTouch ? ev.touches[0] : ev;
      if (!pt) return;
      panel.style.left = clampX(pt.clientX - ox) + 'px';
      panel.style.top = clampY(pt.clientY - oy) + 'px';
      if (isTouch && ev.cancelable) ev.preventDefault();
    };
    const end = () => {
      document.removeEventListener(isTouch ? 'touchmove' : 'mousemove', move);
      document.removeEventListener(isTouch ? 'touchend' : 'mouseup', end);
    };
    document.addEventListener(isTouch ? 'touchmove' : 'mousemove', move, { passive: false });
    document.addEventListener(isTouch ? 'touchend' : 'mouseup', end);
  }

  head.addEventListener('mousedown', (e) => {
    if (e.target.closest('button')) return;   // boutons 🕘 / ✕ : pas de drag
    startDrag(e.clientX, e.clientY, false);
    e.preventDefault();
  });
  head.addEventListener('touchstart', (e) => {
    if (e.target.closest('button')) return;
    const t0 = e.touches[0];
    if (t0) startDrag(t0.clientX, t0.clientY, true);
  }, { passive: true });

  // Poignée de redimensionnement (coin bas-droit).
  const handle = document.createElement('div');
  handle.className = 'chat-resize';
  handle.title = 'Redimensionner';
  panel.appendChild(handle);
  function startResize(cx, cy, isTouch) {
    pin();
    const r = panel.getBoundingClientRect();
    const w0 = r.width, h0 = r.height;
    const move = (ev) => {
      const pt = isTouch ? ev.touches[0] : ev;
      if (!pt) return;
      panel.style.width = Math.max(280, Math.min(window.innerWidth - 20, w0 + (pt.clientX - cx))) + 'px';
      panel.style.height = Math.max(320, Math.min(window.innerHeight - 20, h0 + (pt.clientY - cy))) + 'px';
      if (isTouch && ev.cancelable) ev.preventDefault();
    };
    const end = () => {
      document.removeEventListener(isTouch ? 'touchmove' : 'mousemove', move);
      document.removeEventListener(isTouch ? 'touchend' : 'mouseup', end);
    };
    document.addEventListener(isTouch ? 'touchmove' : 'mousemove', move, { passive: false });
    document.addEventListener(isTouch ? 'touchend' : 'mouseup', end);
  }
  handle.addEventListener('mousedown', (e) => { startResize(e.clientX, e.clientY, false); e.preventDefault(); e.stopPropagation(); });
  handle.addEventListener('touchstart', (e) => { const t0 = e.touches[0]; if (t0) startResize(t0.clientX, t0.clientY, true); e.stopPropagation(); }, { passive: true });
}

document.addEventListener('DOMContentLoaded', () => {
  populateCropSelects();
  renderAll();
  setupChatLauncher();
  // Météo (Open-Meteo) : enrichit l'irrigation ; re-rendu quand dispo.
  if (typeof window.fetchWeather === 'function') {
    window.fetchWeather().then(() => renderAll()).catch(() => {});
  }
});
window.addEventListener('resize', drawMap);
