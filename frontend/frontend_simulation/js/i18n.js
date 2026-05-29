/*
  Agri-Botics i18n + safe global helpers.
  Important: language selection must NOT depend on chatbot.js.
*/
(function () {
  const CROP_LABELS = {
    fr: {
      "Blé": "Blé", "Tomate": "Tomate", "Oignon": "Oignon", "Carotte": "Carotte",
      "Pomme de terre": "Pomme de terre", "Orge": "Orge", "Betterave à sucre": "Betterave à sucre",
      "Olivier": "Olivier", "Vigne": "Vigne", "Pastèque": "Pastèque"
    },
    ar: {
      "Blé": "القمح", "Tomate": "الطماطم", "Oignon": "البصل", "Carotte": "الجزر",
      "Pomme de terre": "البطاطس", "Orge": "الشعير", "Betterave à sucre": "الشمندر السكري",
      "Olivier": "الزيتون", "Vigne": "العنب", "Pastèque": "البطيخ"
    },
    da: {
      "Blé": "القمح", "Tomate": "مطيشة", "Oignon": "البصلة", "Carotte": "خيزو",
      "Pomme de terre": "البطاطا", "Orge": "الشعير", "Betterave à sucre": "الباربا",
      "Olivier": "الزيتون", "Vigne": "العنب", "Pastèque": "الدلاح"
    }
  };

  const D = {
    fr: {
      badge:"FR", dir:"ltr", langName:"Français",
      status:"Mode simulation", statusReal:"Mode réel",
      langTitle:"Agri-Botics", langSub:"Choisissez votre langue / اختر لغتك",
      greetTitle:"Bonjour !", greetSub:"Votre champ, votre robot et vos recommandations au même endroit",
      tagSimulation:"Simulation frontend", tagMap:"Carte dynamique", tagZone:"Culture zone par zone",
      missionTitle:"🤖 Mission terrain", missionReady:"En attente", missionReadyText:"Mission prête",
      activePoint:"Point actif", progress:"Progression", measurements:"Mesures", globalCrop:"Culture globale",
      demoLocal:"démo locale", startSimulation:"▶ Démarrer simulation", nextStep:"+ Étape suivante", reset:"↺ Réinitialiser",
      runtimeNote:"Cette version fonctionne sans robot ni backend. Elle simule le déplacement du robot, les mesures et la coloration progressive des zones.",
      humidity:"Humidité", soilPh:"pH du sol", ph:"pH", temperature:"Température", waiting:"En attente", fieldAverage:"moyenne parcelle",
      quickMap:"🎯 Lecture rapide de la carte", capturedValues:"Valeurs captées", lowHumidity:"Humidité faible", outPh:"pH hors plage", limitValue:"Valeur limite", correctValue:"Valeur correcte",
      blue:"Bleu", red:"Rouge", yellow:"Jaune", green:"Vert",
      chatTitle:"Posez votre question", chatWelcome:"Bonjour ! Je peux expliquer les zones, les cultures et les actions à mener.", chatPlaceholder:"Écrire une question...",
      sugWater:"💧 Quelle quantité d’eau ?", sugCrop:"🌾 Quelle culture choisir ?", sugZone:"📍 Action sur ", sugRobot:"🤖 Où est le robot ?",
      robot:"Robot", measuredZones:"zones mesurées", measuredSing:"zone(s) mesurée(s)",
      mapSubtitle:"La coloration dépend uniquement de la valeur captée. Les zones non mesurées restent grisées.",
      robotNote:"🤖 = position actuelle du robot · ✓ = zone mesurée",
      selectZone:"Sélectionnez une zone", map:"Carte", mapHumidity:"💧 Humidité", mapPh:"🧪 pH", mapTemp:"🌡️ Température", mapEc:"⚡ Conductivité",
      weak:"Faible", correct:"Correcte", high:"Élevée", outRange:"Hors plage", borderline:"Limite", unmeasured:"Non mesurée",
      scaleLow:"Valeur faible / hors plage", scaleGood:"Valeur correcte",
      recoTitle:"💡 Conseils zone par zone", recoSub:"Choisissez une culture par zone. Pour cultiver un seul produit partout, appliquez la même culture à toutes les zones.",
      cropToApply:"Culture à appliquer", applyEverywhere:"Appliquer partout", planTitle:"🧩 Plan de culture par zone", clickZone:"Cliquez une zone",
      selectedZone:"Zone sélectionnée", measure:"Mesure", water:"Eau", watch:"Surveiller", good:"Correct", correction:"Correction",
      waterTitle:"Irrigation", limeTitle:"Chaux", compostTitle:"Compost", fertilizationTitle:"Fertilisation", surveillanceTitle:"Surveillance", tempTitle:"Température", ecTitle:"Lessivage salinité", leachSalt:"apport eau pour lessiver",
      alreadyWet:"Sol déjà humide", raisePh:"pH à relever", correctPh:"pH à corriger", organicInput:"apport organique", compatibility:"compatibilité", adaptDate:"attendre/adapter date",
      cropApplied:"{crop} appliquée à toutes les zones", simStarted:"Simulation démarrée", simFinished:"Mission simulée terminée",
      simReady:"Simulation prête", simRunning:"Simulation en cours", simDone:"Simulation terminée", measuringAt:"Mesure au point {point}",
      navFarmer:"Terrain", navMap:"Carte", navReco:"Conseils",
      backendUnavailable:"Backend non joignable. Réponse locale utilisée."
    },
    ar: {
      badge:"ع", dir:"rtl", langName:"العربية",
      status:"وضع المحاكاة", statusReal:"الوضع الحقيقي",
      langTitle:"Agri-Botics", langSub:"اختر لغتك",
      greetTitle:"مرحباً !", greetSub:"حقلك وروبوتك وتوصياتك في مكان واحد",
      tagSimulation:"محاكاة الواجهة", tagMap:"خريطة ديناميكية", tagZone:"زراعة حسب المنطقة",
      missionTitle:"🤖 مهمة ميدانية", missionReady:"في الانتظار", missionReadyText:"المهمة جاهزة",
      activePoint:"النقطة الحالية", progress:"التقدم", measurements:"القياسات", globalCrop:"المحصول العام",
      demoLocal:"محاكاة محلية", startSimulation:"▶ بدء المحاكاة", nextStep:"+ الخطوة التالية", reset:"↺ إعادة التهيئة",
      runtimeNote:"هذه النسخة تعمل بدون روبوت أو خادم. تحاكي حركة الروبوت والقياسات وتلوين المناطق تدريجياً.",
      humidity:"الرطوبة", soilPh:"pH التربة", ph:"pH", temperature:"درجة الحرارة", waiting:"في الانتظار", fieldAverage:"متوسط الحقل",
      quickMap:"🎯 قراءة سريعة للخريطة", capturedValues:"القيم المقاسة", lowHumidity:"رطوبة منخفضة", outPh:"pH خارج المجال", limitValue:"قيمة حدية", correctValue:"قيمة مناسبة",
      blue:"أزرق", red:"أحمر", yellow:"أصفر", green:"أخضر",
      chatTitle:"اطرح سؤالك", chatWelcome:"مرحباً! يمكنني شرح المناطق والمحاصيل والإجراءات المقترحة.", chatPlaceholder:"اكتب سؤالاً...",
      sugWater:"💧 ما كمية الماء؟", sugCrop:"🌾 أي محصول أختار؟", sugZone:"📍 ماذا أفعل في ", sugRobot:"🤖 أين الروبوت؟",
      robot:"الروبوت", measuredZones:"مناطق مقاسة", measuredSing:"منطقة/مناطق مقاسة",
      mapSubtitle:"التلوين يعتمد فقط على القيمة المقاسة. المناطق غير المقاسة تبقى رمادية.",
      robotNote:"🤖 = موقع الروبوت الحالي · ✓ = منطقة مقاسة",
      selectZone:"اختر منطقة", map:"الخريطة", mapHumidity:"💧 الرطوبة", mapPh:"🧪 pH", mapTemp:"🌡️ درجة الحرارة", mapEc:"⚡ الموصلية",
      weak:"منخفضة", correct:"مناسبة", high:"مرتفعة", outRange:"خارج المجال", borderline:"حدية", unmeasured:"غير مقاسة",
      scaleLow:"قيمة منخفضة / خارج المجال", scaleGood:"قيمة مناسبة",
      recoTitle:"💡 نصائح حسب المنطقة", recoSub:"اختر محصولاً لكل منطقة. ولزراعة محصول واحد في كل الحقل، طبّق نفس المحصول على جميع المناطق.",
      cropToApply:"المحصول المراد تطبيقه", applyEverywhere:"تطبيق على الكل", planTitle:"🧩 خطة الزراعة حسب المنطقة", clickZone:"انقر على منطقة",
      selectedZone:"المنطقة المختارة", measure:"القياس", water:"ماء", watch:"مراقبة", good:"مناسب", correction:"تصحيح",
      waterTitle:"ري", limeTitle:"الجير الزراعي", compostTitle:"كومبوست", fertilizationTitle:"تسميد", surveillanceTitle:"مراقبة", tempTitle:"درجة الحرارة", ecTitle:"غسيل الملوحة", leachSalt:"ري لتخفيف الأملاح",
      alreadyWet:"التربة رطبة بالفعل", raisePh:"رفع قيمة pH", correctPh:"تصحيح pH", organicInput:"إضافة عضوية", compatibility:"التوافق", adaptDate:"انتظار/تعديل موعد الزراعة",
      cropApplied:"تم تطبيق {crop} على جميع المناطق", simStarted:"بدأت المحاكاة", simFinished:"انتهت المحاكاة",
      simReady:"المحاكاة جاهزة", simRunning:"المحاكاة جارية", simDone:"انتهت المحاكاة", measuringAt:"قياس في النقطة {point}",
      navFarmer:"الحقـل", navMap:"الخريطة", navReco:"النصائح",
      backendUnavailable:"الخادم غير متاح. تم استخدام إجابة محلية."
    },
    da: {
      badge:"DA", dir:"rtl", langName:"الدارجة",
      status:"مود المحاكاة", statusReal:"المود الحقيقي",
      langTitle:"Agri-Botics", langSub:"اختار اللغة ديالك",
      greetTitle:"سلام !", greetSub:"الحقل، الروبو والنصائح مجموعين فبلاصة وحدة",
      tagSimulation:"محاكاة فالواجهة", tagMap:"خريطة كتتبدل", tagZone:"زرع حسب الزون",
      missionTitle:"🤖 مهمة فالحقل", missionReady:"كيتسنى", missionReadyText:"المهمة واجدة",
      activePoint:"النقطة الحالية", progress:"التقدم", measurements:"القياسات", globalCrop:"الزرعة العامة",
      demoLocal:"ديمو محلي", startSimulation:"▶ بدا المحاكاة", nextStep:"+ الخطوة الجاية", reset:"↺ عاود من اللول",
      runtimeNote:"هاد النسخة كتخدم بلا روبو وبلا backend. كتحاكي الحركة والقياسات وتلوين الزونات.",
      humidity:"الرطوبة", soilPh:"pH ديال التراب", ph:"pH", temperature:"الحرارة", waiting:"كيتسنى", fieldAverage:"معدل الحقل",
      quickMap:"🎯 قراءة سريعة للخريطة", capturedValues:"القيم لي تقاسو", lowHumidity:"الرطوبة ناقصة", outPh:"pH خارج المجال", limitValue:"قيمة خاصها مراقبة", correctValue:"قيمة مزيانة",
      blue:"زرق", red:"حمر", yellow:"صفر", green:"خضر",
      chatTitle:"سول سؤالك", chatWelcome:"سلام! نقدر نشرح الزونات، الزرع، والإجراءات لي خاص دير.", chatPlaceholder:"كتب سؤالك...",
      sugWater:"💧 شحال من الما؟", sugCrop:"🌾 شنو نزرع؟", sugZone:"📍 شنو ندير فـ ", sugRobot:"🤖 فين الروبو؟",
      robot:"الروبو", measuredZones:"زونات تقاسو", measuredSing:"زون/زونات تقاسو",
      mapSubtitle:"اللون كيتبدل غير حسب القيمة لي تقاسات. الزونات لي ما تقاسوش كيبقاو رماديين.",
      robotNote:"🤖 = بلاصة الروبو دابا · ✓ = زون تقاسات",
      selectZone:"اختار زون", map:"الخريطة", mapHumidity:"💧 الرطوبة", mapPh:"🧪 pH", mapTemp:"🌡️ الحرارة", mapEc:"⚡ الكوندوكتي",
      weak:"ناقصة", correct:"مزيانة", high:"طالعة", outRange:"خارجة", borderline:"حدية", unmeasured:"ما تقاساتش",
      scaleLow:"قيمة ناقصة / خارجة", scaleGood:"قيمة مزيانة",
      recoTitle:"💡 نصائح حسب الزون", recoSub:"اختار الزرعة لكل زون. إلا بغيتي زرعة وحدة فالحقل كامل، طبقها على كل الزونات.",
      cropToApply:"الزرعة لي بغيتي تطبق", applyEverywhere:"طبق على الكل", planTitle:"🧩 بلان ديال الزرع حسب الزون", clickZone:"كليكي على زون",
      selectedZone:"الزون المختارة", measure:"القياس", water:"ما", watch:"راقب", good:"مزيان", correction:"تصحيح",
      waterTitle:"السقي", limeTitle:"الجير الفلاحي", compostTitle:"كومبوست", fertilizationTitle:"تسميد", surveillanceTitle:"مراقبة", tempTitle:"الحرارة", ecTitle:"تخفيف الملوحة", leachSalt:"سقي باش تتخفف الأملاح",
      alreadyWet:"التراب فيه الما كافي", raisePh:"طلع pH", correctPh:"صحح pH", organicInput:"إضافة عضوية", compatibility:"التوافق", adaptDate:"تسنى/بدل وقت الزرع",
      cropApplied:"تطبقات {crop} على كل الزونات", simStarted:"بدات المحاكاة", simFinished:"سالات المحاكاة",
      simReady:"المحاكاة واجدة", simRunning:"المحاكاة خدامة", simDone:"المحاكاة سالات", measuringAt:"قياس فالنقطة {point}",
      navFarmer:"الحقل", navMap:"الخريطة", navReco:"النصائح",
      backendUnavailable:"السيرفر ما خدامش. استعملت جواب محلي."
    }
  };

  window.currentLang = localStorage.getItem("agribotics_lang") || "fr";

  window.t = function (key, vars = {}) {
    const lang = window.currentLang || "fr";
    let val = (D[lang] && D[lang][key]) || D.fr[key] || key;
    Object.entries(vars).forEach(([k, v]) => { val = val.replaceAll(`{${k}}`, v); });
    return val;
  };

  window.cropLabel = function (name) {
    const lang = window.currentLang || "fr";
    return (CROP_LABELS[lang] && CROP_LABELS[lang][name]) || name;
  };

  window.dirIsRTL = function () {
    return (window.currentLang || "fr") !== "fr";
  };

  window.trStatus = function (status) {
    if (!status) return t("waiting");
    const s = String(status);
    const point = (s.match(/[ABC][123]/) || [""])[0];
    if (/Simulation prête|En attente/.test(s)) return t("simReady");
    if (/Simulation en cours/.test(s)) return t("simRunning");
    if (/Simulation terminée/.test(s)) return t("simDone");
    if (/Mesure au point/.test(s)) return t("measuringAt", { point });
    if (/Backend indisponible/.test(s)) return window.currentLang === "fr" ? "Backend indisponible" : (window.currentLang === "ar" ? "الخادم غير متاح" : "السيرفر ما خدامش");
    return s;
  };

  function setText(selector, value) {
    const el = document.querySelector(selector);
    if (el) el.textContent = value;
  }

  function setAll(selector, values) {
    const els = document.querySelectorAll(selector);
    els.forEach((el, i) => { if (values[i] !== undefined) el.textContent = values[i]; });
  }

  function setPlaceholder(selector, value) {
    const el = document.querySelector(selector);
    if (el) el.placeholder = value;
  }

  window.showToast = function (msg) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2300);
  };

  window.applyLanguage = function () {
    const lang = window.currentLang || "fr";
    document.documentElement.lang = lang === "da" ? "ar-MA" : lang;
    document.documentElement.dir = D[lang].dir;
    document.body.dir = D[lang].dir;
    document.body.classList.toggle("rtl", lang !== "fr");

    setText("#langBadge", t("badge"));
    setText("#statusTxt", (window.APP_STATE && APP_STATE.runtimeMode === "real") ? t("statusReal") : t("status"));
    setText("#greet-title", t("greetTitle"));
    setText("#greet-sub", t("greetSub"));
    setText("#lbl-water", t("humidity"));
    setText("#lbl-ph", t("soilPh"));
    setText("#lbl-temp", t("temperature"));
    setText("#lbl-ec", t("mapEc"));
    setText("#chat-title", t("chatTitle"));
    setText("#chat-welcome", t("chatWelcome"));
    setPlaceholder("#chatInput", t("chatPlaceholder"));
    setText("#nav-farmer", t("navFarmer"));
    setText("#nav-map", t("navMap"));
    setText("#nav-reco", t("navReco"));

    setText(".mission-title", t("missionTitle"));
    setAll(".mission-stat-label", [t("activePoint"), t("progress"), t("measurements"), t("globalCrop")]);
    setText(".runtime-note", t("runtimeNote"));
    setAll(".mission-actions button", [t("startSimulation"), t("nextStep"), t("reset")]);
    setText(".quick-intent-head .section-title", t("quickMap"));
    setText(".quick-intent-head .mini-badge", t("capturedValues"));
    setAll(".quick-intent-item strong", [t("blue"), t("red"), t("yellow"), t("green")]);
    setAll(".quick-intent-item p", [t("lowHumidity"), t("outPh"), t("limitValue"), t("correctValue")]);
    const currentZone = (window.APP_STATE && APP_STATE.selectedZone) || 'A1';
    const zoneSuffix = (lang === 'fr') ? ' ?' : '؟';
    setAll("#sugQuestions .sug-q", [t("sugWater"), t("sugCrop"), t("sugZone") + currentZone + zoneSuffix, t("sugRobot")]);

    setText(".map-subtitle", t("mapSubtitle"));
    setText(".robot-marker-note", t("robotNote"));
    const mapBtns = document.querySelectorAll("#mapVarBtns .map-var-btn");
    if (mapBtns[0]) mapBtns[0].textContent = t("mapHumidity");
    if (mapBtns[1]) mapBtns[1].textContent = t("mapPh");
    if (mapBtns[2]) mapBtns[2].textContent = t("mapTemp");
    if (mapBtns[3]) mapBtns[3].textContent = t("mapEc");

    setText(".reco-hero h2", t("recoTitle"));
    setText(".reco-hero p", t("recoSub"));
    setText("label[for='globalCropSelect']", t("cropToApply"));
    setText(".crop-selector-row .btn-primary", t("applyEverywhere"));
    setText("#page-reco .card-title", t("planTitle"));
    setText("#page-reco .mini-badge", t("clickZone"));
    setText("#zoneDetailPanel .section-title", t("selectedZone"));

    const langScreen = document.getElementById("lang-screen");
    if (langScreen) {
      const h1 = langScreen.querySelector("h1");
      const p = langScreen.querySelector("p");
      if (h1) h1.textContent = t("langTitle");
      if (p) p.textContent = t("langSub");
    }
  };

  window.chooseLang = function (lang) {
    if (!D[lang]) lang = "fr";
    window.currentLang = lang;
    if (window.APP_STATE) APP_STATE.language = lang;
    localStorage.setItem("agribotics_lang", lang);
    const screen = document.getElementById("lang-screen");
    if (screen) screen.style.display = "none";
    applyLanguage();
    if (typeof populateCropSelects === "function") populateCropSelects();
    if (typeof renderAll === "function") renderAll();
    if (typeof drawMap === "function") setTimeout(drawMap, 40);
  };

  window.openLangScreen = function () {
    const screen = document.getElementById("lang-screen");
    if (screen) screen.style.display = "flex";
  };

  document.addEventListener("DOMContentLoaded", () => {
    applyLanguage();
    const screen = document.getElementById("lang-screen");
    if (screen) screen.style.display = "flex";
  });
})();
