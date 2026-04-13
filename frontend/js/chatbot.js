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
    sug:['💧 Quand arroser ?','🌿 Quel engrais ?','📍 Quelle zone ?','🤖 Robot où ?'],
    responses:{
      water:"💧 Zone B2 a besoin d'eau maintenant ! Arrosez 15 litres par m², tôt le matin entre 6h et 8h pour éviter l'évaporation.",
      engrais:"🌿 La zone A1 manque d'azote. Ajoutez de l'urée (46%) : environ 30 kg par hectare, avant la prochaine pluie.",
      zone:"📍 Votre robot est en ce moment dans la zone A3. C'est une bonne zone, tout va bien là-bas !",
      robot:"🤖 Le robot travaille en zone A3. Il a fait 17 mesures sur 36. Batterie à 74%, tout va bien !",
      salinity:"⚡ La conductivité est un peu élevée en C3. Un lessivage (arrosage abondant) peut aider à réduire la salinité.",
      cultures:"🌾 Votre sol est très favorable à l'Olivier, au Palmier Dattier et à l'Orge. Consultez l'onglet 'Conseils' pour plus de détails.",
      default:"Je n'ai pas bien compris. Essayez : 'quand arroser ?', 'quel engrais ?' ou 'que cultiver ?'"
    }
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
    sug:['💧 متى أسقي؟','🌿 أي سماد؟','📍 أي منطقة؟','🤖 أين الروبوت؟'],
    responses:{
      water:"💧 المنطقة B2 تحتاج ماء الآن! اسقِ 15 لتر لكل متر مربع، في الصباح الباكر بين 6 و8 صباحاً.",
      engrais:"🌿 المنطقة A1 تفتقر إلى النيتروجين. أضف اليوريا (46٪): حوالي 30 كجم لكل هكتار قبل المطر القادم.",
      zone:"📍 روبوتك في المنطقة A3 الآن. هذه منطقة جيدة، كل شيء على ما يرام!",
      robot:"🤖 الروبوت يعمل في المنطقة A3. أجرى 17 قياساً من 36. البطارية 74٪، كل شيء بخير!",
      salinity:"⚡ الملوحة مرتفعة قليلاً في المنطقة C3. السقي الوفير يمكن أن يساعد في غسل الأملاح الزائدة.",
      cultures:"🌾 تربتك مناسبة جداً للزيتون، نخيل التمر والشعير. راجع علامة التبويب 'نصائح' للمزيد.",
      default:"لم أفهم جيداً. جرب: 'متى أسقي؟' أو 'أي سماد أضع؟'"
    }
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
    sug:['💧 فين نسقي؟','🌿 أش من سماد؟','📍 أش من زون؟','🤖 فين الروبو؟'],
    responses:{
      water:"💧 الزون B2 محتاجة ما دابا! سقيها 15 ليتر ف كل متر مربع، فالصباح بكري باش ما يطيرش الما.",
      engrais:"🌿 الزون A1 ناقصها النيتروجين. زيد اليوريا حوالي 30 كيلو فالهكتار قبل شتا الجاي.",
      zone:"📍 الروبو ديالك فالزون A3 دابا. هادي زون مزيانة، كل شي بخير!",
      robot:"🤖 الروبو خدام فالزون A3. البطاريا 74٪، كل شي مزيان!",
      salinity:"⚡ الملوحة طالعة شوية ف الزون C3. السقي المجهد يقدر يعاون باش تغسل الأملاح.",
      cultures:"🌾 الأرض ديالك مزيانة بزاف للزيتون، النخل والشعير. شوف الصفحة ديال 'النصايح' باش تعرف كتر.",
      default:"ما فهمتش مزيان. جرب تقول: 'فين نسقي؟' ولا 'أش من سماد نحط؟'"
    }
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


// ======== CHATBOT ========
function getResponse(msg) {
  const L = LANG[currentLang].responses;
  if(/(eau|arros|irrigu|sqi|s9i|sgi|ma|ماء|سقي|نسقي|نسقيو|الما)/i.test(msg)) return L.water;
  if(/(engrais|azote|npk|ur[eé]e|سماد|نيتروجين|دوا|لغبار|غبار)/i.test(msg)) return L.engrais;
  if(/(robot|rbo|روبو|روبوت|مكينة|الة)/i.test(msg)) return L.robot;
  if(/(zone|place|endroit|زون|منطقة|فين|بلاص|بلاصة)/i.test(msg)) return L.zone;
  if(/(sel|salin|ملح|ملوحة|salt)/i.test(msg)) return L.salinity;
  if(/(culti|plant|زرع|نزرع|crop)/i.test(msg)) return L.cultures;
  return L.default;
}

function addMessage(text, who) {
  const div = document.createElement('div');
  div.className = 'chat-bubble ' + who;
  div.textContent = text;
  const msgs = document.getElementById('chatMessages');
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function sendChat() {
  const inp = document.getElementById('chatInput');
  const txt = inp.value.trim();
  if(!txt) return;
  addMessage(txt, 'user');
  inp.value = '';
  setTimeout(()=>{ addMessage(getResponse(txt), 'bot'); speak(getResponse(txt)); }, 600);
}

function askSuggested(el) {
  const txt = el.textContent;
  addMessage(txt, 'user');
  setTimeout(()=>{ const r=getResponse(txt); addMessage(r,'bot'); speak(r); }, 600);
}

// ======== SPEECH SYNTHESIS ========
function speak(text) {
  if(!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = currentLang==='fr'?'fr-FR': currentLang==='ar'?'ar-MA':'ar-MA';
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

