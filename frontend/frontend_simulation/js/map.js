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

// --- Fond satellite : vraie photo si disponible, sinon mosaïque aérienne ---
// Pose une photo (drone/satellite) à assets/parcelle.jpg et elle sera utilisée
// automatiquement ; sinon repli sur une mosaïque agricole procédurale.
const MAP_BG_URL = (typeof window !== 'undefined' && window.AGRIBOTICS_MAP_BG) || 'assets/parcelle.jpg';
let _bgImg = null, _bgFailed = false;
function _bgImage() {
  if (_bgFailed || typeof Image === 'undefined') return null;
  if (!_bgImg) {
    _bgImg = new Image();
    _bgImg.onload = () => drawMap();
    _bgImg.onerror = () => { _bgFailed = true; };
    _bgImg.src = MAP_BG_URL;
  }
  return (_bgImg.complete && _bgImg.naturalWidth) ? _bgImg : null;
}

// --- Image du robot (remplace l'emoji 🤖) -----------------------------------
// Photo du robot réel posée à assets/robot.png ; repli emoji si absente.
const ROBOT_IMG_URL = (typeof window !== 'undefined' && window.AGRIBOTICS_ROBOT_IMG) || 'assets/robot.png';
let _robotImg = null, _robotImgFailed = false;
function _robotImage() {
  if (_robotImgFailed || typeof Image === 'undefined') return null;
  if (!_robotImg) {
    _robotImg = new Image();
    _robotImg.onload = () => drawMap();
    _robotImg.onerror = () => { _robotImgFailed = true; };
    _robotImg.src = ROBOT_IMG_URL;
  }
  return (_robotImg.complete && _robotImg.naturalWidth) ? _robotImg : null;
}

// --- Animation fluide du robot (glissement + cap, façon caméra de suivi) -----
// Position du robot en coordonnées PLAN (mètres) : on interpole de l'ancien
// point vers le point actif sur une durée fixe avec accélération douce, plutôt
// que de « sauter ». drawMap() dessine la position courante ; _robotRAF anime.
const _robot = { x: null, y: null, fromX: 0, fromY: 0, toX: 0, toY: 0,
                 t0: 0, dur: 900, animating: false, angle: 0, targetLabel: null };
let _robotRAF = null;
const _easeInOut = (u) => (u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2);

// Glisser-déposer d'un point de mesure sur la carte.
let _drag = null, _suppressClick = false;

// Synchronise la cible d'animation avec le point actif du robot (appelé par
// drawMap). Démarre la boucle RAF si une nouvelle cible apparaît.
function _startPoint() {
  return (typeof START_POINT !== 'undefined') ? START_POINT : { label: 'Départ', x: 0, y: 0 };
}

function _syncRobotTarget() {
  const label = APP_STATE.robot && APP_STATE.robot.activePoint;
  let p = label ? planPoint(label) : null;
  // Point actif inconnu du plan (HOME / Départ / pas encore en mission) → le
  // robot stationne au DÉPART (coin), d'où il glissera vers le 1er point mesuré.
  const key = p ? label : '__start__';
  if (!p) p = _startPoint();
  if (_robot.x === null) {            // 1re apparition : placer sans glisser
    _robot.x = p.x; _robot.y = p.y; _robot.targetLabel = key;
    return;
  }
  if (key !== _robot.targetLabel) {   // nouvelle cible → lancer le glissement
    _robot.fromX = _robot.x; _robot.fromY = _robot.y;
    _robot.toX = p.x; _robot.toY = p.y;
    _robot.t0 = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    _robot.animating = true;
    _robot.targetLabel = key;
    if (!_robotRAF) _robotRAF = requestAnimationFrame(_robotStep);
  }
}

function _robotStep() {
  const now = (typeof performance !== 'undefined' ? performance.now() : Date.now());
  const u = Math.min(1, (now - _robot.t0) / _robot.dur);
  const e = _easeInOut(u);
  _robot.x = _robot.fromX + (_robot.toX - _robot.fromX) * e;
  _robot.y = _robot.fromY + (_robot.toY - _robot.fromY) * e;
  drawMap();
  if (u < 1) {
    _robotRAF = requestAnimationFrame(_robotStep);
  } else {
    _robot.animating = false; _robotRAF = null;
  }
}

// Dessine le robot (image ronde + halo de suivi + cap) à sa position animée.
function _drawRobot(ctx, project, pxPerM, r) {
  if (_robot.x === null) return;
  const s = project(_robot.x, _robot.y);
  const size = Math.max(26, r * 2.0);

  // cap : direction du déplacement courant (repère écran)
  const a = project(_robot.fromX, _robot.fromY), b = project(_robot.toX, _robot.toY);
  const dx = b.x - a.x, dy = b.y - a.y;
  if (_robot.animating && (dx || dy)) _robot.angle = Math.atan2(dy, dx);

  // halo pulsé pendant le déplacement
  if (_robot.animating) {
    const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 180);
    ctx.beginPath(); ctx.arc(s.x, s.y, size / 2 + 6 + pulse * 4, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(124,196,90,${0.18 + pulse * 0.12})`; ctx.fill();
  }

  // jeton circulaire : image du robot détourée en cercle
  const img = _robotImage();
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 3;
  ctx.beginPath(); ctx.arc(s.x, s.y, size / 2, 0, Math.PI * 2);
  ctx.fillStyle = '#fff'; ctx.fill();
  ctx.restore();
  if (img) {
    ctx.save();
    ctx.beginPath(); ctx.arc(s.x, s.y, size / 2 - 1.5, 0, Math.PI * 2); ctx.clip();
    const m = Math.min(img.naturalWidth, img.naturalHeight);
    ctx.drawImage(img, (img.naturalWidth - m) / 2, (img.naturalHeight - m) / 2, m, m,
                  s.x - size / 2, s.y - size / 2, size, size);
    ctx.restore();
  } else {
    ctx.font = `${Math.round(size * 0.7)}px serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('🤖', s.x, s.y);
    ctx.textBaseline = 'alphabetic';
  }

  // anneau + petite flèche de cap
  ctx.beginPath(); ctx.arc(s.x, s.y, size / 2, 0, Math.PI * 2);
  ctx.strokeStyle = '#7cc45a'; ctx.lineWidth = 3; ctx.stroke();
  ctx.save();
  ctx.translate(s.x, s.y); ctx.rotate(_robot.angle);
  ctx.beginPath();
  ctx.moveTo(size / 2 + 9, 0); ctx.lineTo(size / 2 + 2, -5); ctx.lineTo(size / 2 + 2, 5);
  ctx.closePath();
  ctx.fillStyle = '#7cc45a'; ctx.fill();
  ctx.restore();
}

// Marqueur du point de DÉPART (coin) : losange « maison » distinct des points
// de mesure, sans valeur — c'est la base du robot, jamais mesurée.
function _drawStart(ctx, pt, r) {
  const s = Math.max(9, r * 0.85);
  ctx.save();
  ctx.translate(pt.x, pt.y);
  ctx.shadowColor = 'rgba(0,0,0,0.40)'; ctx.shadowBlur = 7; ctx.shadowOffsetY = 2;
  ctx.beginPath();                     // losange
  ctx.moveTo(0, -s); ctx.lineTo(s, 0); ctx.lineTo(0, s); ctx.lineTo(-s, 0); ctx.closePath();
  ctx.fillStyle = '#2f3e46'; ctx.fill();
  ctx.restore();
  ctx.beginPath();
  ctx.moveTo(0 + pt.x, -s + pt.y); ctx.lineTo(s + pt.x, 0 + pt.y);
  ctx.lineTo(0 + pt.x, s + pt.y); ctx.lineTo(-s + pt.x, 0 + pt.y); ctx.closePath();
  ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.lineWidth = 2; ctx.stroke();
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center';
  ctx.font = `${Math.round(s * 0.9)}px serif`;
  ctx.textBaseline = 'middle'; ctx.fillText('🏠', pt.x, pt.y + 0.5); ctx.textBaseline = 'alphabetic';
  ctx.font = '800 10px DM Sans';
  ctx.fillText(t('start') || 'Départ', pt.x, pt.y - s - 5);
}

// Trajet planifié (ordre du plan) : polyligne pointillée pour matérialiser le
// parcours du robot — segment « parcouru » plus marqué jusqu'au robot.
function _drawRoute(ctx, placed) {
  if (placed.length < 2) return;
  ctx.save();
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  ctx.setLineDash([5, 5]);
  ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = 2;
  ctx.beginPath();
  placed.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
  ctx.stroke();
  ctx.restore();
}

// Mosaïque agricole vue du ciel (parcelles irrégulières, sillons, haies, piste).
function drawAerial(ctx, W, H) {
  const rnd = _rng(20240529);
  ctx.fillStyle = '#5b6a36';
  ctx.fillRect(0, 0, W, H);

  const palette = ['#6f7d3e', '#86843f', '#9c7e3b', '#5d6e34', '#7c8c47', '#b2a65c', '#6b5836', '#90a14f', '#a98b46'];
  const cols = 4, rows = 3, cw = W / cols, ch = H / rows;
  const jx = cw * 0.22, jy = ch * 0.22;
  const cnr = (c, r) => ({ x: c * cw + (rnd() - 0.5) * jx, y: r * ch + (rnd() - 0.5) * jy });
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const a = cnr(c, r), b = cnr(c + 1, r), d = cnr(c + 1, r + 1), e = cnr(c, r + 1);
      const cx = (a.x + d.x) / 2, cy = (a.y + d.y) / 2;
      const col = palette[(rnd() * palette.length) | 0];
      ctx.beginPath();
      ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.lineTo(d.x, d.y); ctx.lineTo(e.x, e.y); ctx.closePath();
      ctx.fillStyle = col; ctx.fill();
      // sillons orientés par parcelle
      ctx.save(); ctx.clip();
      ctx.translate(cx, cy); ctx.rotate(rnd() * Math.PI);
      ctx.globalAlpha = 0.13; ctx.strokeStyle = 'rgba(0,0,0,0.55)'; ctx.lineWidth = 1;
      const span = Math.max(cw, ch) * 1.5;
      for (let yy = -span; yy <= span; yy += 5) {
        ctx.beginPath(); ctx.moveTo(-span, yy); ctx.lineTo(span, yy); ctx.stroke();
      }
      ctx.restore();
      // haie / bordure de parcelle
      ctx.beginPath();
      ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.lineTo(d.x, d.y); ctx.lineTo(e.x, e.y); ctx.closePath();
      ctx.strokeStyle = 'rgba(38,52,28,0.55)'; ctx.lineWidth = 2.2; ctx.stroke();
    }
  }

  // piste / chemin de terre sinueux
  ctx.save();
  ctx.strokeStyle = 'rgba(176,150,96,0.55)'; ctx.lineWidth = Math.max(6, W * 0.018);
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(-10, H * 0.7);
  ctx.bezierCurveTo(W * 0.3, H * 0.55, W * 0.5, H * 0.85, W + 10, H * 0.45);
  ctx.stroke();
  ctx.restore();

  // grain / speckle
  for (let i = 0; i < 240; i++) {
    const sx = rnd() * W, sy = rnd() * H;
    ctx.fillStyle = rnd() > 0.5 ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)';
    ctx.fillRect(sx, sy, 2, 2);
  }
}

// Compose le fond de carte : photo satellite si présente, sinon mosaïque ;
// clip arrondi + vignette + voile sombre pour le contraste des marqueurs.
function drawBackground(ctx, W, H, rad) {
  ctx.save();
  roundRect(ctx, 0, 0, W, H, rad);
  ctx.clip();

  const img = _bgImage();
  if (img) {
    const ar = img.naturalWidth / img.naturalHeight, car = W / H;
    let dw, dh;
    if (ar > car) { dh = H; dw = H * ar; } else { dw = W; dh = W / ar; }
    ctx.drawImage(img, (W - dw) / 2, (H - dh) / 2, dw, dh);
    ctx.fillStyle = 'rgba(18,28,16,0.20)'; ctx.fillRect(0, 0, W, H);   // voile contraste
  } else {
    drawAerial(ctx, W, H);
  }

  const vg = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.32, W / 2, H / 2, Math.max(W, H) * 0.72);
  vg.addColorStop(0, 'rgba(0,0,0,0)');
  vg.addColorStop(1, 'rgba(0,0,0,0.30)');
  ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);
  ctx.restore();

  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
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
  // Origine du plan (minX, minY = point de départ du robot) ANCRÉE dans le coin
  // bas-gauche, +x vers la droite et +y (Nord) vers le HAUT (cohérent avec la
  // rose des vents). Le robot part donc d'un coin, pas du centre.
  const padX = W * pad, padY = H * pad;
  const project = (px, py) => ({
    x: spanX < 1e-6 ? W / 2 : padX + (px - b.minX) * s,
    y: spanY < 1e-6 ? H / 2 : H - padY - (py - b.minY) * s,
  });
  // Inverse de project : écran (px) → plan (mètres). Utilisé pour déplacer un
  // point en le glissant sur la carte.
  const invert = (sx, sy) => ({
    x: spanX < 1e-6 ? b.minX : b.minX + (sx - padX) / s,
    y: spanY < 1e-6 ? b.minY : b.minY + (H - padY - sy) / s,
  });
  const placed = plan.map((p) => {
    const xy = project(p.x, p.y);
    return { label: p.label, x: xy.x, y: xy.y };
  });
  return { placed, pxPerM: s, span: Math.max(spanX, spanY), project, invert };
}

// Rayon des marqueurs adapté au nombre de points (légèrement agrandi).
function _markerRadius(n) { return Math.max(9, Math.min(30, 52 / Math.sqrt(n))); }

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
  canvas.height = W;                 // carte CARRÉE (parcelle carrée)
  const H = canvas.height;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, W, H);

  // 1) Fond : photo satellite si dispo, sinon mosaïque aérienne procédurale
  drawBackground(ctx, W, H, 18);

  // 2) Disposition réelle (distances préservées) — le point de DÉPART est
  // inclus dans les bornes pour qu'il s'ancre au coin, mais n'est PAS un point
  // de mesure : on le dessine à part et on l'exclut des marqueurs/clics.
  const plan = currentPlan();
  const n = Math.max(1, plan.length);
  const pad = 0.12;
  const layoutPts = [_startPoint(), ...plan];
  const layout = _layoutField(layoutPts, W, H, pad);
  const { pxPerM, span, project, invert } = layout;
  const startPlaced = layout.placed[0];
  const placed = layout.placed.slice(1);              // points de mesure seuls
  const r = _markerRadius(n);

  // 2b) Trajet planifié : départ → 1er point, puis le serpentin
  _drawRoute(ctx, [startPlaced, ...placed]);

  // 2c) Marqueur du point de départ (coin)
  _drawStart(ctx, startPlaced, r);

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

  // 4) Robot animé sur le point actif (glissement fluide + cap + halo)
  _syncRobotTarget();
  _drawRobot(ctx, project, pxPerM, r);

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
    if (_suppressClick) { _suppressClick = false; return; }  // fin d'un glisser
    selectZone(zoneAt(e));
    showPage('reco', document.querySelector('[onclick*=reco]'));
  };

  // Glisser-déposer d'un point sur la carte (comme déplacer un pion) — pointer
  // events → souris ET tactile. Le glisser modifie les coordonnées du point ;
  // un simple clic (sans déplacement) sélectionne la zone comme avant.
  canvas.style.touchAction = 'none';
  const _toCanvas = (e) => {
    const rect = canvas.getBoundingClientRect();
    return { x: (e.clientX - rect.left) * (W / rect.width),
             y: (e.clientY - rect.top) * (H / rect.height) };
  };
  canvas.onpointerdown = (e) => {
    const c = _toCanvas(e);
    let best = -1, bd = 1e9;
    placed.forEach((p, i) => { const d = Math.hypot(c.x - p.x, c.y - p.y); if (d < bd) { bd = d; best = i; } });
    if (best >= 0 && bd <= r + 8) {
      _drag = { i: best, moved: false };
      try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
    }
  };
  canvas.onpointermove = (e) => {
    if (!_drag) return;
    const c = _toCanvas(e);
    const pm = invert(c.x, c.y);
    APP_STATE.plan[_drag.i].x = Math.round(pm.x * 100) / 100;
    APP_STATE.plan[_drag.i].y = Math.round(pm.y * 100) / 100;
    _drag.moved = true;
    drawMap();
  };
  canvas.onpointerup = () => {
    if (!_drag) return;
    if (_drag.moved && typeof renderPlanEditor === 'function') {
      _suppressClick = true;        // empêche la sélection juste après un glisser
      renderPlanEditor();           // reflète les nouvelles coordonnées dans l'éditeur
    }
    _drag = null;
    drawMap();
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
