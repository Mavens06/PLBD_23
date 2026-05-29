APP_STATE.runtimeMode='real';
let realPollTimer=null;

async function startRealMode(){
  APP_STATE.robot.status='Connexion backend...';
  renderAll();
  try{ await postBackend('/mission/start',{route:APP_STATE.missionRoute}); }catch(_){}
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
}

async function stopRealMode(){
  if(realPollTimer) clearInterval(realPollTimer);
  realPollTimer=null;
  try{ await postBackend('/mission/end',{}); }catch(_){}
  APP_STATE.robot.status='Arrêt demandé';
  renderAll();
}
