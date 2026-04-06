// Robeng ELC — Service Worker v3 (Push Notifications)
const VAPID_PUBLIC_KEY = 'BHjw01VsaDwADSf7LU1rxSB5o2-8J5wjm_SYNrh-C0C-akmFjdrCGV_scj6n0ZTqt8Bdyux4UWNHXkF61JnJErM';

self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => { self.clients.claim(); });

// Не перехватываем fetch — только push
self.addEventListener('fetch', () => {});

// Push уведомление
self.addEventListener('push', e => {
  let payload = { title: 'Robeng ELC', body: 'Новое уведомление', icon: '/testing-robeng/icon-192.png', tag: 'robeng', url: '/' };
  try {
    const data = e.data?.json();
    if(data) Object.assign(payload, data);
  } catch {}

  e.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: payload.icon || '/testing-robeng/icon-192.png',
      badge: '/testing-robeng/icon-192.png',
      tag: payload.tag || 'robeng-' + Date.now(),
      data: { url: payload.url || '/' },
      vibrate: [200, 100, 200],
      requireInteraction: payload.requireInteraction || false,
    })
  );
});

// Клик по уведомлению
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data?.url || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url.includes('pllato.github.io') && 'focus' in c) return c.focus();
      }
      return clients.openWindow('https://pllato.github.io/testing-robeng/' + url);
    })
  );
});
