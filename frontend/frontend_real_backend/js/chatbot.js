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
        robot_state: APP_STATE?.robot || null
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

  window.speakBotAnswer = function (text) {
    if (!window.CHATBOT_SPEAK) return;
    if (!("speechSynthesis" in window)) {
      showToast((window.currentLang || "fr") === "fr" ? "Synthèse vocale non supportée" : "الصوت غير مدعوم في هذا المتصفح");
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
      speechSynthesis.speak(utter);
    } catch (_) {
      // Ne jamais bloquer l'interface si la voix échoue.
    }
  };

  window.stopBotVoice = function () {
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  };

  window.toggleVoiceReply = function () {
    window.CHATBOT_SPEAK = !window.CHATBOT_SPEAK;
    showToast(window.CHATBOT_SPEAK ? "Réponse vocale activée" : "Réponse vocale désactivée");
  };

  window.sendChat = async function () {
    const input = document.getElementById("chatInput");
    const message = (input && input.value || "").trim();
    if (!message) return;
    addMessage(message, "user");
    input.value = "";
    const answer = await askBackendOrLocal(message);
    addMessage(answer, "bot");
    window.speakBotAnswer(answer);
  };

  window.askSuggested = function (el) {
    const input = document.getElementById("chatInput");
    if (!input || !el) return;
    input.value = el.textContent.replace(/[💧🌾📍🤖]/g, "").trim();
    window.sendChat();
  };

  window.toggleMic = function () {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      showToast((window.currentLang || "fr") === "fr" ? "Micro non supporté" : "الميكروفون غير مدعوم");
      return;
    }
    const rec = new SR();
    rec.lang = (window.currentLang || "fr") === "fr" ? "fr-FR" : "ar-MA";
    rec.interimResults = false;
    rec.onresult = (e) => {
      const input = document.getElementById("chatInput");
      if (input) input.value = e.results[0][0].transcript;
      window.sendChat();
    };
    rec.onerror = () => {
      showToast((window.currentLang || "fr") === "fr" ? "Reconnaissance vocale interrompue" : "توقفت ميزة التعرف على الصوت");
    };
    rec.start();
  };

  if ("speechSynthesis" in window) {
    speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
  }
})();
