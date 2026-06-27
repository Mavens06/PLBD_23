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
  let _ttsGen = 0;   // n° de lecture courant : incrémenté à chaque stop → annule un pipeline en cours
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

  // Échappe le HTML avant toute mise en forme (anti-injection : le texte du LLM
  // n'introduit jamais de balise brute).
  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  // Rendu MARKDOWN LÉGER et SÛR des réponses du bot : gras `**…**`, titres `#`,
  // listes à puces (- • *) et numérotées (1.), paragraphes. On échappe le HTML
  // EN PREMIER, puis on n'injecte que des balises connues (strong/p/ul/ol/li).
  function renderRich(text) {
    let src = escapeHtml(text).replace(/\r\n/g, "\n");
    // Énumérations EN LIGNE (le LLM n'insère pas toujours un saut de ligne entre
    // les items) : « … : 1. ceci 2. cela 3) autre » → un item par ligne. Limité
    // à 1-2 chiffres suivis de .|) puis espace, pour NE PAS couper les décimales
    // (6.5), années (2024) ou heures. Idem pour les puces « • » en ligne.
    src = src.replace(/(\S)[ \t]+(\d{1,2}[.)][ \t]+)/g, "$1\n$2");
    src = src.replace(/(\S)[ \t]+(•[ \t]+)/g, "$1\n$2");
    const lines = src.split("\n");
    const inline = (s) => s
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_]+)__/g, "<strong>$1</strong>");
    let html = "";
    let list = null;                                  // 'ul' | 'ol' | null
    const closeList = () => { if (list) { html += `</${list}>`; list = null; } };
    for (const raw of lines) {
      const line = raw.trim();
      if (!line) { closeList(); continue; }
      const bullet = line.match(/^[-•*]\s+(.*)$/);
      const numbered = line.match(/^\d+[.)]\s+(.*)$/);
      const heading = line.match(/^#{1,4}\s+(.*)$/);
      if (bullet) {
        if (list !== "ul") { closeList(); html += "<ul>"; list = "ul"; }
        html += `<li>${inline(bullet[1])}</li>`;
      } else if (numbered) {
        if (list !== "ol") { closeList(); html += "<ol>"; list = "ol"; }
        html += `<li>${inline(numbered[1])}</li>`;
      } else if (heading) {
        closeList();
        html += `<p><strong>${inline(heading[1])}</strong></p>`;
      } else {
        closeList();
        html += `<p>${inline(line)}</p>`;
      }
    }
    closeList();
    return html || escapeHtml(text);
  }

  function addMessage(text, who) {
    const box = document.getElementById("chatMessages");
    if (!box) return;
    const b = document.createElement("div");
    b.className = `chat-bubble ${who || "bot"}`;
    // Bulles du bot : markdown léger mis en forme. Bulles utilisateur : texte
    // brut (rien à formater, et zéro surface d'injection).
    if ((who || "bot") === "bot") b.innerHTML = renderRich(text);
    else b.textContent = text;
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

  // Récupère l'audio WAV d'un texte via /api/tts (promesse de Blob).
  function _ttsFetchBlob(text) {
    const headers = { "Content-Type": "application/json" };
    if (window.AGRIBOTICS_API_KEY) headers["X-API-Key"] = window.AGRIBOTICS_API_KEY;
    return fetch(`${CHAT_API_BASE}/tts`, {
      method: "POST", headers,
      body: JSON.stringify({ text, language: window.currentLang || "ar" }),
    }).then((r) => { if (!r.ok) throw new Error("tts http " + r.status); return r.blob(); });
  }

  // Découpe la réponse en morceaux (phrases regroupées, ~90 car. min) pour
  // générer/jouer la voix AU FUR ET À MESURE : la lecture démarre dès la 1re
  // phrase au lieu d'attendre l'audio de toute la réponse → supprime le blanc
  // texte→voix sur les réponses longues (arabe/darija surtout).
  function _splitForTTS(text) {
    const parts = String(text || "")
      .split(/(?<=[.!?؟…\n])\s+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (parts.length <= 1) return [String(text || "")];
    const chunks = [];
    // 1er morceau = 1re phrase SEULE (la plus courte possible) → audio prêt le
    // plus vite → la voix démarre presque tout de suite après le texte.
    chunks.push(parts[0]);
    // Le reste est regroupé en morceaux ~120 car. (équilibre fluidité / nb d'appels).
    const MIN = 120;
    let cur = "";
    for (let k = 1; k < parts.length; k++) {
      cur = cur ? cur + " " + parts[k] : parts[k];
      if (cur.length >= MIN) { chunks.push(cur); cur = ""; }
    }
    if (cur) chunks.push(cur);
    return chunks;
  }

  // Lecture cloud EN PIPELINE : l'audio du morceau suivant est préchargé pendant
  // que le morceau courant se joue → voix quasi immédiate après le texte. Repli
  // sur la voix locale si le tout premier morceau échoue (réseau/quota).
  function speakViaCloudTTSChunked(text, done) {
    const chunks = _splitForTTS(text);
    window.stopBotVoice();                  // coupe toute lecture (et incrémente _ttsGen)
    const myGen = ++_ttsGen;                // identifie CE pipeline
    setVoiceState("thinking");
    let i = 0;
    let next = _ttsFetchBlob(chunks[0]);    // précharge le 1er morceau
    let firstPlayed = false;

    const playNext = () => {
      if (myGen !== _ttsGen) return;        // une autre lecture a pris la main → abandon
      if (i >= chunks.length) { setVoiceState("idle"); done(); return; }
      const pending = next;
      i += 1;
      next = (i < chunks.length) ? _ttsFetchBlob(chunks[i]) : null;  // précharge le suivant
      pending.then((blob) => {
        if (myGen !== _ttsGen) return;
        const url = URL.createObjectURL(blob);
        const audio = _ttsAudioEl();
        window._ttsAudio = audio;
        audio.onended = () => { URL.revokeObjectURL(url); playNext(); };
        audio.onerror = () => { URL.revokeObjectURL(url); playNext(); };
        audio.muted = false;
        audio.src = url;
        audio.playbackRate = 0.9;    // voix cloud ralentie (plus posée, mieux comprise)
        setVoiceState("speaking");
        const p = audio.play();
        if (p && p.then) {
          // firstPlayed est passé à true SEULEMENT si la lecture réussit (et non
          // avant) : sinon un blocage autoplay passait inaperçu (silence total).
          p.then(() => { firstPlayed = true; })
           .catch(() => {
             if (myGen !== _ttsGen) return;
             setVoiceState("idle");
             showToast((window.currentLang || "fr") === "fr"
               ? "🔊 Touchez l'écran puis renvoyez pour entendre la voix"
               : "🔊 المس الشاشة ثم أعد الإرسال لسماع الصوت");
             done();
           });
        } else {
          firstPlayed = true;
        }
      }).catch(() => {
        if (i === 1 && !firstPlayed) speakLocal(text, done);  // échec du 1er → repli local
        else playNext();                                      // sinon on saute ce morceau
      });
    };
    playNext();
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
      utter.rate = lang === "fr" ? 0.86 : 0.82;  // ralenti (lecture plus posée)
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
    // voix arabe (surtout Chrome). On privilégie donc la vraie voix cloud, EN
    // PIPELINE (1re phrase jouée dès qu'elle est prête), avec repli local interne.
    if (needsArabic) {
      speakViaCloudTTSChunked(text, done);
      return;
    }
    speakLocal(text, done);
  };

  window.stopBotVoice = function () {
    _ttsGen++;   // invalide tout pipeline TTS par morceaux en cours
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
        const isUser = m.role === "user";
        b.className = `chat-bubble ${isUser ? "user" : "bot"} archived`;
        if (isUser) b.textContent = m.content;
        else b.innerHTML = renderRich(m.content);
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
  // Dernière question posée par l'agriculteur (pour enchaîner logiquement).
  function _lastUserMessage() {
    const h = window.chatHistory || [];
    for (let i = h.length - 1; i >= 0; i--) {
      if (h[i] && h[i].role === "user") return h[i].content || "";
    }
    return "";
  }
  // Thème de la dernière question → permet des suivis qui s'enchaînent (eau,
  // sol/acidité-salinité, choix de culture, robot), sinon générique.
  function _followupTopic(msg) {
    const s = String(msg || "").toLowerCase();
    if (/eau|arro|irrig|sécher|sèch|pluie|ماء|سقي|ري|سقا|الما|مطر/.test(s)) return "water";
    if (/acid|\bph\b|salin|salé|\bsel\b|conductiv|\bec\b|corrig|amend|chaux|soufre|amélior|fertil|حمو|ملوح|ملح|تحسين|تصحيح|سماد|جير/.test(s)) return "soil";
    if (/cultur|semer|semis|planter|récolt|conv|adapt|زرع|محصول|غرس|نزرع|يناسب|مناسب/.test(s)) return "crop";
    if (/robot|mission|position|où est|فين|روبو|روبوت|الروبو/.test(s)) return "robot";
    return "default";
  }
  // Suggestions de SUIVI orientées « comprendre mon sol » et « comment faire »,
  // choisies selon le thème de la dernière question pour former une suite logique.
  function _followupSuggestions() {
    const lang = window.currentLang || "fr";
    const topic = _followupTopic(_lastUserMessage());
    const BANK = {
      water: {
        fr: ["À quelle fréquence arroser ?", "Comment savoir si j'arrose trop ?", "Et si la pluie est annoncée ?"],
        ar: ["كم مرة أسقي؟", "كيف أعرف أنني أُفرط في الري؟", "وإذا كان المطر متوقعاً؟"],
        da: ["شحال من مرة نسقي؟", "كيفاش نعرف بللي كنزيد فالما؟", "وإلا جا المطر؟"],
      },
      soil: {
        fr: ["Comment corriger mon sol concrètement ?", "Combien de temps avant de voir l'effet ?", "Quelle culture supporte ce sol ?"],
        ar: ["كيف أُصحّح تربتي عملياً؟", "كم من الوقت حتى تظهر النتيجة؟", "أي محصول يتحمّل هذه التربة؟"],
        da: ["كيفاش نصلح الأرض ديالي بالضبط؟", "شحال من وقت باش يبان الأثر؟", "أش من زرع يتحمّل هاد الأرض؟"],
      },
      crop: {
        fr: ["Pourquoi cette culture convient à mon sol ?", "Comment préparer le sol pour la semer ?", "Quelle autre culture est possible ?"],
        ar: ["لماذا يناسب هذا المحصول تربتي؟", "كيف أُهيّئ التربة لزراعته؟", "ما المحصول الآخر الممكن؟"],
        da: ["علاش هاد الزرع يناسب الأرض ديالي؟", "كيفاش نوجّد الأرض باش نزرعو؟", "أش من زرع آخر ممكن؟"],
      },
      robot: {
        fr: ["Quelles zones sont déjà mesurées ?", "Quelle zone a le meilleur sol ?", "Que faire après les mesures ?"],
        ar: ["ما المناطق التي تم قياسها؟", "أي منطقة تربتها الأفضل؟", "ماذا أفعل بعد القياسات؟"],
        da: ["شنو هي الزونات لي تقاسات؟", "أش من زون عندو أحسن أرض؟", "أش ندير من بعد القياسات؟"],
      },
      default: {
        fr: ["En quoi est-ce important pour ma récolte ?", "Par quoi commencer concrètement ?", "Quels résultats espérer, et en combien de temps ?"],
        ar: ["لماذا هذا مهمّ لمحصولي؟", "بماذا أبدأ عملياً؟", "ما النتائج المتوقَّعة وفي كم من الوقت؟"],
        da: ["علاش هادشي مهمّ للمحصول ديالي؟", "بأش نبدا بالضبط؟", "أش من نتيجة نتسنّى وفشحال من وقت؟"],
      },
    };
    return (BANK[topic] && (BANK[topic][lang] || BANK[topic].fr)) || BANK.default.fr;
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
  let _sttStop = null;        // arrêt anticipé d'un enregistrement cloud en cours

  // La reconnaissance vocale INTÉGRÉE au navigateur (Web Speech API) est faible
  // en arabe et quasi inexistante en darija. Quand le backend est joignable, on
  // privilégie une transcription CLOUD (route /api/stt → OpenAI Whisper /
  // gpt-4o-transcribe) bien plus fiable, avec repli automatique sur le navigateur.
  function _cloudSTTEnabled() {
    return (window.CHATBOT_USE_BACKEND === true || APP_STATE?.runtimeMode === "real")
      && !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  }

  // Enregistre le micro jusqu'à un court silence (ou une durée max), via une
  // détection d'énergie audio (AnalyserNode). Résout { blob, spoke }.
  function _recordUntilSilence(opts) {
    const { maxMs = 12000, silenceMs = 1400, startGraceMs = 4000 } = opts || {};
    return navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      const pick = ["audio/webm", "audio/ogg", "audio/mp4"].find(
        (m) => window.MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m));
      const type = pick || "audio/webm";
      const rec = new MediaRecorder(stream, pick ? { mimeType: pick } : undefined);
      const chunks = [];
      rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
      let ac, analyser, buf;
      try {
        ac = new (window.AudioContext || window.webkitAudioContext)();
        const node = ac.createMediaStreamSource(stream);
        analyser = ac.createAnalyser(); analyser.fftSize = 1024;
        node.connect(analyser);
        buf = new Uint8Array(analyser.fftSize);
      } catch (_) { /* pas d'analyse possible : on s'appuiera sur maxMs */ }

      return new Promise((resolve) => {
        let stopped = false, spoke = false, timer = null;
        const t0 = Date.now();
        let lastLoud = t0;
        const cleanup = () => {
          if (timer) { clearInterval(timer); clearTimeout(timer); }
          try { if (ac) ac.close(); } catch (_) {}
          stream.getTracks().forEach((tr) => tr.stop());
        };
        const finish = () => {
          if (stopped) return; stopped = true; _sttStop = null;
          try { rec.stop(); } catch (_) { cleanup(); resolve({ blob: new Blob(chunks, { type }), spoke }); }
        };
        rec.onstop = () => { cleanup(); resolve({ blob: new Blob(chunks, { type }), spoke }); };
        rec.onerror = () => finish();
        _sttStop = finish;                 // permet un arrêt manuel (re-clic micro)
        if (analyser) {
          timer = setInterval(() => {
            if (stopped) return;
            analyser.getByteTimeDomainData(buf);
            let peak = 0;
            for (let i = 0; i < buf.length; i++) { const d = Math.abs(buf[i] - 128); if (d > peak) peak = d; }
            const now = Date.now();
            if (peak > 9) { lastLoud = now; spoke = true; }
            if (now - t0 > maxMs) return finish();                     // durée max atteinte
            if (spoke && now - lastLoud > silenceMs) return finish();  // silence après parole
            if (!spoke && now - t0 > startGraceMs) return finish();    // rien dit → on abandonne
          }, 100);
        } else {
          timer = setTimeout(finish, maxMs);
        }
        rec.start();
      });
    });
  }

  // Envoie l'enregistrement à /api/stt et renvoie le texte transcrit.
  function _cloudTranscribe(blob) {
    const fd = new FormData();
    const ext = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "mp4" : "webm";
    fd.append("audio", blob, "speech." + ext);
    fd.append("language", window.currentLang || "fr");
    const headers = {};
    if (window.AGRIBOTICS_API_KEY) headers["X-API-Key"] = window.AGRIBOTICS_API_KEY;
    return fetch(`${CHAT_API_BASE}/stt`, { method: "POST", headers, body: fd })
      .then((r) => { if (!r.ok) throw new Error("stt http " + r.status); return r.json(); })
      .then((d) => (d.text || "").trim());
  }

  // Écoute via le cloud (Whisper). Repli sur la Web Speech API du navigateur si
  // le micro est refusé ou la transcription échoue.
  function _listenCloud() {
    if (recognizing) return;
    recognizing = true; gotResult = false;
    setVoiceState("listening");
    _recordUntilSilence().then((res) => {
      if (!res || !res.spoke) {
        recognizing = false;
        if (CONV_MODE) setTimeout(() => { if (CONV_MODE && !recognizing) startListening(); }, 300);
        else setVoiceState("idle");
        return;
      }
      setVoiceState("thinking");
      _cloudTranscribe(res.blob).then((txt) => {
        recognizing = false;
        if (txt) { gotResult = true; window.sendChat(txt); }     // → réponse + voix + ré-écoute
        else if (CONV_MODE) setTimeout(() => { if (CONV_MODE && !recognizing) startListening(); }, 300);
        else setVoiceState("idle");
      }).catch(() => {
        recognizing = false;
        showToast((window.currentLang || "fr") === "fr"
          ? "Transcription indisponible — micro local" : "تعذّر التفريغ — الميكروفون المحلي");
        _listenWebSpeech();                                       // repli navigateur
      });
    }).catch(() => {                                              // micro refusé / indisponible
      recognizing = false;
      _listenWebSpeech();
    });
  }

  // Aiguillage : cloud si dispo (bien meilleur en arabe/darija), sinon navigateur.
  function startListening() {
    if (recognizing) return;
    if (_cloudSTTEnabled()) { _listenCloud(); return; }
    _listenWebSpeech();
  }

  // Reconnaissance vocale INTÉGRÉE au navigateur (repli, ou si pas de backend).
  function _listenWebSpeech() {
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
    try { if (_sttStop) _sttStop(); } catch (_) {}
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
    // Un 2e appui PENDANT un enregistrement cloud le valide/stoppe immédiatement.
    if (_sttStop) { try { _sttStop(); } catch (_) {} return; }
    // Cloud (Whisper) si dispo : enregistre jusqu'au silence puis transcrit.
    if (_cloudSTTEnabled()) { _listenCloud(); return; }
    // Repli : reconnaissance vocale du navigateur (un seul tour).
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
