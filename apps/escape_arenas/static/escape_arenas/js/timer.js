/* Visual exclusivamente: no envía tiempo ni decide el estado de la sesión. */
(() => {
  const timer = document.getElementById('escape-timer');
  if (!timer) return;
  const initial = Number(timer.dataset.seconds);
  if (!Number.isFinite(initial)) return;
  const began = performance.now();
  let refreshed = false;
  function tick() {
    const left = Math.max(0, Math.ceil(initial - (performance.now() - began) / 1000));
    timer.textContent = `${String(Math.floor(left / 60)).padStart(2, '0')}:${String(left % 60).padStart(2, '0')}`;
    timer.classList.toggle('urgent', left <= 60);
    if (left === 0 && !refreshed) {
      refreshed = true;
      window.location.replace(timer.dataset.refreshUrl);
    }
  }
  tick();
  setInterval(tick, 250);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) window.location.reload();
  });
})();
