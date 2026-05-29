/*
  Chatbot universel + retour vocal automatique.
  - Ne bloque jamais l'écran de choix de langue.
  - Fonctionne en local si le backend est absent.
  - Répond en français, arabe ou darija selon la langue choisie.
  - Lit automatiquement la réponse du bot à voix haute.
*/
(function () {
  window.CHATBOT_SPEAK = window.CHATBOT_SPEAK !== false;

  function safeAverage() {
    try {
      return averageField(APP_STATE.fieldData || {});
    } catch (_) {
      return { humidity: 0, ph: 0, temp: 0, ec: 0 };
    }
  }

  function selectedZone() {
    return (APP_STATE && APP_STATE.selectedZone) || "A1";
  }

  function selectedCrop() {
    return (APP_STATE && (APP_STATE.zoneCropPlan?.[APP_STATE.selectedZone] || APP_STATE.selectedCrop)) || "Tomate";
  }

  function zoneData(zone) {
    return (APP_STATE && APP_STATE.fieldData && APP_STATE.fieldData[zone]) || null;
  }

  function addMessage(text, who) {
    const box = document.getElementById("chatMessages");
    if (!box) return;
    const b = document.createElement("div");
    b.className = `chat-bubble ${who || "bot"}`;
    b.textContent = text;
    box.appendChild(b);
    box.scrollTop = box.scrollHeight;
  }

  function extractZone(q) {
    const match = String(q || "").match(/\b[A-Ca-c][1-3]\b/);
    return match ? match[0].toUpperCase() : selectedZone();
  }

  function isOffTopic(q) {
    const s = String(q || "").toLowerCase();
    const off = ["football", "match", "film", "musique", "crypto", "bitcoin", "pizza", "recette"];
    if (off.some(w => s.includes(w))) return true;
    // Une référence de zone (ex. B2, A1, C3) = toujours agricole
    if (/\b[a-c][1-3]\b/i.test(q)) return false;
    const domain = [
      // Français
      "zone", "champ", "culture", "eau", "arro", "ph", "sol", "robot", "carte", "mesure",
      "conseil", "action", "faire", "recommand", "irrigat", "salini", "conductiv", "humidi",
      "temperatur", "récolte", "semis", "engrais", "amendement", "lessiv", "parcelle",
      // Arabe
      "منطقة", "حقل", "زراعة", "ماء", "تربة", "روبوت", "خريطة", "نصيحة", "ملوحة",
      "إجراء", "توصية", "ري", "تسميد", "حموضة",
      // Darija
      "زون", "زرع", "تراب", "روبو", "شنو", "فين", "دير", "نعمل", "نسقي", "كوندوكتي",
    ];
    return !domain.some(w => s.includes(w));
  }

  function localAnswer(q) {
    const lang = window.currentLang || "fr";
    if (isOffTopic(q)) {
      if (lang === "ar") return "أجيب فقط عن أسئلة الحقل، المناطق، المحاصيل، الروبوت والتوصيات الزراعية.";
      if (lang === "da") return "كنجاوب غير على أسئلة الحقل، الزونات، الزرع، الروبو والنصائح الفلاحية.";
      return "Je réponds seulement aux questions liées au champ, aux zones, aux cultures, au robot et aux recommandations agricoles.";
    }

    const zone = extractZone(q);
    const crop = selectedCrop();
    const data = zoneData(zone);
    const actions = data ? recommendActionsForZone(data, crop) : [];

    const robot = APP_STATE?.robot || { activePoint: "HOME", measuredPoints: 0, totalPoints: 9 };
    if (/robot|mission|position|où|فين|روبوت|روبو/i.test(q)) {
      if (lang === "ar") return `الروبوت في النقطة ${robot.activePoint}. التقدم: ${robot.measuredPoints}/${robot.totalPoints}.`;
      if (lang === "da") return `الروبو دابا فـ ${robot.activePoint}. التقدم: ${robot.measuredPoints}/${robot.totalPoints}.`;
      return `Le robot est au point ${robot.activePoint}. Progression : ${robot.measuredPoints}/${robot.totalPoints}.`;
    }

    if (!data) {
      if (lang === "ar") return `المنطقة ${zone} لم تُقَس بعد. انتظر وصول الروبوت أو شغّل المحاكاة.`;
      if (lang === "da") return `زون ${zone} ما تقاساتش مزال. تسنى الروبو يوصل ولا بدا المحاكاة.`;
      return `La zone ${zone} n’est pas encore mesurée. Attendez le robot ou lancez la simulation.`;
    }

    const cropTxt = cropLabel(crop);
    const ecVal = data.ec != null ? data.ec : '—';

    // Formater toutes les actions (max 3) en une liste lisible
    const fmtActions = (sep, prefix) =>
      actions.map((a, i) => `${i + 1}. ${a.title} : ${a.value} (${a.detail})`).join(sep);

    if (lang === "ar") {
      const actTxt = actions.map((a, i) => `${i + 1}. ${a.title}: ${a.value} (${a.detail})`).join(' | ');
      return `المنطقة ${zone} — ${cropTxt}. الرطوبة ${data.humidity}%، pH ${data.ph}، الحرارة ${data.temp}°C، الموصلية ${ecVal} mS/cm. الإجراءات: ${actTxt}.`;
    }
    if (lang === "da") {
      const actTxt = actions.map((a, i) => `${i + 1}. ${a.title}: ${a.value} (${a.detail})`).join(' | ');
      return `زون ${zone} — ${cropTxt}. الرطوبة ${data.humidity}%، pH ${data.ph}، الحرارة ${data.temp}°C، الكوندوكتي ${ecVal} mS/cm. ما تدير: ${actTxt}.`;
    }
    return `Zone ${zone} — ${cropTxt}. Mesures : H ${data.humidity}%, pH ${data.ph}, T ${data.temp}°C, EC ${ecVal} mS/cm. Actions : ${fmtActions(' | ')}.`;
  }

  async function askBackendOrLocal(message) {
    const useBackend = window.CHATBOT_USE_BACKEND === true || APP_STATE?.runtimeMode === "real";
    if (!useBackend) return localAnswer(message);

    try {
      const zone = extractZone(message);
      const zd = zoneData(zone);
      const payload = {
        message,
        language: window.currentLang || "fr",
        selected_zone: zone,
        selected_crop: selectedCrop(),
        zone_data: zd,
        sensor_data: zd ? {
          pH: zd.ph, humidity: zd.humidity,
          temperature: zd.temp, salinity: zd.ec
        } : null,
        robot_state: APP_STATE?.robot || null,
        // Historique multi-tours (6 derniers) pour une conversation suivie.
        history: (window.chatHistory || []).slice(-6),
      };
      const base = (window.AGRIBOTICS_API_BASE || "http://localhost:8000/api").replace(/\/$/, "");
      const r = await fetch(`${base}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!r.ok) throw new Error("chat api failed");
      const data = await r.json();
      return data.response || localAnswer(message);
    } catch (err) {
      showToast(t("backendUnavailable"));
      return localAnswer(message);
    }
  }

  function browserSpeechLang() {
    const lang = window.currentLang || "fr";
    if (lang === "fr") return "fr-FR";
    return "ar-MA";
  }

  function pickVoice() {
    if (!("speechSynthesis" in window)) return null;
    const lang = window.currentLang || "fr";
    const voices = speechSynthesis.getVoices ? speechSynthesis.getVoices() : [];
    if (!voices.length) return null;

    if (lang === "fr") {
      return voices.find(v => v.lang?.toLowerCase().startsWith("fr")) || null;
    }

    return (
      voices.find(v => v.lang?.toLowerCase() === "ar-ma") ||
      voices.find(v => v.lang?.toLowerCase().startsWith("ar")) ||
      voices.find(v => v.lang?.toLowerCase().startsWith("fr")) ||
      null
    );
  }

  window.speakBotAnswer = function (text, onEnd) {
    const done = typeof onEnd === "function" ? onEnd : function () {};
    if (!window.CHATBOT_SPEAK) { done(); return; }
    if (!("speechSynthesis" in window)) {
      showToast((window.currentLang || "fr") === "fr" ? "Synthèse vocale non supportée" : "الصوت غير مدعوم في هذا المتصفح");
      done();
      return;
    }

    try {
      speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = browserSpeechLang();
      utter.rate = (window.currentLang || "fr") === "fr" ? 0.95 : 0.9;
      utter.pitch = 1;
      utter.volume = 1;
      const voice = pickVoice();
      if (voice) utter.voice = voice;
      utter.onend = () => done();
      utter.onerror = () => done();
      setVoiceState("speaking");
      speechSynthesis.speak(utter);
    } catch (_) {
      // Ne jamais bloquer l'interface si la voix échoue.
      done();
    }
  };

  window.stopBotVoice = function () {
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  };

  window.toggleVoiceReply = function () {
    window.CHATBOT_SPEAK = !window.CHATBOT_SPEAK;
    showToast(window.CHATBOT_SPEAK ? "Réponse vocale activée" : "Réponse vocale désactivée");
  };

  // -- Mémoire de conversation (envoyée au backend pour le suivi multi-tours) --
  window.chatHistory = window.chatHistory || [];

  // -- État vocal : pilote l'indicateur visuel de la carte chatbot ----------
  function setVoiceState(state) {
    const card = document.querySelector(".chatbot-card");
    if (card) card.dataset.voice = state;          // idle | listening | thinking | speaking
    const label = document.getElementById("conv-label");
    if (!label) return;
    const lang = window.currentLang || "fr";
    const TXT = {
      fr: { idle: CONV_MODE ? "Arrêter" : "Parler avec AgriBot", listening: "J'écoute…", thinking: "Je réfléchis…", speaking: "Je réponds…" },
      ar: { idle: CONV_MODE ? "إيقاف" : "تحدث مع AgriBot", listening: "أستمع…", thinking: "أفكر…", speaking: "أجيب…" },
      da: { idle: CONV_MODE ? "وقف" : "هضر مع AgriBot", listening: "كنسمع…", thinking: "كنفكر…", speaking: "كنجاوب…" },
    };
    label.textContent = (TXT[lang] || TXT.fr)[state] || (TXT[lang] || TXT.fr).idle;
  }
  window.setVoiceState = setVoiceState;

  window.sendChat = async function (forcedText) {
    const input = document.getElementById("chatInput");
    const message = (forcedText != null ? forcedText : (input && input.value) || "").trim();
    if (!message) return;
    addMessage(message, "user");
    window.chatHistory.push({ role: "user", content: message });
    if (input && forcedText == null) input.value = "";
    setVoiceState("thinking");

    const answer = await askBackendOrLocal(message);
    addMessage(answer, "bot");
    window.chatHistory.push({ role: "bot", content: answer });
    if (window.chatHistory.length > 12) window.chatHistory = window.chatHistory.slice(-12);

    // Lit la réponse, puis enchaîne l'écoute si on est en mode conversation.
    window.speakBotAnswer(answer, () => {
      if (CONV_MODE) startListening();
      else setVoiceState("idle");
    });
  };

  window.askSuggested = function (el) {
    if (!el) return;
    window.sendChat(el.textContent.replace(/[💧🌾📍🤖]/g, "").trim());
  };

  // ---- Conversation vocale mains-libres (écoute → réponse → écoute) --------
  // Conçue pour les agriculteurs non alphabétisés : tout se fait à la voix.
  let CONV_MODE = false;
  let recognizing = false;
  let gotResult = false;
  let recognizer = null;

  function startListening() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      showToast((window.currentLang || "fr") === "fr" ? "Micro non supporté" : "الميكروفون غير مدعوم");
      CONV_MODE = false; setVoiceState("idle"); return;
    }
    if (recognizing) return;
    recognizer = new SR();
    recognizer.lang = browserSpeechLang();
    recognizer.interimResults = false;
    recognizer.continuous = false;
    recognizing = true;
    gotResult = false;
    setVoiceState("listening");

    recognizer.onresult = (e) => {
      gotResult = true;
      recognizing = false;
      const txt = e.results[0][0].transcript;
      window.sendChat(txt);          // → réponse + voix + ré-écoute
    };
    recognizer.onerror = () => {
      recognizing = false;
      if (CONV_MODE) setTimeout(() => { if (CONV_MODE && !recognizing) startListening(); }, 700);
      else setVoiceState("idle");
    };
    recognizer.onend = () => {
      recognizing = false;
      // Fin sans parole captée (silence) : on relance l'écoute en mode conversation.
      if (CONV_MODE && !gotResult) setTimeout(() => { if (CONV_MODE && !recognizing) startListening(); }, 500);
    };
    try { recognizer.start(); } catch (_) { recognizing = false; }
  }

  function stopConversation() {
    CONV_MODE = false;
    recognizing = false;
    try { if (recognizer) recognizer.abort(); } catch (_) {}
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    setVoiceState("idle");
  }

  // Démarre/arrête la conversation vocale continue (bouton principal).
  window.toggleVoiceConversation = function () {
    if (CONV_MODE) {
      stopConversation();
      showToast((window.currentLang || "fr") === "fr" ? "Conversation vocale arrêtée" : "توقفت المحادثة الصوتية");
    } else {
      CONV_MODE = true;
      window.CHATBOT_SPEAK = true;
      showToast((window.currentLang || "fr") === "fr" ? "Conversation vocale activée — parlez" : "المحادثة الصوتية مفعّلة — تكلّم");
      startListening();
    }
  };

  // Bouton micro classique (un seul tour, sans boucle).
  window.toggleMic = function () {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      showToast((window.currentLang || "fr") === "fr" ? "Micro non supporté" : "الميكروفون غير مدعوم");
      return;
    }
    const rec = new SR();
    rec.lang = browserSpeechLang();
    rec.interimResults = false;
    rec.onresult = (e) => window.sendChat(e.results[0][0].transcript);
    rec.onerror = () => showToast((window.currentLang || "fr") === "fr" ? "Reconnaissance vocale interrompue" : "توقفت ميزة التعرف على الصوت");
    rec.start();
  };

  // Injecte le bouton de conversation vocale en haut de la carte chatbot
  // (évite d'éditer chaque variante HTML ; garantit la cohérence partout).
  function injectConversationButton() {
    const card = document.querySelector(".chatbot-card");
    if (!card || document.getElementById("convBtn")) return;
    const title = card.querySelector(".chatbot-title");
    const btn = document.createElement("button");
    btn.className = "conv-btn";
    btn.id = "convBtn";
    btn.setAttribute("onclick", "toggleVoiceConversation()");
    btn.innerHTML = `<span class="conv-ico">🎤</span><span id="conv-label">Parler avec AgriBot</span>`;
    if (title && title.nextSibling) card.insertBefore(btn, title.nextSibling);
    else card.insertBefore(btn, card.firstChild);
    setVoiceState("idle");
  }

  if ("speechSynthesis" in window) {
    speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
  }
  if (document.readyState !== "loading") injectConversationButton();
  else document.addEventListener("DOMContentLoaded", injectConversationButton);
})();
