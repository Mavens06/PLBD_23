function showPage(id, btn) {
  document.querySelectorAll('.page').forEach((p) => p.classList.remove('active'));
  document.querySelectorAll('.bnav-item').forEach((b) => b.classList.remove('active'));
  document.getElementById(`page-${id}`).classList.add('active');
  btn?.classList.add('active');
  if (id === 'map') setTimeout(drawMap, 80);
  if (id === 'tech') setTimeout(drawPhChart, 80);
}

function renderMission() {
  document.getElementById('missionName').textContent = APP_STATE.robot.mission;
  document.getElementById('robotPoint').textContent = `Point ${APP_STATE.robot.activePoint}`;
  document.getElementById('missionProgress').textContent = `${APP_STATE.robot.progress}%`;
}

function statusFor(sensor) {
  if (sensor === 'humidity') return APP_STATE.sensors.humidity < 45 ? ['warn', 'Arrosage conseillé'] : ['good', 'Humidité correcte'];
  if (sensor === 'ph') return APP_STATE.sensors.ph < 6 || APP_STATE.sensors.ph > 7.8 ? ['warn', 'pH à corriger'] : ['good', 'pH stable'];
  if (sensor === 'ec') return APP_STATE.sensors.ec > 1.8 ? ['warn', 'Conductivité élevée'] : ['good', 'Conductivité correcte'];
  return APP_STATE.sensors.temp > 30 ? ['warn', 'Sol chaud'] : ['good', 'Température stable'];
}

function renderGauges() {
  const map = [
    ['water', 'humidity', '%', APP_STATE.sensors.humidity],
    ['ph', 'ph', '', APP_STATE.sensors.ph],
    ['ec', 'ec', ' mS/cm', APP_STATE.sensors.ec],
    ['temp', 'temp', ' °C', APP_STATE.sensors.temp],
  ];

  map.forEach(([id, key, unit, val]) => {
    const [level, label] = statusFor(key);
    const el = document.getElementById(`stat-${id}`);
    el.className = `gauge-status ${level}`;
    el.textContent = `${val}${unit} · ${label}`;
  });
}

function renderReco() {
  const list = document.getElementById('topActions');
  const actions = (window.RECO_ACTIONS || []).slice(0, 3);
  const fallback = [
    { title: 'Irrigation légère', detail: '12–18 mm sur A1/B1.', priority: 'high' },
    { title: 'Suivi salinité', detail: 'Contrôler B1/B2 si EC monte.', priority: 'medium' },
    { title: 'Passage robot', detail: 'Finaliser les points restants.', priority: 'low' },
  ];
  const source = actions.length ? actions : fallback;

  list.innerHTML = source.map((a) => {
    const cls = a.priority === 'high' ? 'urgent' : a.priority === 'medium' ? 'warn' : 'good';
    const badge = a.priority === 'high' ? 'Urgent' : a.priority === 'medium' ? 'Action' : 'Suivi';
    return `<div class="zone-practice-card ${cls}"><div><span class="zpc-zone">${a.title}</span><span class="zpc-badge ${cls}">${badge}</span></div><div class="zpc-actions">${a.detail}</div></div>`;
  }).join('');

  const topCultures = [...CULTURES].sort((a, b) => b.score - a.score).slice(0, 5);
  document.getElementById('cultureGrid').innerHTML = topCultures.map((c) => `<div class="culture-card"><div class="culture-emoji">${c.emoji}</div><div class="culture-name">${c.name}</div><div class="culture-match-label">${c.score}% · ${c.category}</div></div>`).join('');

  document.getElementById('weatherLine').textContent = `Ben Guerir · ${APP_STATE.weather.temperature}°C · Vent ${APP_STATE.weather.wind} km/h · Pluie ${APP_STATE.weather.rain} mm`;
}

function renderTech() {
  const cards = [
    ['Humidité', APP_STATE.sensors.humidity, '%'],
    ['pH', APP_STATE.sensors.ph, ''],
    ['Conductivité', APP_STATE.sensors.ec, ' mS/cm'],
    ['Température', APP_STATE.sensors.temp, ' °C'],
  ];
  document.getElementById('techMetrics').innerHTML = cards.map(([name, val, unit]) => `<div class="data-card"><div class="data-name">${name}</div><div class="data-value">${val}<span class="data-unit">${unit}</span></div></div>`).join('');

  document.getElementById('techLogs').innerHTML = `
    <div style="font-size:12px;line-height:1.6">
      <div>• Stabilisation capteurs: 3s</div>
      <div>• Nombre de lectures: 10 / capteur</div>
      <div>• Qualité acquisition: dispersion faible (MAD &lt; 0.3)</div>
      <div>• Dernier point: ${APP_STATE.robot.activePoint}</div>
    </div>`;
}

async function boot() {
  await syncFromBackend();
  renderMission();
  renderGauges();
  renderReco();
  renderTech();
  drawMap();
  drawPhChart();
}

document.addEventListener('DOMContentLoaded', boot);
window.addEventListener('resize', () => {
  drawMap();
  drawPhChart();
});
