/* Never cache authenticated dashboard, API responses, or secrets. */
self.addEventListener('install', event => { self.skipWaiting(); });
self.addEventListener('activate', event => { event.waitUntil(self.clients.claim()); });
self.addEventListener('push', event => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (_) {}
  const title = String(data.title || 'URRISE Server Console');
  const body = String(data.body || 'Server alert');
  event.waitUntil(self.registration.showNotification(title, {
    body, tag: 'urrise-alert-' + String(data.event_id || Date.now()),
    icon: '/static/icons/urrise.svg', data: {url: '/'}
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow('/'));
});
