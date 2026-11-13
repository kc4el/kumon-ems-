/* Notification events only invalidate the existing, authenticated inbox. */
(() => {
  if (!window.EventSource || window.__notificationEventsSetup) return;
  window.__notificationEventsSetup = true;
  let source;
  const connect = () => {
    if (source) return;
    source = new EventSource('/api/notifications/events/');
    source.addEventListener('changed', () => window.dispatchEvent(new Event('notifications:changed')));
  };
  connect();
  window.addEventListener('pagehide', () => { if (source) source.close(); source = null; });
  window.addEventListener('pageshow', () => connect());
})();
