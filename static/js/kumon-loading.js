window.kumonLoadingNavigate = function (destination, fallback) {
  const defaultPath = fallback || '/employee/';
  let target;
  try {
    target = new URL(typeof destination === 'string' ? destination : defaultPath, window.location.origin);
  } catch (_) {
    target = new URL(defaultPath, window.location.origin);
  }
  if (target.origin !== window.location.origin) target = new URL(defaultPath, window.location.origin);

  const screen = document.getElementById('kumonLoadingScreen');
  if (!screen) {
    window.location.assign(target.href);
    return;
  }

  screen.hidden = false;
  screen.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  const delay = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 80 : 700;
  window.setTimeout(() => window.location.assign(target.href), delay);
};
