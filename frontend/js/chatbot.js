// ======== LANGUAGES ========
const LANG = {
  fr: {
    badge:'FR', status:'Robot actif',
    greetTitle:'Bonjour !', greetSub:'Voici l\'état de votre champ aujourd\'hui',
    chatTitle:'Posez votre question',
    chatWelcome:'Bonjour ! Je suis votre assistant agricole. Posez-moi une question sur votre champ, ou appuyez sur le micro pour parler 🎙️',
    chatPlaceholder:'Écrire une question...',
    navFarmer:'Agriculteur', navMap:'Carte', navExpert:'Expert', navReco:'Conseils',
    lblWater:'Eau dans le sol', lblPh:'Qualité du sol', lblNpk:'Conductivité (Salinité)', lblTemp:'Température',
    statWaterWarn:'Arrosage bientôt', statPhGood:'Très bien !', statNpkBad:'Sels équilibrés', statTempGood:'Parfait !',
    sug:['💧 Quand arroser ?','🌿 Quel engrais ?','📍 Quelle zone ?','🤖 Robot où ?']
  },
  ar: {
    badge:'ع', status:'الروبوت نشيط',
    greetTitle:'مرحباً !', greetSub:'هذه حالة حقلك اليوم',
    chatTitle:'اسأل سؤالك',
    chatWelcome:'مرحباً! أنا مساعدك الزراعي. اسألني عن حقلك أو اضغط على الميكروفون للتحدث 🎙️',
    chatPlaceholder:'اكتب سؤالاً...',
    navFarmer:'المزارع', navMap:'الخريطة', navExpert:'خبير', navReco:'نصائح',
    lblWater:'الماء في التربة', lblPh:'جودة التربة', lblNpk:'الموصلية (الملوحة)', lblTemp:'الحرارة',
    statWaterWarn:'سقي قريباً', statPhGood:'ممتاز !', statNpkBad:'أملاح متوازنة', statTempGood:'مثالي !',
    sug:['💧 متى أسقي؟','🌿 أي سماد؟','📍 أي منطقة؟','🤖 أين الروبوت؟']
  },
  da: {
    badge:'DA', status:'الروبو خدام',
    greetTitle:'!صباح الخير', greetSub:'هاهو حال الضيعة ديالك اليوم',
    chatTitle:'سول على شي حاجة',
    chatWelcome:'!أهلاً بيك! أنا المساعد الزراعي ديالك. سولني على الضيعة ديالك ولا دوز على الميكرو باش تهضر 🎙️',
    chatPlaceholder:'كتب سوالك...',
    navFarmer:'الفلاح', navMap:'الخريطة', navExpert:'الخبير', navReco:'النصايح',
    lblWater:'الما فالتربة', lblPh:'جودة التربة', lblNpk:'الملوحة (الكوندوكتي)', lblTemp:'السخانة',
    statWaterWarn:'السقي قريب', statPhGood:'!مزيان بزاف', statNpkBad:'الأملاح مقادة', statTempGood:'!ميا ميا',
    sug:['💧 فين نسقي؟','🌿 أش من سماد؟','📍 أش من زون؟','🤖 فين الروبو؟']
  }
};

let currentLang = 'fr';
let isListening = false;
let recognition = null;

function chooseLang(lang) {
  currentLang = lang;
  const L = LANG[lang];
  document.getElementById('lang-screen').style.display = 'none';
  document.getElementById('langBadge').textContent = L.badge;
  document.getElementById('statusTxt').textContent = L.status;
  document.getElementById('greet-title').textContent = L.greetTitle;
  document.getElementById('greet-sub').textContent = L.greetSub;
  document.getElementById('chat-title').textContent = L.chatTitle;
  document.getElementById('chat-welcome').textContent = L.chatWelcome;
  document.getElementById('chatInput').placeholder = L.chatPlaceholder;
  document.getElementById('nav-farmer').textContent = L.navFarmer;
  document.getElementById('nav-map').textContent = L.navMap;
  document.getElementById('nav-expert').textContent = L.navExpert;
  if(document.getElementById('nav-reco')) document.getElementById('nav-reco').textContent = L.navReco;
  document.getElementById('lbl-water').textContent = L.lblWater;
  document.getElementById('lbl-ph').textContent = L.lblPh;
  document.getElementById('lbl-npk').textContent = L.lblNpk;
  document.getElementById('lbl-temp').textContent = L.lblTemp;
  document.getElementById('stat-water').textContent = L.statWaterWarn;
  document.getElementById('stat-ph').textContent = L.statPhGood;
  document.getElementById('stat-npk').textContent = L.statNpkBad;
  document.getElementById('stat-temp').textContent = L.statTempGood;
  const sugs = document.getElementById('sugQuestions');
  sugs.innerHTML = L.sug.map(s => `<span class="sug-q" onclick="askSuggested(this)">${s}</span>`).join('');
  if(lang==='ar'||lang==='da') document.body.style.direction='rtl';
  else document.body.style.direction='ltr';
}


// ======== CHATBOT API ========
const API_URL = 'http://localhost:8000/api/chat';

const DUMMY_SENSOR_DATA = {
  "pH": 6.5,
  "humidity": 40,
  "temperature": 25,
  "rainfall": 12,
  "salinity": 1.8,
  "soil_moisture": 42
};

async function callChatAPI(msg) {
  const payload = {
    message: msg,
    language: currentLang,
    sensor_data: DUMMY_SENSOR_DATA,
    ml_prediction: "Arganier"
  };
  try {
    const res = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Réponse serveur invalide');
    const data = await res.json();
    return data.response;
  } catch (e) {
    const errMsgs = {
      fr: '⚠️ Erreur de connexion au serveur IA. Veuillez réessayer.',
      ar: '⚠️ خطأ في الاتصال بخادم الذكاء الاصطناعي. حاول مرة أخرى.',
      da: '⚠️ كاين مشكل في الاتصال بالسيرفر ديال الذكاء الاصطناعي. عاود جرب.'
    };
    return errMsgs[currentLang] || errMsgs.fr;
  }
}

function addMessage(text, who) {
  const div = document.createElement('div');
  div.className = 'chat-bubble ' + who;
  div.textContent = text;
  const msgs = document.getElementById('chatMessages');
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function addLoadingMessage() {
  const loadingTexts = { fr: '⏳ ...', ar: '⏳ ...', da: '⏳ ...' };
  return addMessage(loadingTexts[currentLang] || '⏳ ...', 'bot');
}

async function sendChat() {
  const inp = document.getElementById('chatInput');
  const txt = inp.value.trim();
  if(!txt) return;
  addMessage(txt, 'user');
  inp.value = '';
  const loadingDiv = addLoadingMessage();
  const response = await callChatAPI(txt);
  loadingDiv.remove();
  addMessage(response, 'bot');
  speak(response);
}

async function askSuggested(el) {
  const txt = el.textContent;
  addMessage(txt, 'user');
  const loadingDiv = addLoadingMessage();
  const response = await callChatAPI(txt);
  loadingDiv.remove();
  addMessage(response, 'bot');
  speak(response);
}

// ======== SPEECH SYNTHESIS ========
function speak(text) {
  if(!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = currentLang==='fr'?'fr-FR': currentLang==='ar'?'ar-SA':'ar-MA';
  utt.rate = 0.9;
  window.speechSynthesis.speak(utt);
}

// ======== SPEECH RECOGNITION ========
function toggleMic() {
  const btn = document.getElementById('micBtn');
  if(!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    showToast('Micro non supporté sur ce navigateur'); return;
  }
  if(isListening) {
    recognition && recognition.stop();
    isListening = false;
    btn.classList.remove('listening');
    btn.textContent = '🎙️';
    return;
  }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = currentLang==='fr'?'fr-FR': currentLang==='ar'?'ar-SA':'ar-MA';
  recognition.interimResults = false;
  recognition.onresult = e => {
    const txt = e.results[0][0].transcript;
    document.getElementById('chatInput').value = txt;
    sendChat();
  };
  recognition.onend = ()=>{
    isListening=false;
    btn.classList.remove('listening');
    btn.textContent='🎙️';
  };
  recognition.start();
  isListening=true;
  btn.classList.add('listening');
  btn.textContent='⏹';
  showToast(currentLang==='fr'?'Parlez maintenant...':currentLang==='ar'?'تحدث الآن...':'هضر دابا...');
}

// ======== TOAST ========
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 2500);
}
