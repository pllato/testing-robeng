// Robeng ELC — Service Worker v5

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('push', e => {
  let payload = { title: 'Robeng ELC', body: 'Новое уведомление', tag: 'robeng' };
  try { if (e.data) Object.assign(payload, e.data.json()); } catch {}

  e.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      tag: payload.tag || 'robeng',
      data: { url: payload.url || '/' },
      vibrate: [200, 100, 200],
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const target = 'https://pllato.github.io/testing-robeng/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url.startsWith(target) && 'focus' in c) return c.focus();
      }
      return clients.openWindow(target);
    })
  );
});
