/* ===========================================================================
   Agri — assistant de navigation « AgriBot », avatar FERMIER (sérieux, posé).
   ---------------------------------------------------------------------------
   • UN SEUL personnage, fusionné au chatbot : l'avatar EST le lanceur du chat
     (un clic ouvre la conversation) ET le guide. Les conseils sont aussi repris
     dans le fil du chat → une seule entité qui guide et discute.
   • Présent dès l'écran de langue, suit l'utilisateur partout, LIT l'interface
     (mission, plan, mesures) via _coachStepName() et propose la prochaine action.
   • Phrases GÉNÉRÉES PAR LE LLM (route /api/coach, GPT/Gemini) : douces, courtes,
     polies. Affichage LOCAL instantané (jamais d'attente), remplacé par la phrase
     LLM dès qu'elle arrive. Repli local complet si hors-ligne (simulation).
   • Avatar SÉRIEUX : pas de bouche qui s'ouvre ; quand il parle, un halo discret
     pulse autour de l'avatar. Clignement d'yeux léger.
   • NON bloquant : bulle compacte dans le coin, AUTO-MASQUÉE (~9 s), masquée
     quand le chat est ouvert → ne recouvre jamais le texte des pages.
   • Réutilise _GUIDE_TXT / _coachStepName / _guidePulse / _guideGoto /
     _missionSummary / _confetti / _guideAdd (app.js) + speakBotAnswer /
     toggleChatPanel / CHATBOT_SPEAK (chatbot.js) + API_BASE (api.js).
   =========================================================================== */
(function () {
  if (window.Assistant) return;

  var INTRO = {
    fr: "👋 Bonjour, je suis AgriBot, votre assistant. Sélectionnez votre langue pour commencer.",
    ar: "👋 مرحباً، أنا كريم مساعدكم. اختاروا لغتكم للبدء.",
    da: "👋 السلام، أنا كريم لمساعد ديالكم. ختاروا اللغة ديالكم باش نبداو.",
  };
  // Écran de langue : message AFFICHÉ dans les 3 langues (le choix n'est pas
  // encore fait → chacun doit comprendre l'invitation à choisir sa langue).
  var INTRO_ALL = "👋 Choisissez votre langue\nاختر لغتك\nختار اللغة ديالك";
  // Phrase PARLÉE sur l'écran de langue (voix). NB : les navigateurs bloquent
  // souvent l'audio avant la 1ʳᵉ interaction → reparlé au clic sur l'avatar.
  var LANG_SPEAK = "Bonjour, je suis AgriBot. Choisissez votre langue pour commencer.";
  // Invitation à choisir la langue, DITE DANS LES 3 LANGUES et RAPIDEMENT.
  var LANG_PROMPT = [
    { lang: 'fr-FR', text: 'Choisissez votre langue' },
    { lang: 'ar',    text: '\u0627\u062e\u062a\u0627\u0631\u0648\u0627 \u0644\u063a\u062a\u0643\u0645' },
    { lang: 'ar-MA', text: '\u062e\u062a\u0627\u0631\u0648\u0627 \u0627\u0644\u0644\u063a\u0629 \u062f\u064a\u0627\u0644\u0643\u0645' },
  ];
  // Dit UN segment (la langue actuellement pointée), synchronisé avec le pointeur.
  function speakOneLang(idx) {
    try {
      if (window.CHATBOT_SPEAK === false) return;
      var seg = LANG_PROMPT[idx];
      if (!seg || !('speechSynthesis' in window)) return;
      if (window.stopBotVoice) window.stopBotVoice();
      window.speechSynthesis.cancel();
      setSpeaking(true);
      clearTimeout(st.hideTimer);
      var voices = window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : [];
      var p = seg.lang.slice(0, 2).toLowerCase();
      var v = voices.filter(function (vo) { return vo.lang && vo.lang.toLowerCase().indexOf(p) === 0; })[0];
      var u = new SpeechSynthesisUtterance(seg.text);
      u.lang = seg.lang; u.rate = 1.12;
      if (v) u.voice = v;
      u.onend = function () { setSpeaking(false); };
      u.onerror = function () { setSpeaking(false); };
      window.speechSynthesis.speak(u);
    } catch (e) { setSpeaking(false); }
  }
  // Indice de découvrabilité : rappelle qu'on peut DISCUTER avec AgriBot (chatbot).
  var CHAT_HINT = {
    fr: "💬 Cliquez sur moi pour échanger à tout moment",
    ar: "💬 انقروا عليّ للتحدث في أي وقت",
    da: "💬 كليكيو عليّا باش تهضرو فأي وقت",
  };
  // RELANCES (repli local si GPT indispo) : réexplication plus claire d'une étape
  // quand l'utilisateur reste inactif. Ton complice, poli, sans « s'il vous plaît ».
  var NUDGE_TXT = {
    fr: {
      lang: "Pour commencer, choisissez une langue en haut : Français, العربية ou الدارجة.",
      plan: "Choisissez vos points de mesure : cochez les emplacements souhaités sur la grille, puis validez avec « Appliquer le plan ».",
      start: "Votre plan est prêt. Appuyez sur « Démarrer mission », en bas, pour lancer le robot.",
      done: "Mission terminée. Ouvrez l'onglet « Conseils » pour voir, zone par zone, la culture adaptée et les corrections du sol.",
    },
    ar: {
      lang: "للبدء، اختاروا لغة في الأعلى: Français أو العربية أو الدارجة.",
      plan: "اختاروا نقاط القياس: أشّروا على الأماكن المطلوبة في الشبكة، ثم صادقوا عبر « تطبيق الخطة ».",
      start: "خطتكم جاهزة. اضغطوا على « بدء المهمة » في الأسفل لتشغيل الروبوت.",
      done: "انتهت المهمة. افتحوا تبويب « النصائح » للاطلاع، منطقة بمنطقة، على المحصول المناسب وتصحيحات التربة.",
    },
    da: {
      lang: "باش تبداو، ختاروا لغة فوق: Français ولا العربية ولا الدارجة.",
      plan: "ختاروا نقط القياس: شيكيو على البلايص لي بغيتو فالشبكة، من بعد صادقوا بـ « تطبيق الخطة ».",
      start: "الخطة ديالكم واجدة. كليكيو على « بدء المهمة » فالأسفل باش تشغّلوا الروبو.",
      done: "المهمة سالات. حلّوا تبويب « النصائح » باش تشوفوا، بلاصة ببلاصة، المحصول المناسب وتصحيحات التربة.",
    },
  };
  var MOOD = { plan: 'action', start: 'action', running: 'action', done: 'happy', progress: 'happy' };

  var el = {};
  var st = { built: false, introShown: false, spoke: false, lastStep: null, lastMeasured: -1,
             talkTimer: null, hideTimer: null, tipToken: 0, curText: '' };
  var coachCache = {};
  // Relances sur inactivité : EXACTEMENT 3 par étape (40 s, +60 s, +90 s), puis
  // PLUS RIEN jusqu'à un vrai changement d'étape. Une simple interaction
  // RÉAMORCE le minuteur mais NE remet PAS le compteur à zéro (sinon le plafond
  // de 3 ne tiendrait jamais). `step` = étape pour laquelle on compte les relances.
  var IDLE = { delays: [40000, 60000, 90000], max: 3, count: 0, timer: null, step: null };

  function lang() { return (window.currentLang || 'fr'); }
  function clean(t) {
    return String(t || '').replace(/[①②③④🤖🗺️💡🎉👋📊✅⚡🌱⭐🎊⚠️«»▶✓]/g, '').replace(/\s+/g, ' ').trim();
  }
  function onLang() {
    var s = document.getElementById('lang-screen');
    return !!(s && getComputedStyle(s).display !== 'none');
  }
  function chatOpen() {
    var p = document.getElementById('chatPanel');
    return !!(p && p.classList.contains('open'));
  }

  /* ---- styles ------------------------------------------------------------ */
  function injectStyles() {
    if (document.getElementById('agriAssistantStyles')) return;
    var s = document.createElement('style');
    s.id = 'agriAssistantStyles';
    s.textContent = [
      ".agri-assistant{position:fixed;right:18px;bottom:84px;z-index:9999;display:flex;flex-direction:column;align-items:flex-end;gap:9px;font-family:inherit;--ac:#3b7a44;pointer-events:none}",
      ".agri-assistant[data-mood=action]{--ac:#d98a2b}.agri-assistant[data-mood=alert]{--ac:#c0392b}.agri-assistant[data-mood=happy]{--ac:#2f9e57}",
      ".agri-bubble{position:relative;max-width:min(290px,78vw);background:linear-gradient(180deg,#ffffff,#f7fbf6);border:1px solid #e3ece4;border-right:4px solid var(--ac);border-radius:17px;padding:13px 16px 14px;box-shadow:0 14px 34px rgba(20,50,25,.22);font-size:13.5px;line-height:1.55;color:#22372a;font-weight:500;transform:translateY(8px) scale(.96);opacity:0;pointer-events:none;transition:transform .22s,opacity .22s}",
      ".agri-assistant.show .agri-bubble{transform:none;opacity:1;pointer-events:auto}",
      ".agri-bubble:after{content:'';position:absolute;right:22px;bottom:-8px;width:0;height:0;border:9px solid transparent;border-top-color:#f7fbf6;border-bottom:0}",
      ".agri-bubble-x{position:absolute;top:4px;right:8px;border:none;background:transparent;color:#aab5ae;cursor:pointer;font-size:15px;line-height:1;padding:2px}",
      ".agri-name{display:flex;align-items:center;gap:5px;font-size:10px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:var(--ac);margin-bottom:6px;opacity:.95}",
      ".agri-name .dot{width:6px;height:6px;border-radius:50%;background:var(--ac);box-shadow:0 0 0 3px rgba(59,122,68,.14)}",
      ".agri-text{color:#22372a;white-space:pre-line}",
      ".agri-btn{display:inline-block;background:var(--ac);color:#fff;font-weight:700;font-size:12px;line-height:1.35;padding:1px 8px;border-radius:8px;margin:0 1px;white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,.18)}",
      ".agri-sub{margin-top:7px;font-weight:700;color:var(--ac);font-size:12px;display:flex;align-items:center;gap:4px}",
      ".agri-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}",
      ".agri-act{background:var(--ac);color:#fff;border:none;border-radius:10px;padding:6px 11px;font-weight:700;font-size:12px;cursor:pointer;font-family:inherit;transition:filter .15s,transform .1s}",
      ".agri-act:hover{filter:brightness(1.08)}.agri-act:active{transform:scale(.95)}",
      ".agri-fab{position:relative;width:60px;height:60px;border-radius:50%;border:none;padding:0;cursor:pointer;pointer-events:auto;background:#fff;box-shadow:0 8px 22px rgba(20,60,25,.40);transition:transform .15s;overflow:visible}",
      ".agri-fab:hover{transform:translateY(-2px) scale(1.05)}",
      ".agri-fab svg{width:100%;height:100%;display:block;border-radius:50%}",
      ".agri-assistant.speaking .agri-fab{animation:agriSpeak 1.1s ease-in-out infinite}",
      "@keyframes agriSpeak{0%,100%{box-shadow:0 8px 22px rgba(20,60,25,.40),0 0 0 0 var(--ac)}50%{box-shadow:0 8px 22px rgba(20,60,25,.40),0 0 0 7px rgba(59,122,68,.16)}}",
      ".agri-svg .badge{fill:#f3f8f0;stroke:var(--ac);stroke-width:3}",
      ".agri-svg .skin{fill:#e0a877}.agri-svg .shirt{fill:var(--ac)}",
      ".agri-svg .eye{fill:#2a1c10;transform-box:fill-box;transform-origin:center;animation:agriBlink 5.2s infinite}",
      ".agri-svg .line{stroke:#6b4a2a;stroke-width:1.4;fill:none;stroke-linecap:round}",
      ".agri-svg .mouth{stroke:#6b4a2a;stroke-width:1.7;fill:none;stroke-linecap:round}",
      ".agri-svg .hat{fill:#e3c069;stroke:#b8923f;stroke-width:1.2}.agri-svg .band{stroke:#7a5230;stroke-width:2.4;fill:none;stroke-linecap:round}",
      "@keyframes agriBlink{0%,94%,100%{transform:scaleY(1)}97%{transform:scaleY(.1)}}",
      ".agri-news{position:absolute;top:-1px;right:-1px;width:13px;height:13px;border-radius:50%;background:#ffd23f;border:2px solid #fff;display:none}",
      ".agri-assistant.news .agri-news{display:block;animation:agriNews 1.2s infinite}",
      "@keyframes agriNews{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.3);opacity:.65}}",
      // Badge 💬 permanent : signale clairement qu'on peut DISCUTER (chatbot).
      ".agri-chat{position:absolute;left:-3px;bottom:-3px;width:21px;height:21px;border-radius:50%;background:#fff;border:2px solid var(--ac);display:grid;place-items:center;font-size:10px;box-shadow:0 2px 7px rgba(0,0,0,.22);animation:agriChat 3.4s ease-in-out infinite}",
      "@keyframes agriChat{0%,88%,100%{transform:scale(1)}94%{transform:scale(1.18)}}",
      // Pointeur : flèche animée + libellé du bouton à cliquer (suit la cible).
      ".agri-pointer{position:fixed;z-index:9997;pointer-events:none;display:none;flex-direction:column;align-items:center;transform:translateX(-50%);transition:left .25s ease,top .25s ease}",
      ".agri-pointer.on{display:flex}.agri-pointer.below{flex-direction:column-reverse}",
      ".agri-pointer .arr{font-size:25px;line-height:1;filter:drop-shadow(0 2px 3px rgba(0,0,0,.35));animation:agriBob 1s ease-in-out infinite}",
      ".agri-pointer .lab{margin:2px 0;background:#e0922f;color:#fff;font-weight:800;font-size:11.5px;padding:3px 10px;border-radius:10px;white-space:nowrap;box-shadow:0 5px 16px rgba(0,0,0,.3)}",
      "@keyframes agriBob{0%,100%{transform:translateY(0)}50%{transform:translateY(6px)}}",
      "@media (max-width:480px){.agri-assistant{right:12px;bottom:78px}.agri-fab{width:52px;height:52px}}",
    ].join('');
    document.head.appendChild(s);
  }

  // Avatar FERMIER (chapeau de paille, visage posé). Aucune animation de bouche.
  var FARMER =
    '<svg class="agri-svg" viewBox="0 0 72 72" aria-hidden="true">' +
      '<circle class="badge" cx="36" cy="36" r="34"/>' +
      '<clipPath id="agriClip"><circle cx="36" cy="36" r="34"/></clipPath>' +
      '<g clip-path="url(#agriClip)">' +
        '<path class="shirt" d="M12 74 V63 Q36 49 60 63 V74 Z"/>' +
        '<rect class="skin" x="31" y="45" width="10" height="11" rx="4"/>' +
        '<circle class="skin" cx="36" cy="39" r="13.5"/>' +
        '<circle class="skin" cx="22.8" cy="39" r="3"/><circle class="skin" cx="49.2" cy="39" r="3"/>' +
        '<path class="line" d="M28.6 34 q3.1 -1.9 6.2 0"/><path class="line" d="M37.2 34 q3.1 -1.9 6.2 0"/>' +
        '<circle class="eye" cx="31.6" cy="38.4" r="1.9"/><circle class="eye" cx="40.4" cy="38.4" r="1.9"/>' +
        '<path class="line" d="M36 40 v3"/>' +
        '<path class="mouth" d="M31.5 46 q4.5 3 9 0"/>' +
        '<ellipse class="hat" cx="36" cy="28.5" rx="23" ry="6.4"/>' +
        '<path class="hat" d="M25 29 Q36 8.5 47 29 Z"/>' +
        '<path class="band" d="M26 27.6 Q36 22.4 46 27.6"/>' +
      '</g>' +
    '</svg>';

  /* ---- construction ------------------------------------------------------ */
  function build() {
    if (st.built || !document.body) return;
    injectStyles();
    var root = document.createElement('div');
    root.className = 'agri-assistant';
    root.setAttribute('data-mood', 'idle');
    root.innerHTML =
      '<div class="agri-bubble"><button class="agri-bubble-x" title="Masquer" aria-label="Masquer">×</button>' +
        '<div class="agri-name"><span class="dot"></span>AgriBot</div>' +
        '<div class="agri-text"></div><div class="agri-sub"></div><div class="agri-actions"></div></div>' +
      '<button class="agri-fab" title="AgriBot — clique pour discuter avec moi">' + FARMER +
        '<span class="agri-news"></span><span class="agri-chat">💬</span></button>';
    document.body.appendChild(root);
    el.root = root;
    el.bubble = root.querySelector('.agri-bubble');
    el.text = root.querySelector('.agri-text');
    el.sub = root.querySelector('.agri-sub');
    el.actions = root.querySelector('.agri-actions');
    el.fab = root.querySelector('.agri-fab');
    // Pointeur (flèche + libellé) qui désigne le bouton à cliquer — au niveau du body.
    var ptr = document.createElement('div');
    ptr.className = 'agri-pointer';
    ptr.innerHTML = '<div class="arr">👇</div><div class="lab"></div>';
    document.body.appendChild(ptr);
    el.pointer = ptr;
    el.pointerArr = ptr.querySelector('.arr');
    el.pointerLab = ptr.querySelector('.lab');
    st.built = true;

    root.querySelector('.agri-bubble-x').onclick = function (e) { e.stopPropagation(); hideBubble(); };
    el.fab.onclick = onAvatarClick;
    hideOldFab();
    // Repositionne le pointeur quand la page défile / se redimensionne.
    ['scroll', 'resize'].forEach(function (ev) {
      window.addEventListener(ev, function () { if (st._ptStep) pointTo(st._ptStep); }, { passive: true });
    });
  }

  // Cible (sélecteur) + libellé du bouton à désigner, par étape.
  var PT = {
    lang:    { sel: '#lang-screen .lang-btn', lab: { fr: 'Choisissez une langue', ar: 'اختاروا لغة', da: 'ختاروا لغة' } },
    plan:    { sel: '#planEditor',            lab: { fr: 'Choisissez vos points de mesure ici', ar: 'اختاروا نقاط القياس هنا', da: 'ختاروا نقط القياس هنا' } },
    start:   { sel: '#btnStartReal',          lab: { fr: 'Démarrer mission', ar: 'بدء المهمة', da: 'بدء المهمة' } },
    done:    { sel: '.bottom-nav .bnav-item:nth-child(3)', lab: { fr: 'Voir les conseils', ar: 'النصائح', da: 'النصائح' } },
  };
  // Désigne le bouton à cliquer pour l'étape (flèche animée + libellé). Masqué
  // pendant la mission (running), quand le chat est ouvert, ou si la cible est absente.
  // Place la flèche + le libellé sur un élément cible précis.
  function pointAtEl(t, label) {
    if (!el.pointer) return;
    if (!t) { el.pointer.classList.remove('on'); return; }
    var r = t.getBoundingClientRect();
    if (r.width === 0 || r.bottom < 8 || r.top > window.innerHeight - 8) { el.pointer.classList.remove('on'); return; }
    var above = r.top > 64;                       // assez de place au-dessus ?
    el.pointer.classList.toggle('below', !above);
    el.pointerArr.textContent = above ? '👇' : '👆';
    el.pointerLab.textContent = label || '';
    var cx = r.left + r.width / 2;
    el.pointer.style.left = Math.max(64, Math.min(window.innerWidth - 64, cx)) + 'px';
    el.pointer.style.top = (above ? r.top - 48 : r.bottom + 6) + 'px';
    el.pointer.classList.add('on');
  }
  // Écran de langue : la flèche pointe CHAQUE langue, 3 s par bouton (cycle).
  function stopLangCycle() { clearTimeout(st.langTimer); st.langTimer = null; }
  function langCycleStep() {
    if (!st.built || !onLang() || chatOpen()) { stopLangCycle(); if (el.pointer) el.pointer.classList.remove('on'); return; }
    var btns = document.querySelectorAll('#lang-screen .lang-btn');
    if (!btns.length) { st.langTimer = setTimeout(langCycleStep, 600); return; }
    st.langIdx = (st.langIdx == null) ? 0 : (st.langIdx + 1) % btns.length;
    var b = btns[st.langIdx];
    pointAtEl(b, (b.textContent || '').trim());
    speakOneLang(st.langIdx);                             // VOIX synchronisée avec le pointeur
    st.langTimer = setTimeout(langCycleStep, 3000);       // 3 s sur chaque langue
  }
  function pointTo(step) {
    if (!el.pointer) return;
    st._ptStep = step;
    if (step === 'lang') {                                // cycle sur chaque langue
      if (!st.langTimer) { st.langIdx = null; langCycleStep(); }
      return;
    }
    stopLangCycle();
    var def = PT[step];
    if (!def || step === 'running' || chatOpen()) { el.pointer.classList.remove('on'); return; }
    pointAtEl(document.querySelector(def.sel), def.lab[lang()] || def.lab.fr);
  }

  // Masque l'ancien bouton flottant 🚜 : l'avatar fermier devient l'unique lanceur.
  function hideOldFab() { var f = document.getElementById('chatFab'); if (f) f.style.display = 'none'; }
  // Masque l'avatar quand le panneau de chat est ouvert (évite tout recouvrement).
  function watchPanel() {
    var p = document.getElementById('chatPanel');
    if (!p || p._agriWatched) return;
    p._agriWatched = true;
    try {
      new MutationObserver(function () {
        var open = p.classList.contains('open');
        if (el.root) el.root.style.display = open ? 'none' : '';
        if (open && el.pointer) el.pointer.classList.remove('on');   // pas de pointeur quand le chat est ouvert
      }).observe(p, { attributes: true, attributeFilter: ['class'] });
    } catch (e) { /* observer indispo : ignoré */ }
  }

  function onAvatarClick() {
    el.root.classList.remove('news');
    if (onLang()) { showBubble(); stopLangCycle(); st.langIdx = null; langCycleStep(); return; }   // écran langue : re-saluer + parler
    if (typeof window.toggleChatPanel === 'function') window.toggleChatPanel();  // sinon : ouvrir le chat
    else { showBubble(); if (st.curText) speak(st.curText); }
  }

  /* ---- voix (avatar sérieux : halo discret, pas de bouche) --------------- */
  function setMood(m) { if (el.root) el.root.setAttribute('data-mood', m || 'idle'); }
  function setSpeaking(on) { if (el.root) el.root.classList.toggle('speaking', !!on); }
  function speak(text) {
    try {
      if (window.CHATBOT_SPEAK === false || typeof window.speakBotAnswer !== 'function') return;
      var t = clean(text); if (!t) return;
      setSpeaking(true);
      clearTimeout(st.hideTimer);          // NE PAS masquer la bulle pendant la lecture
      if (window.stopBotVoice) window.stopBotVoice();
      var ended = function () { setSpeaking(false); scheduleHide(3200); };  // fin de voix → on laisse 3,2 s puis on masque
      window.speakBotAnswer(t, ended);
      clearTimeout(st.talkTimer);
      // Repli si la callback de fin n'est jamais appelée (estimation de durée).
      st.talkTimer = setTimeout(ended, Math.min(22000, 2000 + t.length * 80));
    } catch (e) { setSpeaking(false); scheduleHide(3200); }
  }

  /* ---- bulle (auto-masquée, non bloquante) ------------------------------- */
  // Rend le texte en remplaçant les noms de boutons « … » par des PASTILLES
  // stylées (et lit le texte sans les guillemets). DOM sûr (pas d'innerHTML).
  function renderRich(container, text) {
    container.textContent = '';
    var re = /«\s*([^»]+?)\s*»/g, last = 0, m;
    while ((m = re.exec(String(text || ''))) !== null) {
      if (m.index > last) container.appendChild(document.createTextNode(text.slice(last, m.index)));
      var chip = document.createElement('span');
      chip.className = 'agri-btn';
      chip.textContent = m[1];
      container.appendChild(chip);
      last = re.lastIndex;
    }
    if (last < String(text || '').length) container.appendChild(document.createTextNode(text.slice(last)));
  }
  function setBubble(text, actions, sub) {
    if (!el.root) return;
    st.curText = text;
    renderRich(el.text, text);
    renderRich(el.sub, sub || '');
    el.sub.style.display = sub ? '' : 'none';
    el.actions.innerHTML = '';
    (actions || []).forEach(function (a) {
      var b = document.createElement('button');
      b.className = 'agri-act'; b.textContent = a.label;
      b.onclick = function (e) { e.stopPropagation(); try { a.on(); } catch (_) {} };
      el.actions.appendChild(b);
    });
  }
  function scheduleHide(ms) {
    clearTimeout(st.hideTimer);
    st.hideTimer = setTimeout(function () { if (el.root) el.root.classList.remove('show'); }, ms);
  }
  function showBubble() {
    if (!el.root) return;
    if (chatOpen()) { el.root.classList.add('news'); return; }   // chat ouvert : pas de bulle
    el.root.classList.add('show'); el.root.classList.remove('news');
    // Repli : si la voix est coupée (muet) ou absente, on masque après 16 s.
    // Sinon c'est la FIN de la lecture (speak) qui pilote le masquage.
    scheduleHide(16000);
  }
  function hideBubble() { if (el.root) el.root.classList.remove('show'); clearTimeout(st.hideTimer); }

  // Le guidage ne s'affiche PLUS dans le chatbot (demandé) : la bulle de AgriBot
  // est le seul canal du guidage ; le chat reste réservé aux échanges Q/R.
  function mirrorToChat() { /* no-op */ }

  /* ---- phrasage LLM (route /api/coach) ----------------------------------- */
  function fetchCoach(ctx) {
    return new Promise(function (resolve) {
      try {
        if (window.AGRIBOTICS_COACH === false || typeof API_BASE === 'undefined' || !ctx) { resolve(null); return; }
        var ctrl = new AbortController();
        // 8 s : laisse au LLM le temps de répondre (1er appel à froid ~7 s) pour
        // que la phrase soit affichée puis mise en cache. L'affichage local est
        // instantané et la voix part au plus tard à 2,6 s → aucune attente perçue.
        var to = setTimeout(function () { try { ctrl.abort(); } catch (_) {} }, 8000);
        var headers = { 'Content-Type': 'application/json' };
        if (window.AGRIBOTICS_API_KEY) headers['X-API-Key'] = window.AGRIBOTICS_API_KEY;
        fetch(API_BASE + '/coach', { method: 'POST', headers: headers, body: JSON.stringify(ctx), signal: ctrl.signal })
          .then(function (r) { clearTimeout(to); return r.ok ? r.json() : null; })
          .then(function (j) { resolve(j && j.text ? String(j.text).trim() : null); })
          .catch(function () { clearTimeout(to); resolve(null); });
      } catch (e) { resolve(null); }
    });
  }

  // Affiche le LOCAL tout de suite, puis remplace par la phrase LLM si elle
  // arrive sous ~2,6 s ; sinon garde le local. Parle UNE fois (texte final).
  function present(localText, actions, mood, sub, ctx) {
    var token = ++st.tipToken;
    setMood(mood);
    setBubble(localText, actions, sub);
    showBubble();
    var key = ctx ? (ctx.step + '|' + ctx.language + '|' + (ctx.measured == null ? '' : ctx.measured) + '|' + (ctx.nudge ? 'n' : '')) : null;
    var finalize = function (text, doMirror) {
      if (token !== st.tipToken) return;
      setBubble(text, actions, sub);
      showBubble();
      if (doMirror !== false) mirrorToChat(text, actions);
      speak(text);
    };
    if (key && coachCache[key]) { finalize(coachCache[key]); return; }
    if (!ctx) { finalize(localText); return; }
    var done = false;
    var timer = setTimeout(function () { if (!done) { done = true; finalize(localText); } }, 2600);
    fetchCoach(ctx).then(function (gpt) {
      if (gpt && key) coachCache[key] = gpt;
      if (done) return;                       // local déjà finalisé : on garde en cache pour la prochaine fois
      done = true; clearTimeout(timer);
      finalize(gpt || localText);
    });
  }

  function actsFor(step, L) {
    if (step === 'running') return [{ label: '🗺️ ' + L.seeMap, on: function () { try { _guideGoto(2); } catch (_) {} } }];
    if (step === 'done') return [{ label: '💡 ' + L.seeAdvice, on: function () { try { _guideGoto(3); } catch (_) {} } }];
    return null;
  }

  /* ---- moteur de guidage (lit l'interface) ------------------------------- */
  function update(force) {
    try {
      if (!st.built) build();
      if (!el.root) return;
      hideOldFab(); watchPanel();
      if (onLang()) {
        setMood('idle');
        if (!st.introShown) { st.introShown = true; setBubble(INTRO_ALL, null, ''); showBubble(); pointTo('lang'); resetIdle('lang'); }
        return;
      }
      if (typeof _GUIDE_TXT === 'undefined' || typeof _coachStepName !== 'function') return;
      var L = _GUIDE_TXT[lang()] || _GUIDE_TXT.fr;
      var r = ((typeof APP_STATE !== 'undefined' && APP_STATE.robot) || {});
      var step = _coachStepName();
      if (typeof _guidePulse === 'function') _guidePulse(step);
      pointTo(step);                          // désigne le bouton à cliquer (suit la page)

      // 1) Accueil : se présente UNE fois + 1ère consigne, puis discret.
      if (!st.spoke) {
        st.spoke = true; st.lastStep = step; st.lastMeasured = r.measuredPoints || 0;
        // Première bulle : on glisse l'indice « tape-moi pour discuter » (sous-texte)
        // pour que l'utilisateur découvre que AgriBot est AUSSI un chatbot.
        present(L.welcome + ' ' + (L[step] || ''), actsFor(step, L), MOOD[step] || 'idle',
                CHAT_HINT[lang()] || CHAT_HINT.fr, { step: step, language: lang() });
        if (step === 'running') setTimeout(function () { try { _guideGoto(2); } catch (_) {} }, 800);
        resetIdle(step);
        return;
      }
      // 2) Changement d'étape (l'utilisateur a agi) → nouvelle consigne.
      if (force || step !== st.lastStep) {
        st.lastStep = step; st.lastMeasured = r.measuredPoints || 0;
        var sub = '';
        if (step === 'done') {
          var sm = (typeof _missionSummary === 'function') ? _missionSummary() : null;
          if (sm) sub = L.summary(sm.good, sm.total, sm.bad);
          if (typeof _confetti === 'function') _confetti();
        }
        present(L[step] || '', actsFor(step, L), MOOD[step] || 'idle', sub, { step: step, language: lang() });
        if (step === 'running') setTimeout(function () { try { _guideGoto(2); } catch (_) {} }, 800);
        resetIdle(step);
        return;
      }
      // 3) Mission en cours : commente chaque NOUVELLE zone mesurée.
      if (step === 'running') {
        var m = r.measuredPoints || 0;
        if (m > st.lastMeasured) {
          st.lastMeasured = m;
          var z = r.activePoint || ('P' + m);
          present(L.progress(z, m, r.totalPoints || 0), actsFor('running', L), 'happy', '',
                  { step: 'progress', language: lang(), zone: z, measured: m, total: r.totalPoints || 0 });
        }
      }
    } catch (e) { /* le guidage ne doit jamais casser l'app */ }
  }

  /* ---- relances sur inactivité (3 MAX par étape, puis fini) --------------- */
  function clearIdle() { clearTimeout(IDLE.timer); IDLE.timer = null; }
  // (Re)programme le PROCHAIN minuteur SANS toucher au compteur (appelé sur
  // activité). Au-delà du max → aucune relance jusqu'au prochain changement d'étape.
  function bumpIdle() {
    clearIdle();
    if (IDLE.count >= IDLE.max) return;                    // 3 relances faites → terminé
    var d = IDLE.delays[Math.min(IDLE.count, IDLE.delays.length - 1)];
    IDLE.timer = setTimeout(onIdle, d);
  }
  // Nouvelle étape (l'utilisateur a progressé) → repart sur 3 relances fraîches.
  function resetIdle(step) { IDLE.count = 0; IDLE.step = step || null; bumpIdle(); }
  function onIdle() {
    try {
      if (!st.built || !el.root) return;
      var step = onLang() ? 'lang' : ((typeof _coachStepName === 'function') ? _coachStepName() : null);
      if (!step || step === 'running') { clearIdle(); return; }   // pas de relance pendant la mission auto
      if (step !== IDLE.step) { resetIdle(step); return; }        // anti-flap : étape changée → on repart
      if (chatOpen() || el.root.classList.contains('speaking')) { // occupé : on retente sans consommer
        IDLE.timer = setTimeout(onIdle, 8000); return;
      }
      IDLE.count += 1;
      doNudge(step);
      bumpIdle();                                                 // planifie la suivante (s'arrête au max)
    } catch (e) { /* relance non bloquante */ }
  }
  function doNudge(step) {
    var N = NUDGE_TXT[lang()] || NUDGE_TXT.fr;
    if (step === 'lang') { present(N.lang, null, 'action', '', null); return; }
    var L = (typeof _GUIDE_TXT !== 'undefined') ? (_GUIDE_TXT[lang()] || _GUIDE_TXT.fr) : {};
    var local = N[step] || (L[step] || '');
    if (!local) return;
    present(local, actsFor(step, L), 'action', CHAT_HINT[lang()] || CHAT_HINT.fr,
            { step: step, language: lang(), nudge: true });
  }

  window.Assistant = {
    update: update,
    reset: function () { st.spoke = false; st.lastStep = null; st.lastMeasured = -1; st.introShown = false; clearIdle(); IDLE.count = 0; IDLE.step = null; },
    say: function (text, actions, mood) { if (!st.built) build(); present(text, actions, mood || 'idle', '', null); },
  };

  // Toute interaction RÉAMORCE le minuteur (repousse la prochaine relance) mais
  // NE remet PAS le compteur à zéro → on reste plafonné à 3 relances par étape.
  ['pointerdown', 'keydown', 'touchstart'].forEach(function (ev) {
    document.addEventListener(ev, function () { if (st.built) bumpIdle(); }, { passive: true, capture: true });
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { build(); update(); });
  else { build(); update(); }
})();
