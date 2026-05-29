const APP_STATE = {
  runtimeMode:'real',
  selectedCrop:'Tomate',
  plan: DEFAULT_PLAN.map(p => ({ ...p })),     // plan de mission dynamique (label, x, y)
  selectedZone: DEFAULT_PLAN[0].label,
  zoneCropPlan:{},
  fieldData:{},
  missionRoute: DEFAULT_PLAN.map(p => p.label),
  robot:{status:'En attente',activePoint:'HOME',progress:0,measuredPoints:0,totalPoints:DEFAULT_PLAN.length},
  language: window.currentLang || localStorage.getItem('agribotics_lang') || 'fr'
};
APP_STATE.fieldData = emptyField();
planLabels().forEach(z => APP_STATE.zoneCropPlan[z] = (typeof DEFAULT_ZONE_CROPS !== 'undefined' && DEFAULT_ZONE_CROPS[z]) ? DEFAULT_ZONE_CROPS[z] : APP_STATE.selectedCrop);
