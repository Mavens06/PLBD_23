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
    const mv = mission.value;
    // Adopter le plan du backend (défini via l'UI puis exécuté par le robot) :
    // la carte reflète exactement les points que le robot va mesurer.
    if (Array.isArray(mv.plan) && mv.plan.length) {
      const sameLabels =
        mv.plan.length === APP_STATE.plan.length &&
        mv.plan.every((p, i) => p.label === APP_STATE.plan[i].label
          && p.x === APP_STATE.plan[i].x && p.y === APP_STATE.plan[i].y);
      if (!sameLabels) applyPlanPoints(mv.plan);
    }
    const r = mv.robot;
    APP_STATE.robot.status = r.status || APP_STATE.robot.status;
    APP_STATE.robot.activePoint = r.active_point || r.activePoint || APP_STATE.robot.activePoint;
    APP_STATE.robot.progress = Number(r.progress_pct ?? r.progress ?? APP_STATE.robot.progress);
    APP_STATE.robot.measuredPoints = Number(mv.measured_points ?? APP_STATE.robot.measuredPoints);
    APP_STATE.robot.totalPoints = Number(mv.total_points ?? APP_STATE.robot.totalPoints);
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

// Météo (Open-Meteo via le backend) — affine l'irrigation. Repli silencieux.
window.fetchWeather = async function () {
  try {
    const w = await fetchJSON('/weather');
    APP_STATE.weather = (w && w.available)
      ? { available: true, rain3d: w.rain_3d_mm, tmax: w.tmax }
      : { available: false };
  } catch (_) {
    APP_STATE.weather = { available: false };
  }
};

// Diagnostic de correction faisant autorité, calculé par le backend
// (rules.correction). Normalisé pour renderDiagnostic(). Repli silencieux
// sur le rendu local si le backend est injoignable.
const _CORR_UNIT  = { ph:'', humidity:'%', temperature:'°C', ec:' mS/cm' };
const _CORR_LABEL = { ph:'ph', humidity:'humidity', temperature:'temperature', ec:'mapEc' };

window.fetchCorrection = async function (zone, crop) {
  const data = APP_STATE.fieldData[zone];
  if (!data) return null;
  try {
    const r = await fetchJSON(`/recommendation/${zone}/correction?crop=${encodeURIComponent(crop)}`);
    const items = (r.diagnostics || []).map((d) => ({
      label: t(_CORR_LABEL[d.variable] || d.variable),
      val: d.value,
      unit: _CORR_UNIT[d.variable] ?? '',
      range: d.range,
      status: d.status === 'ok' ? 'good' : d.status,   // ok | low | high
    }));
    const local = {
      crop: r.target_crop || crop,
      compatibility: Math.round(r.compatibility),
      items,
      betterSuited: (r.better_suited || []).map((b) => ({ name: b.crop, score: Math.round(b.score) })),
    };
    return { local, actions: recommendActionsForZone(data, crop) };
  } catch (_) {
    return null;
  }
};
