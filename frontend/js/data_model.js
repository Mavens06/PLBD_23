// ======== CORE STATE ========
const LATEST_MEASURE = {
  humidity: 42,
  ph: 6.4,
  ec: 1.8,
  temp: 18
};

const MISSION_STATE = {
  status: "Mesure en cours",
  totalPoints: 24,
  completedPoints: 17,
  activePoint: "C3",
  battery: 74,
  mode: "Points fixes",
  sensorCount: 4,
  stabilizationSec: 4,
  sampleCount: 10,
  quality: "OK"
};

const WEATHER_FALLBACK = {
  location: "Ben Guerir, Maroc",
  temperature: 24,
  humidity: 12,
  wind: 18,
  rain3d: 0,
  weatherCode: 0
};

const CULTURES = [
  { id:"ble", name:"Blé tendre", emoji:"🌾", cat:"cereale", match:88, color:"#2E7D32",
    season:"Oct – Mai", water:"350–500 mm", phRange:"6.0–7.5", ecRange:"< 2.5 mS/cm",
    desc:"Céréale · Plaine · Semi-aride" },
  { id:"orge", name:"Orge", emoji:"🌾", cat:"cereale", match:92, color:"#388E3C",
    season:"Oct – Mai", water:"250–400 mm", phRange:"6.0–8.0", ecRange:"< 3.0 mS/cm",
    desc:"Céréale · Tolérant sécheresse" },
  { id:"mais", name:"Maïs", emoji:"🌽", cat:"cereale", match:64, color:"#F57F17",
    season:"Avr – Sep", water:"500–800 mm", phRange:"5.8–7.0", ecRange:"< 1.8 mS/cm",
    desc:"Céréale · Besoin eau élevé" },
  { id:"tomate", name:"Tomate", emoji:"🍅", cat:"fruit", match:71, color:"#C62828",
    season:"Mar – Jul", water:"400–600 mm", phRange:"6.0–6.8", ecRange:"< 2.5 mS/cm",
    desc:"Fruit · Maraîchage · Irrigation" },
  { id:"pdt", name:"Pomme de terre", emoji:"🥔", cat:"legume", match:74, color:"#D2B48C",
    season:"Oct – Mar", water:"400–600 mm", phRange:"5.0–6.5", ecRange:"< 1.7 mS/cm",
    desc:"Légume · Besoin élevé en eau" },
  { id:"oignon", name:"Oignon", emoji:"🧅", cat:"legume", match:68, color:"#6A1B9A",
    season:"Sep – Mar", water:"350–500 mm", phRange:"6.0–7.0", ecRange:"< 1.8 mS/cm",
    desc:"Légume bulbe · Demande régulière en eau" },
  { id:"olive", name:"Olivier", emoji:"🫒", cat:"fruit", match:95, color:"#556B2F",
    season:"Toute l'année", water:"200–400 mm", phRange:"6.5–8.5", ecRange:"< 3.5 mS/cm",
    desc:"Arboriculture · Emblème du Maroc" },
  { id:"agrumes", name:"Agrumes", emoji:"🍊", cat:"fruit", match:82, color:"#FF8C00",
    season:"Toute l'année", water:"600–900 mm", phRange:"5.5–7.5", ecRange:"< 2.2 mS/cm",
    desc:"Fruit · Irrigation nécessaire" },
  { id:"luzerne", name:"Luzerne", emoji:"🌿", cat:"fourrage", match:84, color:"#43A047",
    season:"Toute l'année", water:"700–1200 mm", phRange:"6.2–7.8", ecRange:"< 2.0 mS/cm",
    desc:"Fourrage · Bonne reprise après coupe" },
  { id:"pois", name:"Pois chiche", emoji:"🫘", cat:"legume", match:90, color:"#0277BD",
    season:"Nov – Avr", water:"250–400 mm", phRange:"5.5–7.5", ecRange:"< 2.8 mS/cm",
    desc:"Légumineuse · Très adapté semi-aride" }
];

let currentCultureFilter = "all";
let selectedCulture = null;

const PH_HISTORY_7DAYS = [6.1, 6.3, 6.2, 6.5, 6.4, 6.3, 6.4];

const TEMPORAL_DATA = {
  sessions: ["S1 – 08/03", "S2 – 10/03", "S3 – 12/03"],
  ph: [5.8, 6.1, 6.2],
  hum: [39, 41, 42],
  ec: [2.1, 1.9, 1.8]
};

const ZONES_HEALTH = [
  [55, 72, 80], [40, 48, 62], [88, 90, 91], [30, 35, 50],
  [65, 70, 74], [78, 80, 83], [22, 28, 40], [55, 60, 65],
  [90, 91, 92], [44, 50, 55], [66, 68, 70], [38, 42, 48],
  [80, 82, 85], [58, 62, 68], [72, 74, 78]
];
const ZONE_LABELS_HM = ["A1","A2","A3","B1","B2","B3","C1","C2","C3","D1","D2","D3","D4","E1","E2"];
