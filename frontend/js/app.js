// ======== PAGE NAV ========
function showPage(id, btn) {
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.bnav-item').forEach(b=>b.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(btn) btn.classList.add('active');
  if(id==='map') { setTimeout(drawMap,100); }
  if(id==='expert') { setTimeout(drawPhChart,100); renderExpertData(); }
  if(id==='farmer') { renderDashboard(); }
}

function levelFromRanges(type, value) {
  if (type === 'humidity') return value < 35 ? 0 : value < 50 ? 1 : 2;
  if (type === 'ph') return value < 5.8 || value > 7.8 ? 0 : (value < 6.0 || value > 7.2 ? 1 : 2);
  if (type === 'ec') return value > 2.8 ? 0 : value > 2.2 ? 1 : 2;
  if (type === 'temp') return value < 12 || value > 30 ? 0 : (value < 15 || value > 25 ? 1 : 2);
  return 1;
}

function gaugeText(type, level) {
  const copy = {
    humidity: ['Sol sec', 'Arrosage bientôt', 'Humidité correcte'],
    ph: ['Correction nécessaire', 'À surveiller', 'Très bien !'],
    ec: ['Salinité élevée', 'Surveiller les sels', 'Sels équilibrés'],
    temp: ['Température critique', 'Température moyenne', 'Parfait !']
  };
  return copy[type][level];
}

function setGauge(cardId, statusId, type, value) {
  const level = levelFromRanges(type, value);
  const card = document.getElementById(cardId);
  const status = document.getElementById(statusId);
  if (!card || !status) return;
  card.classList.remove('bad','warn','good');
  status.classList.remove('bad','warn','good');
  const cls = level === 0 ? 'bad' : level === 1 ? 'warn' : 'good';
  card.classList.add(cls);
  status.classList.add(cls);
  status.textContent = gaugeText(type, level);
  const faces = card.querySelectorAll('.gauge-face');
  faces.forEach((f, i) => f.classList.toggle('active', i === level));
}

function renderDashboard() {
  document.getElementById('missionStateBadge').textContent = MISSION_STATE.status;
  document.getElementById('missionPoint').textContent = MISSION_STATE.activePoint;
  document.getElementById('missionMode').textContent = MISSION_STATE.mode;
  document.getElementById('missionBattery').textContent = MISSION_STATE.battery + '%';
  document.getElementById('missionProbe').textContent = MISSION_STATE.sensorCount + ' capteurs';
  const pct = Math.round((MISSION_STATE.completedPoints / MISSION_STATE.totalPoints) * 100);
  document.getElementById('missionProgressTxt').textContent = `${MISSION_STATE.completedPoints} / ${MISSION_STATE.totalPoints} points relevés`;
  document.getElementById('missionEtaTxt').textContent = 'mise à jour en direct';
  document.getElementById('missionProgressBar').style.width = pct + '%';

  setGauge('card-water', 'stat-water', 'humidity', LATEST_MEASURE.humidity);
  setGauge('card-ph', 'stat-ph', 'ph', LATEST_MEASURE.ph);
  setGauge('card-ec', 'stat-ec', 'ec', LATEST_MEASURE.ec);
  setGauge('card-temp', 'stat-temp', 'temp', LATEST_MEASURE.temp);
}

function renderExpertData() {
  document.getElementById('expertHumidity').textContent = LATEST_MEASURE.humidity;
  document.getElementById('expertPh').textContent = LATEST_MEASURE.ph.toFixed(1);
  document.getElementById('expertEc').textContent = LATEST_MEASURE.ec.toFixed(1);
  document.getElementById('expertTemp').textContent = LATEST_MEASURE.temp;
  document.getElementById('barHumidity').style.width = Math.min(100, Math.round((LATEST_MEASURE.humidity / 70) * 100)) + '%';
  document.getElementById('barHumidity').style.background = LATEST_MEASURE.humidity < 50 ? 'var(--orange)' : 'var(--green-light)';
  document.getElementById('barPh').style.width = Math.min(100, Math.round((LATEST_MEASURE.ph / 8) * 100)) + '%';
  document.getElementById('barEc').style.width = Math.min(100, Math.round((LATEST_MEASURE.ec / 3) * 100)) + '%';
  document.getElementById('barEc').style.background = LATEST_MEASURE.ec > 2.2 ? 'var(--orange)' : 'var(--green-light)';
  document.getElementById('barTemp').style.width = Math.min(100, Math.round((LATEST_MEASURE.temp / 30) * 100)) + '%';

  document.getElementById('protoStab').textContent = MISSION_STATE.stabilizationSec + ' s';
  document.getElementById('protoReads').textContent = MISSION_STATE.sampleCount;
  document.getElementById('protoQuality').textContent = MISSION_STATE.quality;

  document.getElementById('robotBattery').textContent = MISSION_STATE.battery;
  document.getElementById('robotBatteryBar').style.width = MISSION_STATE.battery + '%';
  document.getElementById('robotMode').textContent = MISSION_STATE.mode;
  document.getElementById('robotDone').textContent = MISSION_STATE.completedPoints;
  document.getElementById('robotDoneBar').style.width = Math.round((MISSION_STATE.completedPoints/MISSION_STATE.totalPoints)*100) + '%';
  document.getElementById('robotActivePoint').textContent = MISSION_STATE.activePoint;
  document.getElementById('robotStateRange').textContent = MISSION_STATE.status;
}

// ======== RECO PAGE ========
function showRecoTab(id, btn) {
  document.querySelectorAll('.reco-subpage').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.reco-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('reco-' + id).classList.add('active');
  if (btn) btn.classList.add('active');
  if (id === 'practices') { renderSoilPractices(); }
  if (id === 'temporal') { setTimeout(drawTemporalCharts, 80); setTimeout(drawTemporalHeatmap, 80); }
  if (id === 'cultures')  { renderCultureGrid(currentCultureFilter || 'all'); }
}

function renderSoilPractices() {
  const container = document.getElementById('zonePracticeList');
  if (!container) return;
  const practices = [];
  for (let i = 0; i < ZONE_COUNT; i++) {
    const ph = mapData.ph[i], hum = mapData.humidity[i], ec = mapData.ec[i], temp = mapData.temp[i];
    const zone = String.fromCharCode(65 + Math.floor(i/6)) + (i%6 + 1);
    let priority = 'good', badge = '✓ Optimal', actions = [], reason = 'Paramètres optimaux';
    if (ph < 5.8) {
      priority = 'urgent'; badge = '⚠️ Urgent';
      actions.push('<span class="zpc-action lime">🪨 Corriger pH</span>');
      reason = 'pH acide ('+ph.toFixed(1)+')';
    } else if (ph > 7.8) {
      priority = 'warn'; badge = '⚡ Action';
      actions.push('<span class="zpc-action lime">🧪 Réduire alcalinité</span>');
      reason = 'pH élevé ('+ph.toFixed(1)+')';
    }
    if (hum < 35) {
      const p = priority === 'urgent' ? 'urgent' : 'warn';
      priority = p; badge = p === 'urgent' ? '⚠️ Urgent' : '⚡ Action';
      actions.push('<span class="zpc-action water">💧 Irrigation : 20–25 mm</span>');
      reason += (reason==='Paramètres optimaux'?'':'+ ') + 'sol sec ('+hum.toFixed(0)+'%)';
    }
    if (ec > 2.5) {
      priority = 'urgent'; badge = '⚠️ Urgent';
      actions.push('<span class="zpc-action water">🌊 Lessivage : 30–35 mm</span>');
      reason += (reason==='Paramètres optimaux'?'':'+ ') + 'salinité ('+ec.toFixed(1)+' mS/cm)';
    }
    if (temp > 28) {
      const p = priority === 'urgent' ? 'urgent' : 'warn';
      priority = p; badge = p === 'urgent' ? '⚠️ Urgent' : '⚡ Action';
      actions.push('<span class="zpc-action">🌤️ Mesurer tôt le matin</span>');
      reason += (reason==='Paramètres optimaux'?'':'+ ') + 'température élevée ('+temp.toFixed(0)+'°C)';
    }
    if (priority !== 'good') practices.push({ zone, priority, badge, actions, reason });
  }
  practices.sort((a,b) => (a.priority==='urgent'?-1:1));
  const html = practices.slice(0, 4).map(p => `
    <div class="zone-practice-card ${p.priority}">
      <div class="zpc-header"><span class="zpc-zone">Zone ${p.zone}</span><span class="zpc-badge ${p.priority}">${p.badge}</span></div>
      <div class="zpc-actions">${p.actions.join('')}</div>
      <div class="zpc-shap">Moteur local : ${p.reason}</div>
    </div>`).join('');
  container.innerHTML = html || '<div class="zone-practice-card good"><div class="zpc-header"><span class="zpc-zone">Toutes zones</span><span class="zpc-badge good">✓ Optimal</span></div><div class="zpc-actions"><span class="zpc-action">✅ OK</span></div><div class="zpc-shap">Moteur local : état du sol stable.</div></div>';
}

function renderCultureGrid(filter) {
  currentCultureFilter = filter;
  const grid = document.getElementById('cultureGrid');
  if (!grid) return;
  const filtered = filter === 'all' ? CULTURES : CULTURES.filter(c => c.cat === filter);
  const sorted = [...filtered].sort((a,b) => b.match - a.match);
  grid.innerHTML = sorted.map(c => {
    const cls = c.match >= 80 ? 'match-high' : c.match >= 65 ? 'match-med' : 'match-low';
    const fillColor = c.match >= 80 ? '#4CAF50' : c.match >= 65 ? '#FFC107' : '#E53935';
    return `<div class="culture-card ${cls}">
      <div class="culture-emoji">${c.emoji}</div>
      <div class="culture-name">${c.name}</div>
      <div class="culture-match-bar">
        <div class="culture-match-fill" style="width:${c.match}%;background:${fillColor}"></div>
      </div>
      <div class="culture-match-label">${c.match}% compatibilité</div>
      <button class="culture-detail-btn" onclick="showCultureDetail('${c.id}')">Voir détails ▾</button>
    </div>`;
  }).join('');
}

function filterCultures(filter, btn) {
  document.querySelectorAll('.culture-filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderCultureGrid(filter);
  document.getElementById('cultureDetailPanel').classList.remove('visible');
}

function showCultureDetail(id) {
  const c = CULTURES.find(x => x.id === id);
  if (!c) return;
  document.getElementById('cdpEmoji').textContent = c.emoji;
  document.getElementById('cdpName').textContent = c.name;
  document.getElementById('cdpDesc').textContent = c.desc;
  document.getElementById('cdpParams').innerHTML = [
    ['📅 Saison', c.season],
    ['💧 Eau', c.water],
    ['🧪 pH idéal', c.phRange],
    ['⚡ Salinité', c.ecRange],
  ].map(([l,v]) => `<div class="cdp-param"><div class="cdp-param-label">${l}</div><div class="cdp-param-val">${v}</div></div>`).join('');
  const panel = document.getElementById('cultureDetailPanel');
  panel.classList.add('visible');
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function selectSession(idx, el) {
  document.querySelectorAll('.session-chip').forEach(c => c.classList.remove('active'));
  if (el) el.classList.add('active');
  const insights = [
    'Session initiale. Sol légèrement acide en B2 et humidité faible au centre de la parcelle.',
    "Le pH se redresse et l'humidité progresse après irrigation localisée.",
    "La conductivité diminue, le pH reste stable, et l'humidité devient plus homogène."
  ];
  const deltas = [
    ['→ base', '→ base', '→ base'],
    ['▲ +0.3', '▲ +2', '▼ −0.2'],
    ['▲ +0.4', '▲ +3', '▼ −0.3']
  ];
  document.getElementById('temporalInsight').textContent = insights[idx] || insights[0];
  document.getElementById('delta-ph').textContent = deltas[idx][0];
  document.getElementById('delta-hum').textContent = deltas[idx][1];
  document.getElementById('delta-ec').textContent = deltas[idx][2];
  setTimeout(drawTemporalCharts, 50);
  setTimeout(drawTemporalHeatmap, 50);
}

function weatherCodeToEmoji(code) {
  if ([0,1].includes(code)) return '☀️';
  if ([2,3].includes(code)) return '⛅';
  if ([45,48].includes(code)) return '🌫️';
  if ([51,53,55,61,63,65,80,81,82].includes(code)) return '🌧️';
  if ([71,73,75].includes(code)) return '❄️';
  if ([95,96,99].includes(code)) return '⛈️';
  return '🌤️';
}

function forecastDayLabel(offset) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return offset === 0 ? 'Auj.' : d.toLocaleDateString('fr-FR', { weekday:'short' }).replace('.', '');
}

async function loadWeather() {
  const lat = 32.2359, lon = -7.9538;
  const fallback = WEATHER_FALLBACK;
  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&daily=weather_code,temperature_2m_max,precipitation_sum&forecast_days=5&timezone=auto`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('weather');
    const data = await res.json();
    const curr = data.current || {};
    const daily = data.daily || {};
    const icon = weatherCodeToEmoji(curr.weather_code ?? 0);
    document.getElementById('chipTemp').textContent = `${icon} ${Math.round(curr.temperature_2m ?? fallback.temperature)}°C`;
    document.getElementById('chipHumidity').textContent = `💧 ${Math.round(curr.relative_humidity_2m ?? fallback.humidity)}% HR`;
    document.getElementById('chipWind').textContent = `🌬️ ${Math.round(curr.wind_speed_10m ?? fallback.wind)} km/h`;
    const rain3d = ((daily.precipitation_sum || []).slice(0,3).reduce((a,b)=>a+(b||0),0));
    document.getElementById('chipRain').textContent = `🌧️ ${rain3d.toFixed(0)} mm/3j`;
    document.getElementById('weatherMainIcon').textContent = icon;
    document.getElementById('weatherMainTemp').textContent = `${Math.round(curr.temperature_2m ?? fallback.temperature)}°C`;
    document.getElementById('weatherMainDesc').textContent = `${icon} Conditions actuelles · ${fallback.location}`;
    document.getElementById('weatherMainDetail').textContent = `Vent ${Math.round(curr.wind_speed_10m ?? fallback.wind)} km/h · Humidité air ${Math.round(curr.relative_humidity_2m ?? fallback.humidity)}% · Pluie ${((daily.precipitation_sum||[])[0]||0).toFixed(0)} mm aujourd'hui`;
    const row = document.getElementById('forecastRow');
    row.innerHTML = (daily.temperature_2m_max || []).slice(0,5).map((t, i) => `
      <div class="forecast-chip">
        <div class="fc-day">${forecastDayLabel(i)}</div>
        <div class="fc-icon">${weatherCodeToEmoji((daily.weather_code||[])[i] || 0)}</div>
        <div class="fc-temp">${Math.round(t)}°</div>
        <div class="fc-rain">${(((daily.precipitation_sum||[])[i]) || 0).toFixed(0)} mm</div>
      </div>`).join('');
  } catch (e) {
    document.getElementById('chipTemp').textContent = `☀️ ${fallback.temperature}°C`;
    document.getElementById('chipHumidity').textContent = `💧 ${fallback.humidity}% HR`;
    document.getElementById('chipWind').textContent = `🌬️ ${fallback.wind} km/h`;
    document.getElementById('chipRain').textContent = `🌧️ ${fallback.rain3d} mm/3j`;
  }
}

// init
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const resM = await apiGet('/api/measurements');
        LATEST_MEASURE.humidity = resM.latest.humidity;
        LATEST_MEASURE.ph = resM.latest.ph;
        LATEST_MEASURE.ec = resM.latest.ec;
        LATEST_MEASURE.temp = resM.latest.temp;
        
        const resS = await apiGet('/api/mission');
        MISSION_STATE.status = resS.robot.status;
        MISSION_STATE.mode = resS.robot.mission;
        MISSION_STATE.activePoint = resS.robot.active_point;
        MISSION_STATE.completedPoints = resS.measured_points;
        MISSION_STATE.totalPoints = resS.total_points;
    } catch(e) {
        console.error("Backend fetch error, using fallback data", e);
    }

  renderDashboard();
  renderExpertData();
  renderCultureGrid('all');
  renderSoilPractices();
  drawPhChart();
  loadWeather();
  initChatbot();

  setInterval(async () => {
      try {
        const resM = await apiGet('/api/measurements');
        LATEST_MEASURE.humidity = resM.latest.humidity;
        LATEST_MEASURE.ph = resM.latest.ph;
        LATEST_MEASURE.ec = resM.latest.ec;
        LATEST_MEASURE.temp = resM.latest.temp;
        
        const resS = await apiGet('/api/mission');
        MISSION_STATE.status = resS.robot.status;
        MISSION_STATE.mode = resS.robot.mission;
        MISSION_STATE.activePoint = resS.robot.active_point;
        MISSION_STATE.completedPoints = resS.measured_points;
        MISSION_STATE.totalPoints = resS.total_points;
        
        renderDashboard();
        renderExpertData();
      } catch(e) {}
  }, 5000);
});

window.addEventListener('resize',()=>{ drawMap(); drawPhChart(); });
