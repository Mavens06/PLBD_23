/*
  Service worker Agri-Botics (PWA).
  - Précache l'« app shell » (HTML, CSS, JS, icônes) → ouverture rapide + écran
    de base disponible même réseau faible.
  - Stratégie : cache-first sur le MÊME origine (frontend statique), avec mise à
    jour en arrière-plan. Les requêtes vers le BACKEND (autre origine, :8000) et
    toutes les requêtes non-GET (POST chat/mission…) ne sont JAMAIS interceptées
    → les données live passent toujours par le réseau.

  NB : un service worker ne s'enregistre que dans un CONTEXTE SÉCURISÉ
  (HTTPS, ou localhost). En HTTP simple sur une IP de réseau local, l'enregistrement
  échoue silencieusement et l'app fonctionne en page web normale (et reste
  « Ajoutable à l'écran d'accueil » sur iOS via les meta Apple).
*/
const CACHE = "agribotics-shell-v2";
const SHELL = [
  "./",
  "./agribotics_v5.html",
  "./index.html",
  "./manifest.webmanifest",
  "./css/style.css",
  "./js/data_model.js",
  "./js/state.js",
  "./js/api.js",
  "./js/map.js",
  "./js/charts.js",
  "./js/i18n.js",
  "./js/chatbot.js",
  "./js/app.js",
  "./js/runtime_real.js",
  "./assets/robot.png",
  "./assets/parcelle.jpg",
  "./assets/icons/icon-192.png",
  "./assets/icons/icon-512.png",
  "./assets/icons/maskable-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      // addAll échouerait si un seul fichier manque : on tolère les absents.
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;                 // POST (chat, mission…) → réseau direct
  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (url.origin !== self.location.origin) return;  // backend :8000 / polices → réseau direct
  // App shell : cache d'abord, repli réseau, et rafraîchissement en arrière-plan.
  e.respondWith(
    caches.match(req).then((cached) => {
      const fromNet = fetch(req).then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      }).catch(() => cached);
      return cached || fromNet;
    })
  );
});
