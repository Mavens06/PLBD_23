const ZONES = ['A1','A2','A3','B1','B2','B3','C1','C2','C3'];
const ZONE_POS = {
  A1:{x:.17,y:.22}, A2:{x:.5,y:.22}, A3:{x:.83,y:.22},
  B1:{x:.17,y:.5},  B2:{x:.5,y:.5},  B3:{x:.83,y:.5},
  C1:{x:.17,y:.78}, C2:{x:.5,y:.78}, C3:{x:.83,y:.78},
};

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
function emptyField(){ const d = {}; ZONES.forEach(z => d[z] = null); return d; }
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
  const profile = SIMULATION_ZONE_PROFILES[point] || {humidity:58, ph:6.5, temp:22, ec:1.2};
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

function colorForVariable(z, variable){
  if (!z) return '#d9e3da';
  if (variable === 'humidity') return z.humidity < 45 ? '#2f80ed' : z.humidity > 82 ? '#e6a817' : '#4a9c55';
  if (variable === 'ph') return (z.ph < 5.8 || z.ph > 7.8) ? '#c0392b' : (z.ph < 6.2 || z.ph > 7.2) ? '#e6a817' : '#4a9c55';
  if (variable === 'temp') return (z.temp < 14 || z.temp > 32) ? '#e6a817' : '#4a9c55';
  if (variable === 'ec') {
    const ec = z.ec || 0;
    return ec > 2.5 ? '#c0392b' : ec > 1.5 ? '#e6a817' : '#4a9c55';
  }
  return '#4a9c55';
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
    const mm = Math.round(clamp(waterDeficit * 0.9, 3, 35));
    actions.push({type:'water', title:t('waterTitle'), value:`${mm} mm`, detail:`≈ ${mm} L/m²`});
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
