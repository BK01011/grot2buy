const CACHE = 'grot2buy-v15';

const PRECACHE = [
  '/?sw=v8',
  '/static/style.css?v=15',
  '/static/app.js?v=15',
  '/static/logo.svg?v=15',
  '/static/manifest.json?v=15',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).then((response) => {
      if (response.ok && /\.(css|js|svg|json)$/.test(event.request.url)) {
        caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
      }
      if (response.ok && event.request.url.includes('/api/')) {
        caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
      }
      return response;
    }).catch(() => caches.match(event.request))
  );
});

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
    return;
  }
  if (event.data?.type === 'show-notification') {
    self.registration.showNotification(event.data.title, {
      body: event.data.body,
      icon: '/static/logo.svg?v=15',
      badge: '/static/logo.svg?v=15',
      vibrate: [200, 100, 200],
    });
  }
});

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
