APP_STATE.runtimeMode='real';
let realPollTimer=null;

async function startRealMode(){
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
  renderAll();
  // Mission terminée (tous les points mesurés) : on stoppe le polling pour
  // éviter des requêtes inutiles toutes les 1,5 s une fois la mission finie.
  const done = APP_STATE.robot.totalPoints>0
    && APP_STATE.robot.measuredPoints>=APP_STATE.robot.totalPoints;
  if(done && realPollTimer){ clearInterval(realPollTimer); realPollTimer=null; }
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
