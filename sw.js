// Robeng ELC Portal — Service Worker
const CACHE_NAME = 'robeng-v1';
const STATIC_ASSETS = [
  './',
  './index.html',
  './jssip.min.js',
  'https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600;700&family=Manrope:wght@400;500;600&display=swap',
];

// Install — кэшируем статику
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      cache.addAll(STATIC_ASSETS).catch(() => {})
    )
  );
  self.skipWaiting();
});

// Activate — чистим старые кэши
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch — network first, fallback to cache
self.addEventListener('fetch', e => {
  // Не кэшируем Firebase/API запросы
  if (e.request.url.includes('firebaseio.com') ||
      e.request.url.includes('googleapis.com/identitytoolkit') ||
      e.request.url.includes('workers.dev') ||
      e.request.method !== 'GET') {
    return;
  }
  e.respondWith(
    fetch(e.request)
      .then(response => {
        // Кэшируем успешные ответы
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(e.request))
  );
});

// Push уведомления
self.addEventListener('push', e => {
  let data = { title: 'Robeng ELC', body: 'Новое уведомление' };
  try { data = e.data.json(); } catch {}

  e.waitUntil(
    self.registration.showNotification(data.title || 'Robeng ELC', {
      body: data.body || '',
      icon: data.icon || './favicon.ico',
      badge: data.badge || './favicon.ico',
      tag: data.tag || 'robeng',
      data: data.url || '/',
      vibrate: [200, 100, 200],
      requireInteraction: data.urgent || false,
    })
  );
});

// Клик по уведомлению — открываем/фокусируем вкладку
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url.includes('pllato.github.io') || c.url.includes('localhost')) {
          c.focus();
          return;
        }
      }
      return clients.openWindow(url);
    })
  );
});
