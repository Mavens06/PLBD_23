const LANG = {
  fr: {
    badge: 'FR', status: 'Robot actif', greetTitle: 'Bonjour !', greetSub: "Voici l'état de votre champ aujourd'hui",
    chatTitle: 'Posez votre question', chatWelcome: 'Bonjour ! Je suis votre assistant agricole.',
    chatPlaceholder: 'Écrire une question...', navFarmer: 'Terrain', navMap: 'Carte', navReco: 'Conseils', navTech: 'Technique',
    lblWater: 'Humidité', lblPh: 'pH', lblEc: 'Conductivité', lblTemp: 'Température',
    sug: ['💧 Quand arroser ?', '🌾 Quelle culture choisir ?', '📍 Zone critique ?', '🤖 Où est le robot ?'],
  },
  ar: {
    badge: 'ع', status: 'الروبوت نشيط', greetTitle: 'مرحباً !', greetSub: 'هذه حالة حقلك اليوم',
    chatTitle: 'اسأل سؤالك', chatWelcome: 'مرحباً! أنا مساعدك الزراعي.', chatPlaceholder: 'اكتب سؤالاً...',
    navFarmer: 'الميدان', navMap: 'الخريطة', navReco: 'النصائح', navTech: 'تقني',
    lblWater: 'الرطوبة', lblPh: 'الـpH', lblEc: 'الموصلية', lblTemp: 'الحرارة',
    sug: ['💧 متى أسقي؟', '🌾 أي محصول؟', '📍 أي منطقة حرجة؟', '🤖 أين الروبوت؟'],
  },
  da: {
    badge: 'DA', status: 'الروبو خدام', greetTitle: 'مرحبا!', greetSub: 'هاهي حالة الضيعة اليوم',
    chatTitle: 'سول سؤالك', chatWelcome: 'أنا المساعد الفلاحي ديالك.', chatPlaceholder: 'كتب سؤالك...',
    navFarmer: 'التيران', navMap: 'الخريطة', navReco: 'النصائح', navTech: 'تقني',
    lblWater: 'الرطوبة', lblPh: 'pH', lblEc: 'الكوندوكتيڤيتي', lblTemp: 'الحرارة',
    sug: ['💧 فوقاش نسقي؟', '🌾 أشمن زراعة؟', '📍 فين الزون الصعيبة؟', '🤖 فين الروبو؟'],
  },
};
const TOAST_DISPLAY_DURATION_MS = 2200;

let currentLang = 'fr';
let isListening = false;
let recognition = null;

function chooseLang(lang) {
  currentLang = lang;
  APP_STATE.language = lang;
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
  document.getElementById('nav-reco').textContent = L.navReco;
  document.getElementById('nav-tech').textContent = L.navTech;
  document.getElementById('lbl-water').textContent = L.lblWater;
  document.getElementById('lbl-ph').textContent = L.lblPh;
  document.getElementById('lbl-ec').textContent = L.lblEc;
  document.getElementById('lbl-temp').textContent = L.lblTemp;
  document.getElementById('sugQuestions').innerHTML = L.sug.map((s) => `<span class="sug-q" onclick="askSuggested(this)">${s}</span>`).join('');
  document.body.style.direction = lang === 'fr' ? 'ltr' : 'rtl';
}

async function callChatAPI(message) {
  const payload = {
    message,
    language: currentLang,
    sensor_data: {
      humidity: APP_STATE.sensors.humidity,
      ph: APP_STATE.sensors.ph,
      ec: APP_STATE.sensors.ec,
      temp: APP_STATE.sensors.temp,
    },
    robot_state: `${APP_STATE.robot.mission} - ${APP_STATE.robot.activePoint}`,
  };

  try {
    const res = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('chat failed');
    const data = await res.json();
    return data.response;
  } catch (_) {
    return {
      fr: 'Je ne peux pas joindre le serveur IA, mais vos mesures indiquent de surveiller humidité et conductivité.',
      ar: 'لا يمكنني الوصول إلى الخادم الآن، لكن القياسات تشير إلى متابعة الرطوبة والموصلية.',
      da: 'ماقدرتش نوصل للسيرفر دابا، ولكن خاص نراقبو الرطوبة والكوندوكتيڤيتي.',
    }[currentLang];
  }
}

function addMessage(text, who) {
  const div = document.createElement('div');
  div.className = `chat-bubble ${who}`;
  div.textContent = text;
  const msgs = document.getElementById('chatMessages');
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

async function sendChat() {
  const inp = document.getElementById('chatInput');
  const txt = inp.value.trim();
  if (!txt) return;
  addMessage(txt, 'user');
  inp.value = '';
  const wait = addMessage('⏳ ...', 'bot');
  const response = await callChatAPI(txt);
  wait.remove();
  addMessage(response, 'bot');
  speak(response);
}

async function askSuggested(el) {
  const txt = el.textContent;
  addMessage(txt, 'user');
  const wait = addMessage('⏳ ...', 'bot');
  const response = await callChatAPI(txt);
  wait.remove();
  addMessage(response, 'bot');
  speak(response);
}

function speak(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = currentLang === 'fr' ? 'fr-FR' : 'ar-MA';
  utt.rate = 0.92;
  window.speechSynthesis.speak(utt);
}

function toggleMic() {
  const btn = document.getElementById('micBtn');
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    showToast('Micro non supporté');
    return;
  }
  if (isListening) {
    recognition?.stop();
    isListening = false;
    btn.classList.remove('listening');
    btn.textContent = '🎙️';
    return;
  }

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = currentLang === 'fr' ? 'fr-FR' : 'ar-MA';
  recognition.onresult = (e) => {
    document.getElementById('chatInput').value = e.results[0][0].transcript;
    sendChat();
  };
  recognition.onend = () => {
    isListening = false;
    btn.classList.remove('listening');
    btn.textContent = '🎙️';
  };
  recognition.start();
  isListening = true;
  btn.classList.add('listening');
  btn.textContent = '⏹';
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), TOAST_DISPLAY_DURATION_MS);
}
