// Cache-Name: bei Änderung hochzählen, um alten Cache zu invalidieren
const CACHE = 'grot2buy-v24';

// Dateien, die bereits bei der Installation gecacht werden (App-Shell)
const PRECACHE = [
  '/?sw=v12',
  '/static/style.css?v=24',
  '/static/app.js?v=24',
  '/static/logo.svg?v=20',
  '/static/manifest.json?v=20',
];

// Install-Event: App-Shell vorladen und sofort aktiv werden
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

// Aktivieren: alten Cache (anderer Name) löschen, Steuerung übernehmen
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch-Event: Network-First mit Cache-Fallback für statische Assets
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).then((response) => {
      // Erfolgreiche Antworten von CSS/JS/SVG/JSON in den Cache übernehmen
      if (response.ok && /\.(css|js|svg|json)$/.test(event.request.url)) {
        caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
      }
      return response;
    }).catch(() => caches.match(event.request)) // Bei Netzwerkfehler aus dem Cache ausliefern
  );
});

// Nachrichten vom Hauptthread empfangen
self.addEventListener('message', (event) => {
  // Service Worker sofort aktivieren (überspringt Warte-Phase)
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
    return;
  }
  // System-Benachrichtigung anzeigen
  if (event.data?.type === 'show-notification') {
    self.registration.showNotification(event.data.title, {
      body: event.data.body,
      icon: '/static/logo.svg?v=24',
      badge: '/static/logo.svg?v=24',
      vibrate: [200, 100, 200],
    });
  }
});

// Klick auf eine Benachrichtigung: Fenster fokussieren oder öffnen
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cl) => {
    if (cl.length > 0) {
      cl[0].focus();
    } else {
      clients.openWindow('/');
    }
  }));
});
