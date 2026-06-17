/*
  Chatbot universel + retour vocal automatique.
  - Ne bloque jamais l'écran de choix de langue.
  - Fonctionne en local si le backend est absent.
  - Répond en français, arabe ou darija selon la langue choisie.
  - Lit automatiquement la réponse du bot à voix haute.
*/
(function () {
  window.CHATBOT_SPEAK = window.CHATBOT_SPEAK !== false;

  // --- Déverrouillage audio (politique d'autoplay des navigateurs) ----------
  // audio.play() programmatique est BLOQUÉ tant que l'utilisateur n'a pas
  // interagi avec la page → c'est la cause n°1 du « je parle mais aucune voix ».
  // On réutilise UN seul élément <audio> qu'on « déverrouille » au 1er geste
  // (clic / touche / parole) en jouant un son muet ; les lectures TTS suivantes
  // passent alors sans blocage, même déclenchées de façon asynchrone.
  let _ttsEl = null;
  let _audioUnlocked = false;
  function _ttsAudioEl() {
    if (!_ttsEl) { _ttsEl = new Audio(); _ttsEl.preload = "auto"; }
    return _ttsEl;
  }
  function _unlockAudio() {
    if (_audioUnlocked) return;
    const el = _ttsAudioEl();
    try {
      el.muted = true;
      el.src = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";
      const p = el.play();
      if (p && p.then) {
        p.then(() => { el.pause(); el.currentTime = 0; el.muted = false; _audioUnlocked = true; })
         .catch(() => { el.muted = false; });
      } else { el.muted = false; _audioUnlocked = true; }
    } catch (_) { _audioUnlocked = true; }
  }
  if (typeof document !== "undefined") {
    ["click", "keydown", "touchstart"].forEach((ev) =>
      document.addEventListener(ev, _unlockAudio, { capture: true }));
  }

  // Base de l'API dérivée de l'hôte de la page (cf. api.js) : l'interface
  // ouverte depuis http://<ip-pi>:5500 parle au backend http://<ip-pi>:8000.
  // Sans ça, le chatbot visait localhost:8000 = la machine du navigateur, d'où
  // « backend non joignable » depuis un PC/tablette.
  // Même règle que api.js : dev (:5500/:5501) → hôte:8000 ; prod/tunnel HTTPS
  // (origine unique servie par le backend) → même origine + /api ; file:// → localhost.
  const _isHttpChat = location.protocol.startsWith("http");
  const _devSplitChat = _isHttpChat && (location.port === "5500" || location.port === "5501");
  const CHAT_API_BASE = (window.AGRIBOTICS_API_BASE
    || (!_isHttpChat ? "http://localhost:8000/api"
        : _devSplitChat ? `${location.protocol}//${location.hostname}:8000/api`
        : `${location.origin}/api`)
  ).replace(/\/$/, "");

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
      const base = CHAT_API_BASE;
      const chatHeaders = { "Content-Type": "application/json" };
      if (window.AGRIBOTICS_API_KEY) chatHeaders["X-API-Key"] = window.AGRIBOTICS_API_KEY;
      const r = await fetch(`${base}/chat`, {
        method: "POST",
        headers: chatHeaders,
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

    // Arabe / darija : on ne renvoie QU'une voix arabe. Surtout pas de repli sur
    // une voix latine (fr/en) : un moteur latin ne sait pas prononcer les lettres
    // arabes et ne lirait que les chiffres. Mieux vaut null → message explicite.
    return (
      voices.find(v => v.lang?.toLowerCase() === "ar-ma") ||
      voices.find(v => v.lang?.toLowerCase().startsWith("ar")) ||
      null
    );
  }

  // Lecture via Gemini TTS (cloud) : vraie voix naturelle (arabe notamment),
  // indépendante des voix locales du navigateur. Retourne une promesse rejetée
  // si l'appel échoue → le caller bascule alors sur la voix locale.
  function speakViaCloudTTS(text, done) {
    const base = CHAT_API_BASE;
    setVoiceState("thinking");                 // feedback visuel pendant le chargement audio
    const ttsHeaders = { "Content-Type": "application/json" };
    if (window.AGRIBOTICS_API_KEY) ttsHeaders["X-API-Key"] = window.AGRIBOTICS_API_KEY;
    return fetch(`${base}/tts`, {
      method: "POST",
      headers: ttsHeaders,
      body: JSON.stringify({ text, language: window.currentLang || "ar" }),
    }).then((r) => {
      if (!r.ok) throw new Error("tts http " + r.status);
      return r.blob();
    }).then((blob) => {
      window.stopBotVoice();                  // coupe toute lecture en cours
      const url = URL.createObjectURL(blob);
      const audio = _ttsAudioEl();            // élément persistant DÉVERROUILLÉ
      window._ttsAudio = audio;
      const cleanup = () => {
        URL.revokeObjectURL(url);
        if (window._ttsAudio === audio) window._ttsAudio = null;
        setVoiceState("idle");
        done();
      };
      audio.onended = cleanup;
      audio.onerror = cleanup;
      audio.muted = false;
      audio.src = url;
      setVoiceState("speaking");
      const p = audio.play();
      // Si la lecture est REFUSÉE (autoplay non déverrouillé), on prévient
      // l'utilisateur au lieu de rester muet — un geste (toucher) débloquera.
      return (p && p.catch) ? p.catch((err) => {
        setVoiceState("idle");
        showToast((window.currentLang || "fr") === "fr"
          ? "🔊 Touchez l'écran puis renvoyez pour entendre la voix"
          : "🔊 المس الشاشة ثم أعد الإرسال لسماع الصوت");
        done();
        throw err;
      }) : undefined;
    });
  }

  // Lecture via la synthèse vocale locale du navigateur (gratuite, hors-ligne).
  function speakLocal(text, done) {
    if (!("speechSynthesis" in window)) {
      showToast((window.currentLang || "fr") === "fr" ? "Synthèse vocale non supportée" : "الصوت غير مدعوم في هذا المتصفح");
      done();
      return;
    }
    try {
      const lang = window.currentLang || "fr";
      const needsArabic = lang === "ar" || lang === "da";
      const voice = pickVoice();

      // En arabe/darija sans voix arabe installée (typique de Chrome sous Linux),
      // on NE lit PAS avec une voix latine : elle ne prononcerait que les chiffres.
      if (needsArabic && !voice) {
        showToast("صوت عربي غير متوفّر في هذا المتصفّح — جرّب Firefox");
        setVoiceState("idle");
        done();
        return;
      }

      speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = browserSpeechLang();
      utter.rate = lang === "fr" ? 0.95 : 0.9;
      utter.pitch = 1;
      utter.volume = 1;
      if (voice) utter.voice = voice;
      utter.onend = () => done();
      utter.onerror = () => done();
      setVoiceState("speaking");
      speechSynthesis.speak(utter);
    } catch (_) {
      // Ne jamais bloquer l'interface si la voix échoue.
      done();
    }
  }

  window.speakBotAnswer = function (text, onEnd) {
    const done = typeof onEnd === "function" ? onEnd : function () {};
    if (!window.CHATBOT_SPEAK) { done(); return; }

    const lang = window.currentLang || "fr";
    const needsArabic = lang === "ar" || lang === "da";

    // Arabe / darija : la synthèse vocale LOCALE du navigateur n'a souvent PAS de
    // voix arabe (surtout Chrome). On privilégie donc TOUJOURS la vraie voix
    // Gemini (cloud) dès qu'un backend est joignable, et on retombe proprement
    // sur la voix locale si l'appel échoue (quota, réseau, backend absent).
    if (needsArabic) {
      speakViaCloudTTS(text, done).catch(() => speakLocal(text, done));
      return;
    }
    speakLocal(text, done);
  };

  window.stopBotVoice = function () {
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    if (window._ttsAudio) { try { window._ttsAudio.pause(); } catch (_) {} window._ttsAudio = null; }
  };

  // Met à jour l'icône + le libellé du bouton de coupure de voix selon l'état
  // (🔊 = voix activée · 🔇 = voix coupée). Multilingue.
  function _updateMuteBtn() {
    const b = document.getElementById("muteBtn");
    if (!b) return;
    const on = window.CHATBOT_SPEAK;
    const lang = window.currentLang || "fr";
    b.textContent = on ? "🔊" : "🔇";
    b.classList.toggle("muted", !on);
    b.setAttribute("aria-pressed", String(!on));
    const TT = on
      ? { fr: "Voix activée — couper", ar: "الصوت مفعّل — كتم", da: "الصوت خدام — سكّت" }
      : { fr: "Voix coupée — activer", ar: "الصوت مكتوم — تفعيل", da: "الصوت مسكوت — فعّل" };
    b.title = TT[lang] || TT.fr;
  }
  window._updateMuteBtn = _updateMuteBtn;

  // Repère le bouton de voix existant (🔇 dans la barre de saisie) et le
  // convertit en BASCULE muet/activé avec indicateur d'état.
  function _setupMuteButton() {
    let b = document.getElementById("muteBtn");
    if (!b) {
      // Le bouton HTML existant (onclick stopBotVoice, emoji 🔇) → on l'adopte.
      const candidates = Array.from(document.querySelectorAll(".chat-input-row .mic-btn"));
      b = candidates.find((el) => el.id !== "micBtn" && /🔇|🔊/.test(el.textContent));
      if (!b) return;
      b.id = "muteBtn";
    }
    b.onclick = window.toggleVoiceReply;
    _updateMuteBtn();
  }
  window._setupMuteButton = _setupMuteButton;

  window.toggleVoiceReply = function () {
    window.CHATBOT_SPEAK = !window.CHATBOT_SPEAK;
    // Couper = stopper aussi toute lecture en cours (sinon la phrase finit).
    if (!window.CHATBOT_SPEAK) window.stopBotVoice();
    _updateMuteBtn();
    const lang = window.currentLang || "fr";
    const ON = { fr: "Réponse vocale activée", ar: "تم تفعيل الرد الصوتي", da: "تفعّل الرد الصوتي" };
    const OFF = { fr: "Réponse vocale coupée", ar: "تم كتم الرد الصوتي", da: "تسكّت الرد الصوتي" };
    showToast((window.CHATBOT_SPEAK ? ON : OFF)[lang] || (window.CHATBOT_SPEAK ? ON.fr : OFF.fr));
  };

  // -- Mémoire de conversation (envoyée au backend pour le suivi multi-tours) --
  window.chatHistory = window.chatHistory || [];

  // -- Archive des conversations : au lieu de DÉTRUIRE le fil au vidage, on
  //    l'archive (localStorage, plafonné) pour que l'utilisateur puisse relire
  //    une ancienne réponse via le bouton 🕘 de l'en-tête du chat. -----------
  const _ARCHIVE_KEY = "agribotics_chat_archive";
  const _ARCHIVE_MAX = 15;
  function _loadArchive() {
    try { return JSON.parse(localStorage.getItem(_ARCHIVE_KEY) || "[]"); } catch (_) { return []; }
  }
  function _saveArchive(list) {
    try { localStorage.setItem(_ARCHIVE_KEY, JSON.stringify(list.slice(-_ARCHIVE_MAX))); } catch (_) {}
  }
  function _archiveCurrent() {
    const hist = window.chatHistory || [];
    if (!hist.length) return;                       // rien à archiver
    const list = _loadArchive();
    list.push({ ts: Date.now(), lang: window.currentLang || "fr", messages: hist.slice() });
    _saveArchive(list);
  }

  function _welcomeBubble(box) {
    const welcome = document.createElement("div");
    welcome.className = "chat-bubble bot";
    welcome.id = "chat-welcome";
    welcome.textContent = (typeof t === "function") ? t("chatWelcome")
      : "Bonjour ! Je peux expliquer les zones, les cultures et les actions à mener.";
    box.appendChild(welcome);
  }

  // Re-rend le fil COURANT (accueil + messages de window.chatHistory).
  function _renderCurrent() {
    _clearFollowups();
    const box = document.getElementById("chatMessages");
    if (!box) return;
    box.innerHTML = "";
    _welcomeBubble(box);
    (window.chatHistory || []).forEach((m) => addMessage(m.content, m.role === "user" ? "user" : "bot"));
    box.scrollTop = box.scrollHeight;
  }

  // Vide la conversation : ARCHIVE le fil courant (consultable), réinitialise
  // l'historique multi-tours et restaure le message d'accueil dans la langue
  // COURANTE. Appelé (1) au changement de langue — on ne mélange jamais deux
  // langues — et (2) au lancement d'une nouvelle mission. Coupe la voix en cours.
  window.clearChat = function () {
    try { window.stopBotVoice && window.stopBotVoice(); } catch (_) {}
    _archiveCurrent();                  // ← on garde une trace avant de vider
    window.chatHistory = [];
    _clearFollowups();
    const box = document.getElementById("chatMessages");
    if (!box) return;
    box.innerHTML = "";
    _welcomeBubble(box);
  };

  // Ouvre la vue HISTORIQUE (conversations archivées, lecture seule).
  window.openChatHistory = function () {
    const box = document.getElementById("chatMessages");
    if (!box) return;
    const fr = (window.currentLang || "fr") === "fr";
    const list = _loadArchive().slice().reverse();
    _clearFollowups();
    box.innerHTML = "";
    const head = document.createElement("div");
    head.className = "chat-hist-head";
    const ttl = document.createElement("span");
    ttl.textContent = fr ? "🕘 Conversations précédentes" : "🕘 المحادثات السابقة";
    const back = document.createElement("button");
    back.className = "chat-hist-back";
    back.textContent = fr ? "← Retour" : "← رجوع";
    back.onclick = _renderCurrent;
    head.appendChild(ttl); head.appendChild(back);
    box.appendChild(head);
    if (!list.length) {
      const e = document.createElement("div"); e.className = "chat-bubble bot";
      e.textContent = fr ? "Aucune conversation archivée." : "لا توجد محادثات محفوظة.";
      box.appendChild(e); return;
    }
    list.forEach((conv) => {
      const sep = document.createElement("div");
      sep.className = "chat-hist-sep";
      sep.textContent = `${new Date(conv.ts).toLocaleString()} · ${String(conv.lang).toUpperCase()}`;
      box.appendChild(sep);
      (conv.messages || []).forEach((m) => {
        const b = document.createElement("div");
        b.className = `chat-bubble ${m.role === "user" ? "user" : "bot"} archived`;
        b.textContent = m.content;
        box.appendChild(b);
      });
    });
    box.scrollTop = 0;
  };

  // -- Suggestions de SUIVI (texte faible) après chaque réponse : l'utilisateur
  //    valide (clic → envoie) ou ignore (✕ → s'effacent). Effacées à chaque
  //    nouveau message. Modèles selon la langue (aucun appel LLM → zéro latence).
  function _clearFollowups() {
    const old = document.getElementById("chatFollowups");
    if (old) old.remove();
  }
  function _followupSuggestions() {
    const S = {
      fr: ["Pourquoi ?", "Comment faire concrètement ?", "Et pour une autre zone ?"],
      ar: ["لماذا؟", "كيف أقوم بذلك عملياً؟", "وماذا عن منطقة أخرى؟"],
      da: ["علاش؟", "كيفاش ندير هادشي؟", "وزون أخرى؟"],
    };
    return S[window.currentLang || "fr"] || S.fr;
  }
  function _showFollowups() {
    _clearFollowups();
    const box = document.getElementById("chatMessages");
    if (!box) return;
    const wrap = document.createElement("div");
    wrap.id = "chatFollowups";
    wrap.className = "chat-followups";
    _followupSuggestions().forEach((q) => {
      const chip = document.createElement("button");
      chip.className = "chat-followup";
      chip.textContent = q;
      chip.onclick = () => { _clearFollowups(); window.sendChat(q); };
      wrap.appendChild(chip);
    });
    const dismiss = document.createElement("button");
    dismiss.className = "chat-followup dismiss";
    dismiss.textContent = "✕";
    dismiss.title = (window.currentLang || "fr") === "fr" ? "Masquer" : "إخفاء";
    dismiss.onclick = _clearFollowups;
    wrap.appendChild(dismiss);
    box.appendChild(wrap);
    box.scrollTop = box.scrollHeight;
  }

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
    _clearFollowups();                  // nouvelles questions → on retire les anciennes suggestions
    addMessage(message, "user");
    window.chatHistory.push({ role: "user", content: message });
    if (input && forcedText == null) input.value = "";
    setVoiceState("thinking");

    const answer = await askBackendOrLocal(message);
    addMessage(answer, "bot");
    window.chatHistory.push({ role: "bot", content: answer });
    if (window.chatHistory.length > 12) window.chatHistory = window.chatHistory.slice(-12);
    _showFollowups();                   // propose des questions de suivi (texte faible)

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
  function _initChatUI() { injectConversationButton(); _setupMuteButton(); }
  if (document.readyState !== "loading") _initChatUI();
  else document.addEventListener("DOMContentLoaded", _initChatUI);
})();
