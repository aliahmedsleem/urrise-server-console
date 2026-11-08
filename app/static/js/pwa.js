(() => {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('/sw.js').catch(console.warn);
  const button = document.getElementById('enable-push');
  if (!button) return;
  const status = document.getElementById('push-status');
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  const decode = key => {
    const padding = '='.repeat((4 - key.length % 4) % 4);
    const raw = atob((key + padding).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, ch => ch.charCodeAt(0));
  };
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      if (!window.isSecureContext || !('PushManager' in window)) throw Error('HTTPS and Push support are required');
      if (Notification.permission === 'denied') throw Error('Notifications blocked in browser settings');
      const response = await fetch('/api/push/key', {credentials:'same-origin'});
      if (!response.ok) throw Error('Push is not configured on the server');
      const {public_key} = await response.json();
      const registration = await navigator.serviceWorker.ready;
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') throw Error('Notification permission not granted');
      const subscription = await registration.pushManager.subscribe({userVisibleOnly:true, applicationServerKey:decode(public_key)});
      const saved = await fetch('/api/push/subscribe', {
        method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json', 'X-CSRFToken':csrf()},
        body:JSON.stringify(subscription.toJSON())
      });
      if (!saved.ok) throw Error('Subscription could not be saved');
      status.textContent = 'Push notifications enabled';
    } catch (err) { status.textContent = err.message; }
    finally { button.disabled = false; }
  });
})();
