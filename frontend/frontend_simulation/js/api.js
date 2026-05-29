const API_BASE = (window.AGRIBOTICS_API_BASE || 'http://localhost:8000/api').replace(/\/$/, '');

async function fetchJSON(path, opts = {}) {
  const r = await fetch(API_BASE + path, opts);
  if (!r.ok) throw new Error(path + ' failed');
  return r.json();
}

async function syncFromBackend() {
  const [mission, measurements] = await Promise.allSettled([
    fetchJSON('/mission'),
    fetchJSON('/measurements'),
  ]);

  if (mission.status === 'fulfilled' && mission.value.robot) {
    const r = mission.value.robot;
    APP_STATE.robot.status = r.status || APP_STATE.robot.status;
    APP_STATE.robot.activePoint = r.active_point || r.activePoint || APP_STATE.robot.activePoint;
    APP_STATE.robot.progress = Number(r.progress_pct ?? r.progress ?? APP_STATE.robot.progress);
    APP_STATE.robot.measuredPoints = Number(mission.value.measured_points ?? APP_STATE.robot.measuredPoints);
    APP_STATE.robot.totalPoints = Number(mission.value.total_points ?? APP_STATE.robot.totalPoints);
  }

  if (measurements.status === 'fulfilled') {
    const payload = measurements.value;
    const all = payload.history || (payload.latest ? [payload.latest] : []);
    all.forEach((m, idx) => {
      const point = m.point || m.zone || (APP_STATE.missionRoute[idx] || APP_STATE.robot.activePoint);
      if (planLabels().includes(point)) {
        APP_STATE.fieldData[point] = {
          point,
          measured: true,
          humidity: Number(m.humidity ?? 0),
          ph: Number(m.ph ?? 0),
          temp: Number(m.temp ?? m.temperature ?? 0),
          ec: Number(m.ec ?? m.salinity ?? m.conductivity ?? 0),
          timestamp: m.timestamp || new Date().toISOString(),
          quality: m.quality || 'good',
        };
      }
    });
  }
}

async function postBackend(path, payload = {}) {
  return fetchJSON(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

// Météo (Open-Meteo en direct — API publique sans clé, CORS autorisé). Affine
// l'irrigation. Localisation par défaut : plaine du Saïss (Maroc). Repli silencieux.
window.fetchWeather = async function () {
  try {
    const lat = window.AGRIBOTICS_LAT || 33.9, lon = window.AGRIBOTICS_LON || -5.55;
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}`
      + `&daily=precipitation_sum,temperature_2m_max&forecast_days=3&timezone=auto`;
    const d = await (await fetch(url)).json();
    const rain = (d.daily && d.daily.precipitation_sum) || [];
    const rain3d = rain.reduce((s, v) => s + (v || 0), 0);
    APP_STATE.weather = {
      available: true,
      rain3d: Math.round(rain3d * 10) / 10,
      tmax: ((d.daily && d.daily.temperature_2m_max) || [])[0],
    };
  } catch (_) {
    APP_STATE.weather = { available: false };
  }
};
