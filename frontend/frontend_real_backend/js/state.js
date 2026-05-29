const APP_STATE = {
  runtimeMode:'real',
  selectedCrop:'Tomate',
  selectedZone:'A1',
  zoneCropPlan:{},
  fieldData:emptyField(),
  missionRoute:ZONES.slice(),
  robot:{status:'En attente',activePoint:'HOME',progress:0,measuredPoints:0,totalPoints:ZONES.length},
  language: window.currentLang || localStorage.getItem('agribotics_lang') || 'fr'
};
ZONES.forEach(z => APP_STATE.zoneCropPlan[z] = (typeof DEFAULT_ZONE_CROPS !== 'undefined' && DEFAULT_ZONE_CROPS[z]) ? DEFAULT_ZONE_CROPS[z] : APP_STATE.selectedCrop);
