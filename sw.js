// Robeng ELC Portal — Service Worker v2
const CACHE_NAME = 'robeng-v2';

self.addEventListener('install', e => { self.skipWaiting(); });

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))));
  self.clients.claim();
});

// Fetch — пропускаем всё внешнее (CDN, Firebase, Binotel и т.д.)
self.addEventListener('fetch', e => {
  const url = e.request.url;
  // Обрабатываем только запросы своего домена
  if (!url.startsWith(self.location.origin)) return;
  if (e.request.method !== 'GET') return;
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});

// Push уведомления
self.addEventListener('push', e => {
  let data = { title: 'Robeng ELC', body: 'Новое уведомление' };
  try { data = e.data.json(); } catch {}
  e.waitUntil(
    self.registration.showNotification(data.title || 'Robeng ELC', {
      body: data.body || '',
      tag: data.tag || 'robeng',
      vibrate: [200, 100, 200],
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.matchAll({ type:'window', includeUncontrolled:true }).then(list => {
    if(list.length) return list[0].focus();
    return clients.openWindow('/');
  }));
});
