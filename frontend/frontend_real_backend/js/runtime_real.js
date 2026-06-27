APP_STATE.runtimeMode='real';
let realPollTimer=null;

async function startRealMode(){
  // Nouvelle mission = plateforme remise à zéro côté affichage : on efface les
  // anciennes mesures/zones (le backend les vide aussi via set_plan) et on vide
  // la conversation du chatbot, pour repartir d'un état propre.
  APP_STATE.fieldData = emptyField();
  APP_STATE.robot.measuredPoints = 0;
  APP_STATE.robot.progress = 0;
  APP_STATE.robot.activePoint = 'Départ';
  if (typeof clearChat === 'function') clearChat();
  _realPaused=false;
  if (typeof updatePauseBtn === 'function') updatePauseBtn();
  APP_STATE.robot.status='Connexion backend...';
  renderAll();
  try{
    // 1) Envoyer le plan défini dans l'UI ; 2) commander le démarrage.
    // Le robot (mode --watch) détecte la commande et exécute ce plan.
    await postBackend('/mission/plan',{points:APP_STATE.plan.map(p=>({label:p.label,x:p.x,y:p.y}))});
    await postBackend('/mission/start',{});
  }catch(e){ showToast(t('backendUnavailable')); }
  await pollBackendState();
  if(realPollTimer) clearInterval(realPollTimer);
  realPollTimer=setInterval(pollBackendState,1500);
}

async function pollBackendState(){
  try{
    await syncFromBackend();
    APP_STATE.robot.status=APP_STATE.robot.status||'Mission réelle';
    // Refléter l'état de pause du backend sur le bouton (robuste au rechargement).
    const wasPaused=_realPaused;
    _realPaused=(APP_STATE.robot.status==='paused');
    if(wasPaused!==_realPaused) updatePauseBtn();
  }catch(e){
    APP_STATE.robot.status='Backend indisponible';
    showToast(t('backendUnavailable'));
  }
  // Mission terminée (tous les points mesurés) : le robot réel revient à
  // l'origine (ROBOT_RETURN_HOME=1) AVANT d'émettre les signaux de fin. On
  // reflète ce retour sur la carte en faisant glisser le marqueur vers le
  // Départ, puis on stoppe le polling (plus de requêtes inutiles).
  const done = APP_STATE.robot.totalPoints>0
    && APP_STATE.robot.measuredPoints>=APP_STATE.robot.totalPoints;
  if(done){
    APP_STATE.robot.activePoint = (typeof START_POINT!=='undefined') ? START_POINT.label : 'Départ';
    if(realPollTimer){ clearInterval(realPollTimer); realPollTimer=null; }
  }
  renderAll();
}

// Pause MOMENTANÉE / reprise. Le robot s'immobilise sur place (pas de retour au
// départ) et conserve sa progression ; la reprise continue là où il s'était
// arrêté. Le bouton bascule son libellé Pause ↔ Reprendre. Le polling reste
// actif pendant la pause pour refléter le statut en direct.
let _realPaused=false;
async function togglePauseReal(){
  if(!_realPaused){
    try{ await postBackend('/mission/pause',{}); }catch(_){}
    _realPaused=true;
    APP_STATE.robot.status='paused';
  }else{
    try{ await postBackend('/mission/resume',{}); }catch(_){}
    _realPaused=false;
    APP_STATE.robot.status='moving';
  }
  updatePauseBtn();
  renderAll();
}

// Met à jour le libellé du bouton pause selon l'état (i18n, RTL inclus).
function updatePauseBtn(){
  const b=document.getElementById('btnPauseReal');
  if(b && typeof t==='function') b.textContent=t(_realPaused?'resumeBtn':'pauseBtn');
}

// ARRÊT = SUSPENSION : stoppe la mission ET remet l'interface + le robot à leur
// ÉTAT INITIAL (en attente, progression 0), comme si aucune mission n'avait
// démarré — mais le robot reste PHYSIQUEMENT où il est (pas de retour au point
// de départ). Le prochain « Démarrer » repart d'une plateforme propre.
async function stopRealMode(){
  if(realPollTimer){ clearInterval(realPollTimer); realPollTimer=null; }
  _realPaused=false;
  try{ await postBackend('/mission/suspend',{}); }catch(_){}
  // Remise à zéro de l'affichage (miroir du backend reset()).
  APP_STATE.fieldData = emptyField();
  APP_STATE.robot.measuredPoints = 0;
  APP_STATE.robot.progress = 0;
  APP_STATE.robot.activePoint = 'Départ';
  APP_STATE.robot.status = 'idle';
  updatePauseBtn();
  renderAll();
}

// SYNCHRONISER = REMISE À ZÉRO : remet le robot et l'interface à l'état du début
// (progression 0, mesures effacées, en attente), tout en CONSERVANT le plan —
// pour reprendre/relancer une mission proprement. N'enclenche PAS le robot.
async function syncResetReal(){
  if(realPollTimer){ clearInterval(realPollTimer); realPollTimer=null; }
  _realPaused=false;
  try{ await postBackend('/mission/reset',{}); }catch(_){}   // backend : vide l'état, garde le plan
  APP_STATE.fieldData = emptyField();
  APP_STATE.robot.measuredPoints = 0;
  APP_STATE.robot.progress = 0;
  APP_STATE.robot.activePoint = 'Départ';
  APP_STATE.robot.status = 'idle';
  updatePauseBtn();
  renderAll();
  if(typeof showToast==='function') showToast('🔄 Robot remis à zéro — prêt à reprendre');
}
