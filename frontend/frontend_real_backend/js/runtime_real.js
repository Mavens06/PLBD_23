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

async function stopRealMode(){
  if(realPollTimer) clearInterval(realPollTimer);
  realPollTimer=null;
  // Bouton d'arrêt = ARRÊT D'URGENCE : le robot (mode --watch) stoppe entre deux
  // points (cf. /api/mission/stop → command=idle, robot_status=emergency_stop).
  try{ await postBackend('/mission/stop',{}); }catch(_){}
  APP_STATE.robot.status="Arrêt d'urgence";
  renderAll();
}
