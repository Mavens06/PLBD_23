// Plan de mission par défaut : grille 3×3, espacement 3 m. Coordonnées (x,y) en
// mètres. La source de vérité DYNAMIQUE est APP_STATE.plan (défini dans state.js) ;
// ce tableau sert d'amorçage et de repli. N points → N blocs sur la carte.
// ORDRE = serpentin (boustrophédon) validé sur le robot : on monte la colonne
// x=0 (Nord), on passe à x=3 et on la descend, puis on remonte x=6 — déplacement
// CONTINU sans saut diagonal. (Les labels/coords restent identiques ; seul
// l'ordre de visite change, ce qui définit le « sens d'évolution » du robot.)
const DEFAULT_PLAN = [
  {label:'A1',x:0,y:0}, {label:'B1',x:0,y:3}, {label:'C1',x:0,y:6},   // colonne x=0 ↑
  {label:'C2',x:3,y:6}, {label:'B2',x:3,y:3}, {label:'A2',x:3,y:0},   // colonne x=3 ↓
  {label:'A3',x:6,y:0}, {label:'B3',x:6,y:3}, {label:'C3',x:6,y:6},   // colonne x=6 ↑
];
const ZONES = DEFAULT_PLAN.map((p) => p.label);   // compat : labels du plan par défaut

// Plan courant (lu à l'exécution). Repli sur DEFAULT_PLAN tant qu'APP_STATE n'existe pas.
function currentPlan(){
  return (typeof APP_STATE !== 'undefined' && APP_STATE && APP_STATE.plan && APP_STATE.plan.length)
    ? APP_STATE.plan : DEFAULT_PLAN;
}
function planLabels(){ return currentPlan().map((p) => p.label); }
function planPoint(label){ return currentPlan().find((p) => p.label === label) || null; }

// (Le positionnement carte est désormais géré par _layoutField() dans map.js,
//  qui préserve les distances réelles avec une échelle uniforme x/y.)

// Champ de sol synthétique DÉTERMINISTE en fonction de (x,y) en mètres.
// MIROIR EXACT de soil_at() dans raspberry_pi/sensors/rs485_4in1.py — toute
// modification doit être répercutée des deux côtés (mock backend ↔ simulation).
function soilAt(x, y){
  const humidity = 58 + 22 * Math.sin(0.35 * x + 0.6) * Math.cos(0.28 * y - 0.4) + 3 * Math.sin(0.9 * y);
  const ph = 6.6 + 1.1 * Math.sin(0.25 * x - 0.5) + 0.5 * Math.cos(0.4 * y + 0.3);
  const temp = 22 + 8 * Math.cos(0.3 * x + 0.2) - 4 * Math.sin(0.22 * y);
  const ec = 1.4 + 1.0 * Math.sin(0.4 * x + 0.9) * Math.sin(0.3 * y) + 0.4 * Math.cos(0.5 * x);
  return {
    humidity: Math.round(clamp(humidity, 20, 95) * 100) / 100,
    ph: Math.round(clamp(ph, 4.6, 8.6) * 100) / 100,
    temp: Math.round(clamp(temp, 8, 38) * 100) / 100,
    ec: Math.round(clamp(ec, 0.1, 4.5) * 1000) / 1000,
  };
}

// Applique un nouveau plan et reconstruit l'état dépendant (mesures, route,
// crops par zone, sélection). Utilisé par l'éditeur de plan et la synchro backend.
function applyPlanPoints(points){
  APP_STATE.plan = points.map((p) => ({ label: String(p.label), x: Number(p.x), y: Number(p.y) }));
  APP_STATE.missionRoute = planLabels();
  APP_STATE.robot.totalPoints = APP_STATE.plan.length;
  APP_STATE.robot.measuredPoints = 0;
  APP_STATE.robot.progress = 0;
  APP_STATE.fieldData = emptyField();
  const zp = {};
  planLabels().forEach((z) => {
    zp[z] = APP_STATE.zoneCropPlan[z]
      || (typeof DEFAULT_ZONE_CROPS !== 'undefined' && DEFAULT_ZONE_CROPS[z])
      || APP_STATE.selectedCrop;
  });
  APP_STATE.zoneCropPlan = zp;
  if (!planLabels().includes(APP_STATE.selectedZone)) APP_STATE.selectedZone = planLabels()[0];
}

const CULTURES_OPTIMALES = {
  // ec : [min ok, max toléré] en mS/cm — au-delà du max : alerte salinité
  'Blé':              {emoji:'🌾', category:'céréale',       ph:[6.0,7.5], humidity:[50,75], temp:[15,25], ec:[0.2,2.5], compost:0.8},
  'Tomate':           {emoji:'🍅', category:'maraîchage',    ph:[6.0,6.8], humidity:[60,85], temp:[21,24], ec:[0.2,2.0], compost:1.2},
  'Oignon':           {emoji:'🧅', category:'maraîchage',    ph:[6.0,7.0], humidity:[70,85], temp:[15,25], ec:[0.2,1.5], compost:1.0},
  'Carotte':          {emoji:'🥕', category:'maraîchage',    ph:[5.0,6.5], humidity:[70,80], temp:[15,22], ec:[0.2,1.2], compost:0.8},
  'Pomme de terre':   {emoji:'🥔', category:'maraîchage',    ph:[5.0,6.5], humidity:[70,80], temp:[15,22], ec:[0.2,1.7], compost:1.1},
  'Orge':             {emoji:'🌾', category:'céréale',       ph:[6.0,8.0], humidity:[50,70], temp:[15,25], ec:[0.2,3.0], compost:0.7},
  'Betterave à sucre':{emoji:'🍠', category:'industrielle',  ph:[6.5,8.0], humidity:[60,80], temp:[15,25], ec:[0.2,3.5], compost:1.1},
  'Olivier':          {emoji:'🫒', category:'arboriculture', ph:[6.5,8.5], humidity:[40,65], temp:[15,30], ec:[0.2,3.0], compost:0.6},
  'Vigne':            {emoji:'🍇', category:'arboriculture', ph:[5.5,7.5], humidity:[50,70], temp:[18,30], ec:[0.2,2.5], compost:0.6},
  'Pastèque':         {emoji:'🍉', category:'maraîchage',    ph:[6.0,7.0], humidity:[70,85], temp:[22,35], ec:[0.2,2.0], compost:1.3},
};

function cropNames(){ return Object.keys(CULTURES_OPTIMALES); }
function getCrop(name){ return CULTURES_OPTIMALES[name] || CULTURES_OPTIMALES['Tomate']; }
function fmtRange(range, unit=''){ return `${range[0]}–${range[1]}${unit}`; }
function emptyField(){ const d = {}; planLabels().forEach(z => d[z] = null); return d; }
function clamp(v, a, b){ return Math.max(a, Math.min(b, v)); }
function randn(){ let u=0,v=0; while(u===0)u=Math.random(); while(v===0)v=Math.random(); return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v); }

function zoneBias(point){
  const r = point?.[0] || 'B';
  const c = Number(point?.[1] || 2);
  return {
    humidity: ({A:-12, B:-2, C:7}[r] || 0) + (c-2)*2,
    ph: ({A:-.35, B:0, C:.18}[r] || 0) + (c-2)*.06,
    temp: ({A:1.5, B:0, C:-1}[r] || 0),
    ec: ({A:0.4, B:0, C:-0.2}[r] || 0) + (c-2)*0.15,
  };
}

const SIMULATION_ZONE_PROFILES = {
  // ec en mS/cm : < 1.5 normal · 1.5–2.5 élevé · > 2.5 alerte salinité
  A1:{humidity:32.0, ph:5.40, temp:34.0, ec:2.8},   // bleu/rouge/jaune/orange
  A2:{humidity:52.0, ph:6.05, temp:22.0, ec:1.1},   // vert/jaune/vert/vert
  A3:{humidity:88.0, ph:7.90, temp:20.0, ec:0.5},   // jaune/rouge/vert/vert
  B1:{humidity:41.0, ph:6.80, temp:31.0, ec:1.8},   // bleu/vert/vert/jaune
  B2:{humidity:63.0, ph:5.65, temp:24.0, ec:0.9},   // vert/rouge/vert/vert
  B3:{humidity:75.0, ph:7.35, temp:13.0, ec:2.2},   // vert/jaune/jaune/orange
  C1:{humidity:90.0, ph:8.15, temp:36.0, ec:3.1},   // jaune/rouge/jaune/rouge
  C2:{humidity:70.0, ph:6.70, temp:10.0, ec:1.5},   // vert/vert/jaune/jaune
  C3:{humidity:56.0, ph:7.18, temp:26.0, ec:0.7},   // vert/vert-limite/vert/vert
};

function cropColor(name){
  const colors = {
    'Blé':'#d49a18',
    'Tomate':'#d94f45',
    'Oignon':'#9b59b6',
    'Carotte':'#f28c28',
    'Pomme de terre':'#8d6e63',
    'Orge':'#b7a82b',
    'Betterave à sucre':'#b83280',
    'Olivier':'#5f8f3a',
    'Vigne':'#6f42c1',
    'Pastèque':'#2e9f5b'
  };
  return colors[name] || '#4a9c55';
}

const DEFAULT_ZONE_CROPS = {
  A1:'Tomate', A2:'Blé', A3:'Oignon',
  B1:'Carotte', B2:'Pomme de terre', B3:'Orge',
  C1:'Betterave à sucre', C2:'Olivier', C3:'Pastèque'
};

function generateMeasurement(point){
  // Profil curé connu (démo A1..C3) prioritaire ; sinon champ déterministe
  // soilAt(x,y) à partir des coordonnées du point → marche pour tout point.
  let profile = SIMULATION_ZONE_PROFILES[point];
  if (!profile){
    const pt = planPoint(point);
    profile = pt ? soilAt(pt.x, pt.y) : {humidity:58, ph:6.5, temp:22, ec:1.2};
  }
  return {
    point,
    measured: true,
    humidity: Math.round(clamp(profile.humidity + randn()*1.4, 25, 92)*10)/10,
    ph:       Math.round(clamp(profile.ph       + randn()*0.05, 4.7, 8.4)*100)/100,
    temp:     Math.round(clamp(profile.temp     + randn()*0.4,  10, 38)*10)/10,
    ec:       Math.round(clamp(profile.ec       + randn()*0.08, 0.1, 5.0)*100)/100,
    timestamp: new Date().toISOString(),
    quality: 'good',
  };
}

function averageField(fd){
  const rows = Object.values(fd || {}).filter(Boolean);
  if (!rows.length) return {humidity:0, ph:0, temp:0, ec:0};
  return {
    humidity: Math.round(rows.reduce((s,r)=>s+r.humidity,0)/rows.length*10)/10,
    ph:       Math.round(rows.reduce((s,r)=>s+r.ph,0)      /rows.length*100)/100,
    temp:     Math.round(rows.reduce((s,r)=>s+r.temp,0)    /rows.length*10)/10,
    ec:       Math.round(rows.reduce((s,r)=>s+(r.ec||0),0) /rows.length*100)/100,
  };
}

function compatibilityScore(z, cropName){
  if (!z) return 0;
  const c = getCrop(cropName);
  let penalty = 0;
  if (z.humidity < c.humidity[0]) penalty += (c.humidity[0]-z.humidity)*1.8;
  if (z.humidity > c.humidity[1]) penalty += (z.humidity-c.humidity[1])*1.4;
  if (z.ph < c.ph[0]) penalty += (c.ph[0]-z.ph)*28;
  if (z.ph > c.ph[1]) penalty += (z.ph-c.ph[1])*28;
  if (z.temp < c.temp[0]) penalty += (c.temp[0]-z.temp)*3;
  if (z.temp > c.temp[1]) penalty += (z.temp-c.temp[1])*3;
  return Math.round(clamp(100-penalty, 0, 100));
}

// Encodage SÉMANTIQUE CONSTANT pour la carte : quelle que soit la variable,
// vert = bon · ambre = limite · rouge = à corriger · gris = non mesuré.
// (Auparavant le bleu signifiait "humidité faible" et le rouge "pH hors plage",
//  ce qui rendait la même couleur ambiguë d'une variable à l'autre.)
const MAP_STATUS_COLORS = { good:'#4a9c55', warn:'#e6a817', bad:'#c0392b', none:'#d9e3da' };

// Bandes de santé par variable : [bad<, warn<, GOOD entre, warn>, bad>]
// good si dans [g0,g1] ; warn dans les marges ; bad au-delà.
const VARIABLE_BANDS = {
  humidity: { good:[45,82], warn:[35,90] },
  ph:       { good:[6.2,7.2], warn:[5.8,7.8] },
  temp:     { good:[16,30], warn:[12,34] },
  ec:       { good:[0,1.5], warn:[0,2.5] },   // EC : plus c'est haut, pire (salinité)
};
const VARIABLE_KEY = { humidity:'humidity', ph:'ph', temp:'temp', ec:'ec' };

function variableStatus(z, variable){
  if (!z) return 'none';
  const val = z[VARIABLE_KEY[variable] || variable];
  if (val == null) return 'none';
  const b = VARIABLE_BANDS[variable];
  if (!b) return 'good';
  if (val >= b.good[0] && val <= b.good[1]) return 'good';
  if (val >= b.warn[0] && val <= b.warn[1]) return 'warn';
  return 'bad';
}

function colorForVariable(z, variable){
  return MAP_STATUS_COLORS[variableStatus(z, variable)];
}

// --- Météo (Open-Meteo) : affine l'irrigation selon la pluie prévue ---------
// APP_STATE.weather = { available, rain3d, tmax } (rempli par api.js).
function weatherInfo(){
  return (typeof APP_STATE !== 'undefined' && APP_STATE.weather && APP_STATE.weather.available)
    ? APP_STATE.weather : null;
}
// Facteur d'irrigation : 0 = reportée (pluie ≥ 10 mm/3j), 0.5 = réduite (4–10 mm), 1 = normale.
// Mêmes seuils que backend/weather_service.py.
function weatherIrrigationFactor(){
  const w = weatherInfo();
  if (!w) return 1;
  if (w.rain3d >= 10) return 0;
  if (w.rain3d >= 4) return 0.5;
  return 1;
}

// Cultures naturellement les mieux adaptées au sol mesuré (hors culture courante).
// Équivalent frontend du champ "better_suited" du backend (rules.correction).
function betterSuitedCrops(z, currentCrop, k = 3){
  if (!z) return [];
  return cropNames()
    .filter((n) => n !== currentCrop)
    .map((n) => ({ name:n, score: compatibilityScore(z, n) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, k);
}

// Diagnostic par variable pour la culture cible : statut + plage cible + valeur.
// Équivalent frontend de rules.correction.diagnose().
function diagnoseZoneForCrop(z, cropName){
  if (!z) return null;
  const c = getCrop(cropName);
  const defs = [
    { key:'ph',       label:t('ph'),          val:z.ph,       range:c.ph,       unit:'' },
    { key:'humidity', label:t('humidity'),    val:z.humidity, range:c.humidity, unit:'%' },
    { key:'temp',     label:t('temperature'), val:z.temp,     range:c.temp,     unit:'°C' },
    { key:'ec',       label:t('mapEc'),       val:z.ec ?? 0,  range:c.ec,       unit:' mS/cm' },
  ];
  const items = defs.map((d) => {
    let status = 'good';
    if (d.val < d.range[0]) status = 'low';
    else if (d.val > d.range[1]) status = 'high';
    return { ...d, status };
  });
  return {
    crop: cropName,
    compatibility: compatibilityScore(z, cropName),
    items,
    betterSuited: betterSuitedCrops(z, cropName),
  };
}

function evaluateZoneForCrop(z, cropName){
  if (!z) return {type:'pending', color:'#d9e3da', label:t('unmeasured'), detail:t('waiting')};
  const c = getCrop(cropName);
  const score = compatibilityScore(z, cropName);
  if (z.humidity < c.humidity[0]) return {type:'water', color:'#2f80ed', label:t('water'), detail:`${Math.round((c.humidity[0]-z.humidity)*0.9)} mm`, score};
  if (z.ph < c.ph[0] || z.ph > c.ph[1]) return {type:'amend', color:'#c0392b', label:t('ph'), detail:t('correction'), score};
  if (z.humidity > c.humidity[1] || z.temp < c.temp[0] || z.temp > c.temp[1]) return {type:'watch', color:'#e6a817', label:t('watch'), detail:`${score}%`, score};
  return {type:'good', color:'#4a9c55', label:t('good'), detail:`${score}%`, score};
}

function recommendActionsForZone(z, cropName){
  if (!z) return [{type:'watch', title:t('measure'), value:'—', detail:t('waiting')}];
  const c = getCrop(cropName);
  const actions = [];

  // Alerte salinité (EC) — priorité maximale
  if (c.ec && z.ec > c.ec[1]) {
    const mm = Math.round(clamp((z.ec - c.ec[1]) * 12, 5, 40));
    actions.push({type:'amend', title:t('ecTitle'), value:`${mm} mm`, detail:t('leachSalt')});
  }
  const waterDeficit = Math.max(0, c.humidity[0] - z.humidity);
  if (waterDeficit > 1) {
    let mm = Math.round(clamp(waterDeficit * 0.9, 3, 35));
    const wf = weatherIrrigationFactor();   // pluie prévue → on tempère l'arrosage
    if (wf === 0) {
      actions.push({type:'watch', title:t('waterTitle'), value:'0 mm', detail:t('irrigDeferred')});
    } else if (wf < 1) {
      mm = Math.max(1, Math.round(mm * wf));
      actions.push({type:'water', title:t('waterTitle'), value:`${mm} mm`, detail:t('irrigReduced')});
    } else {
      actions.push({type:'water', title:t('waterTitle'), value:`${mm} mm`, detail:`≈ ${mm} L/m²`});
    }
  } else if (z.humidity > c.humidity[1]) {
    actions.push({type:'watch', title:t('waterTitle'), value:'0 mm', detail:t('alreadyWet')});
  }

  if (z.ph < c.ph[0]) {
    const g = Math.round(clamp((c.ph[0] - z.ph) * 300, 60, 450));
    actions.push({type:'amend', title:t('limeTitle'), value:`${g} g/m²`, detail:t('raisePh')});
  } else if (z.ph > c.ph[1]) {
    const kg = Math.round(clamp((z.ph - c.ph[1]) * 1.6, 0.5, 3.0)*10)/10;
    actions.push({type:'amend', title:t('compostTitle'), value:`${kg} kg/m²`, detail:t('correctPh')});
  }

  const score = compatibilityScore(z, cropName);
  if (score >= 70) {
    actions.push({type:'good', title:t('fertilizationTitle'), value:`${c.compost} kg/m²`, detail:t('organicInput')});
  } else if (!actions.length) {
    actions.push({type:'watch', title:t('surveillanceTitle'), value:`${score}%`, detail:t('compatibility')});
  }

  if (z.temp < c.temp[0] || z.temp > c.temp[1]) {
    actions.push({type:'watch', title:t('tempTitle'), value:`${z.temp}°C`, detail:t('adaptDate')});
  }

  return actions.slice(0, 3);
}
