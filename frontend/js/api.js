const API_BASE = 'http://localhost:8000/api';

async function fetchJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} failed`);
  return res.json();
}

async function syncFromBackend() {
  try {
    const [mission, measurements, weather, recommendations] = await Promise.all([
      fetchJSON('/mission'),
      fetchJSON('/measurements'),
      fetchJSON('/weather'),
      fetchJSON('/recommendations'),
    ]);

    APP_STATE.robot.status = mission.robot.status;
    APP_STATE.robot.mission = mission.robot.mission;
    APP_STATE.robot.activePoint = mission.robot.active_point;
    APP_STATE.robot.progress = mission.robot.progress_pct;

    APP_STATE.sensors.humidity = measurements.latest.humidity;
    APP_STATE.sensors.ph = measurements.latest.ph;
    APP_STATE.sensors.ec = measurements.latest.ec;
    APP_STATE.sensors.temp = measurements.latest.temp;

    APP_STATE.weather.temperature = weather.temperature_c;
    APP_STATE.weather.humidity = weather.humidity_pct;
    APP_STATE.weather.wind = weather.wind_kmh;
    APP_STATE.weather.rain = weather.rain_mm_next_24h;

    window.RECO_ACTIONS = recommendations.actions || [];
  } catch (_) {
    window.RECO_ACTIONS = window.RECO_ACTIONS || [];
  }
}
