// ======== LANGUAGES ========
const LANG = {
  fr: {
    badge: "FR", status: "Robot actif",
    greetTitle: "Bonjour !", greetSub: "Voici l'état de votre champ aujourd'hui",
    chatTitle: "Posez votre question",
    chatWelcome: "Bonjour ! Je suis votre assistant agricole. Posez-moi une question sur votre champ, ou appuyez sur le micro pour parler 🎙️",
    chatPlaceholder: "Écrire une question...",
    navFarmer: "Agriculteur", navMap: "Carte", navExpert: "Expert", navReco: "Conseils",
    lblWater: "Eau dans le sol", lblPh: "pH du sol", lblEc: "Conductivité (Salinité)", lblTemp: "Température",
    statWaterWarn: "Arrosage bientôt", statPhGood: "Très bien !", statEcGood: "Sels équilibrés", statTempGood: "Parfait !",
    sug: ["💧 Quand arroser ?", "🌾 Quelle culture ?", "📍 Quelle zone ?", "⚡ Salinité élevée ?"],
    missionTitle: "🤖 Mission terrain", point: "Point actif", mode: "Mode", battery: "Batterie", probe: "Sonde"
  },
  ar: {
    badge: "ع", status: "الروبوت نشيط",
    greetTitle: "مرحباً !", greetSub: "هذه حالة حقلك اليوم",
    chatTitle: "اسأل سؤالك",
    chatWelcome: "مرحباً! أنا مساعدك الزراعي. اسألني عن حقلك أو اضغط على الميكروفون للتحدث 🎙️",
    chatPlaceholder: "اكتب سؤالاً...",
    navFarmer: "المزارع", navMap: "الخريطة", navExpert: "خبير", navReco: "نصائح",
    lblWater: "الماء في التربة", lblPh: "حموضة التربة", lblEc: "الموصلية (الملوحة)", lblTemp: "الحرارة",
    statWaterWarn: "سقي قريباً", statPhGood: "ممتاز !", statEcGood: "الأملاح متوازنة", statTempGood: "مثالي !",
    sug: ["💧 متى أسقي؟", "🌾 أي محصول؟", "📍 أي منطقة؟", "⚡ هل الملوحة مرتفعة؟"],
    missionTitle: "🤖 مهمة الحقل", point: "النقطة", mode: "الوضع", battery: "البطارية", probe: "المسبار"
  },
  da: {
    badge: "DA", status: "الروبو خدام",
    greetTitle: "صباح الخير!", greetSub: "هاهو حال الضيعة ديالك اليوم",
    chatTitle: "سول على شي حاجة",
    chatWelcome: "أهلاً بيك! أنا المساعد الزراعي ديالك. سولني على الضيعة ديالك ولا دوز على الميكرو باش تهضر 🎙️",
    chatPlaceholder: "كتب سوالك...",
    navFarmer: "الفلاح", navMap: "الخريطة", navExpert: "الخبير", navReco: "النصايح",
    lblWater: "الما فالتربة", lblPh: "حموضة التربة", lblEc: "الكوندوكتي والملوحة", lblTemp: "السخانة",
    statWaterWarn: "السقي قريب", statPhGood: "مزيان بزاف!", statEcGood: "الأملاح مقادة", statTempGood: "ميا ميا!",
    sug: ["💧 فوقاش نسقي؟", "🌾 شنو نزرع؟", "📍 أش من زون؟", "⚡ واش الملوحة طالعة؟"],
    missionTitle: "🤖 مهمة فالحقل", point: "البوان", mode: "المود", battery: "البطارية", probe: "المجس"
  }
};

let currentLang = "fr";
let isListening = false;
let recognition = null;

function chooseLang(lang) {
  currentLang = lang;
  const L = LANG[lang];
  document.getElementById("lang-screen").style.display = "none";
  document.getElementById("langBadge").textContent = L.badge;
  document.getElementById("statusTxt").textContent = L.status;
  document.getElementById("greet-title").textContent = L.greetTitle;
  document.getElementById("greet-sub").textContent = L.greetSub;
  document.getElementById("chat-title").textContent = L.chatTitle;
  document.getElementById("chat-welcome").textContent = L.chatWelcome;
  document.getElementById("chatInput").placeholder = L.chatPlaceholder;
  document.getElementById("nav-farmer").textContent = L.navFarmer;
  document.getElementById("nav-map").textContent = L.navMap;
  document.getElementById("nav-expert").textContent = L.navExpert;
  document.getElementById("nav-reco").textContent = L.navReco;
  document.getElementById("lbl-water").textContent = L.lblWater;
  document.getElementById("lbl-ph").textContent = L.lblPh;
  document.getElementById("lbl-ec").textContent = L.lblEc;
  document.getElementById("lbl-temp").textContent = L.lblTemp;
  document.getElementById("stat-water").textContent = L.statWaterWarn;
  document.getElementById("stat-ph").textContent = L.statPhGood;
  document.getElementById("stat-ec").textContent = L.statEcGood;
  document.getElementById("stat-temp").textContent = L.statTempGood;
  document.getElementById("missionTitle").textContent = L.missionTitle;
  document.getElementById("missionLblPoint").textContent = L.point;
  document.getElementById("missionLblMode").textContent = L.mode;
  document.getElementById("missionLblBattery").textContent = L.battery;
  document.getElementById("missionLblDepth").textContent = L.probe;
  const sugs = document.getElementById("sugQuestions");
  sugs.innerHTML = L.sug.map(s => `<span class="sug-q" onclick="askSuggested(this)">${s}</span>`).join("");
  document.body.style.direction = (lang === "ar" || lang === "da") ? "rtl" : "ltr";
}

const API_URL = "http://localhost:8000/api/chat";

function buildChatPayload(message) {
  return {
    message,
    language: currentLang,
    sensor_data: {
      ph: LATEST_MEASURE.ph,
      humidite: LATEST_MEASURE.humidity,
      temperature: LATEST_MEASURE.temp,
      conductivite: LATEST_MEASURE.ec
    },
    robot_state: `Point actif: ${MISSION_STATE.activePoint}, Réalisés: ${MISSION_STATE.completedPoints}/${MISSION_STATE.totalPoints}`
  };
}

async function callChatAPI(msg) {
  const payload = buildChatPayload(msg);
  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Réponse serveur invalide");
    const data = await res.json();
    return data.response;
  } catch (e) {
    const fallback = {
      fr: `Mission en cours au point ${MISSION_STATE.activePoint}. Humidité ${LATEST_MEASURE.humidity}%, pH ${LATEST_MEASURE.ph}, conductivité ${LATEST_MEASURE.ec} mS/cm, température ${LATEST_MEASURE.temp}°C. Les cultures les plus prometteuses sont l'olivier, l'orge et le pois chiche.`,
      ar: `المهمة جارية عند النقطة ${MISSION_STATE.activePoint}. الرطوبة ${LATEST_MEASURE.humidity}%، الحموضة ${LATEST_MEASURE.ph}، الموصلية ${LATEST_MEASURE.ec}، والحرارة ${LATEST_MEASURE.temp}°C. أكثر الزراعات المناسبة: الزيتون والشعير والحمص.`,
      da: `المهمة خدامة فالبوان ${MISSION_STATE.activePoint}. الرطوبة ${LATEST_MEASURE.humidity}%، الحموضة ${LATEST_MEASURE.ph}، الكوندوكتي ${LATEST_MEASURE.ec}، والسخانة ${LATEST_MEASURE.temp}°C. أحسن الزراعات: الزيتون والشعير والحمص.`
    };
    return fallback[currentLang] || fallback.fr;
  }
}

function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = "chat-bubble " + who;
  div.textContent = text;
  const msgs = document.getElementById("chatMessages");
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function addLoadingMessage() {
  return addMessage("⏳ ...", "bot");
}

async function sendChat() {
  const inp = document.getElementById("chatInput");
  const txt = inp.value.trim();
  if (!txt) return;
  addMessage(txt, "user");
  inp.value = "";
  const loadingDiv = addLoadingMessage();
  const response = await callChatAPI(txt);
  loadingDiv.remove();
  addMessage(response, "bot");
  speak(response);
}

async function askSuggested(el) {
  const txt = el.textContent;
  addMessage(txt, "user");
  const loadingDiv = addLoadingMessage();
  const response = await callChatAPI(txt);
  loadingDiv.remove();
  addMessage(response, "bot");
  speak(response);
}

function speak(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = currentLang === "fr" ? "fr-FR" : currentLang === "ar" ? "ar-SA" : "ar-MA";
  utt.rate = 0.9;
  window.speechSynthesis.speak(utt);
}

function toggleMic() {
  const btn = document.getElementById("micBtn");
  if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
    showToast("Micro non supporté sur ce navigateur");
    return;
  }
  if (isListening) {
    recognition && recognition.stop();
    isListening = false;
    btn.classList.remove("listening");
    btn.textContent = "🎙️";
    return;
  }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = currentLang === "fr" ? "fr-FR" : currentLang === "ar" ? "ar-SA" : "ar-MA";
  recognition.interimResults = false;
  recognition.onresult = e => {
    const txt = e.results[0][0].transcript;
    document.getElementById("chatInput").value = txt;
    sendChat();
  };
  recognition.onend = () => {
    isListening = false;
    btn.classList.remove("listening");
    btn.textContent = "🎙️";
  };
  recognition.start();
  isListening = true;
  btn.classList.add("listening");
  btn.textContent = "⏹";
  showToast(currentLang === "fr" ? "Parlez maintenant..." : currentLang === "ar" ? "تحدث الآن..." : "هضر دابا...");
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2500);
}
