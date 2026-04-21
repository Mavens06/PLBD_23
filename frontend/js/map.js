let currentVar = 'humidity';
const GRID_POINT_OFFSETS = [-6, -2, 1, -4, 0, 2, -5, -1, 3];
const PH_OFFSET_MULTIPLIER = 0.05;
const DEFAULT_OFFSET_MULTIPLIER = 0.3;
const ZONE_POINTS = [
  { zone: 'A1', x: 0.15, y: 0.2 }, { zone: 'A2', x: 0.5, y: 0.2 }, { zone: 'A3', x: 0.85, y: 0.2 },
  { zone: 'B1', x: 0.15, y: 0.5 }, { zone: 'B2', x: 0.5, y: 0.5 }, { zone: 'B3', x: 0.85, y: 0.5 },
  { zone: 'C1', x: 0.15, y: 0.8 }, { zone: 'C2', x: 0.5, y: 0.8 }, { zone: 'C3', x: 0.85, y: 0.8 },
];

const mapConfigs = {
  humidity: { label: '💧 Humidité du sol', unit: '%', min: 20, max: 75, grad: 'linear-gradient(90deg,#c0392b,#f5eed8,#4a9c55)' },
  ph: { label: '🧪 pH du sol', unit: '', min: 4.5, max: 8, grad: 'linear-gradient(90deg,#c0392b,#f9c74f,#2d6a35)' },
  ec: { label: '⚡ Conductivité', unit: 'mS/cm', min: 0.3, max: 3.5, grad: 'linear-gradient(90deg,#e8f5e9,#4a9c55,#c0392b)' },
  temp: { label: '🌡️ Température du sol', unit: '°C', min: 8, max: 33, grad: 'linear-gradient(90deg,#aee4f0,#4a9c55,#c0392b)' },
};

function variableValue(pointIdx) {
  const s = APP_STATE.sensors;
  const base = { humidity: s.humidity, ph: s.ph, ec: s.ec, temp: s.temp }[currentVar];
  return +(base + (currentVar === 'ph'
    ? GRID_POINT_OFFSETS[pointIdx] * PH_OFFSET_MULTIPLIER
    : GRID_POINT_OFFSETS[pointIdx] * DEFAULT_OFFSET_MULTIPLIER)).toFixed(2);
}

function colorFor(v, min, max) {
  const t = Math.max(0, Math.min(1, (v - min) / (max - min)));
  const r = Math.round(192 - 80 * t);
  const g = Math.round(57 + 130 * t);
  const b = Math.round(43 + 40 * t);
  return `rgb(${r},${g},${b})`;
}

function drawMap() {
  const canvas = document.getElementById('fieldMap');
  if (!canvas) return;
  const W = canvas.offsetWidth || 340;
  canvas.width = W;
  canvas.height = Math.round(W * 0.62);
  const H = canvas.height;
  const ctx = canvas.getContext('2d');
  const cfg = mapConfigs[currentVar];

  ctx.clearRect(0, 0, W, H);

  ZONE_POINTS.forEach((p, i) => {
    const cx = p.x * W;
    const cy = p.y * H;
    const v = variableValue(i);
    const color = colorFor(v, cfg.min, cfg.max);
    ctx.beginPath();
    ctx.arc(cx, cy, 42, 0, Math.PI * 2);
    ctx.fillStyle = `${color.replace('rgb', 'rgba').replace(')', ',0.35)')}`;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.9)';
    ctx.font = '10px DM Sans';
    ctx.textAlign = 'center';
    ctx.fillText(p.zone, cx, cy + 18);
  });

  const active = ZONE_POINTS.find((p) => p.zone === APP_STATE.robot.activePoint) || ZONE_POINTS[4];
  ctx.beginPath();
  ctx.arc(active.x * W, active.y * H - 22, 12, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255,210,0,0.95)';
  ctx.fill();
  ctx.strokeStyle = '#7a5800';
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillText('🤖', active.x * W, active.y * H - 17);

  document.getElementById('mapVarLabel').textContent = cfg.label;
  document.getElementById('mapScaleBar').style.background = cfg.grad;
  document.getElementById('mapScaleLabels').innerHTML = `<span>${cfg.min}${cfg.unit}</span><span>${cfg.max}${cfg.unit}</span>`;

  canvas.onmousemove = (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const nearest = ZONE_POINTS
      .map((p, i) => ({ ...p, i, d: Math.hypot(x - p.x * W, y - p.y * H) }))
      .sort((a, b) => a.d - b.d)[0];
    const val = variableValue(nearest.i);
    const tip = document.getElementById('mapTooltip');
    tip.textContent = `${nearest.zone} — ${val}${cfg.unit ? ' ' + cfg.unit : ''}`;
    tip.style.left = `${Math.min(x + 10, W - 120)}px`;
    tip.style.top = `${Math.max(y - 30, 0)}px`;
    tip.classList.add('show');
  };
  canvas.onmouseleave = () => document.getElementById('mapTooltip').classList.remove('show');

  canvas.onclick = (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const nearest = ZONE_POINTS
      .map((p, i) => ({ ...p, i, d: Math.hypot(x - p.x * W, y - p.y * H) }))
      .sort((a, b) => a.d - b.d)[0];
    const val = variableValue(nearest.i);
    document.getElementById('zoneDetailTitle').textContent = `Zone ${nearest.zone}`;
    document.getElementById('zoneDetailTags').innerHTML = `<span class="zone-tag" style="background:#e8f5e9;color:#2d6a35">${cfg.label} : ${val}${cfg.unit ? ' ' + cfg.unit : ''}</span>`;
    document.getElementById('zoneDetail').classList.add('visible');
  };
}

function setVar(v, el) {
  currentVar = v;
  document.querySelectorAll('.map-var-btn').forEach((b) => b.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('zoneDetail').classList.remove('visible');
  drawMap();
}
