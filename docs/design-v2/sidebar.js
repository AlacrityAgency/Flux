'use strict';
(() => {
  const app = document.getElementById('app');
  const side = document.getElementById('side');
  const grip = document.getElementById('side-resize');
  const collapse = document.getElementById('collapse');
  const menu = document.getElementById('menu');
  const backdrop = document.getElementById('drawer-backdrop');
  if (!app || !side || !grip || !collapse || !menu) return;

  const min = 232, max = 440, narrow = matchMedia('(max-width:760px)');
  const clamp = n => Math.max(min, Math.min(max, n));
  let width = 280;
  try {
    const saved = Number(localStorage.getItem('flux-design-v2-sidebar-width'));
    if (Number.isFinite(saved) && saved >= min && saved <= max) width = saved;
    if (localStorage.getItem('flux-design-v2-sidebar-collapsed') === 'true') app.classList.add('collapsed');
  } catch (_) {}

  function setWidth(next, persist = false) {
    width = clamp(next);
    app.style.setProperty('--sidebar-width', `${width}px`);
    grip.setAttribute('aria-valuenow', String(width));
    if (persist) try { localStorage.setItem('flux-design-v2-sidebar-width', String(width)); } catch (_) {}
  }
  function setCollapsed(value, persist = false) {
    app.classList.toggle('collapsed', value);
    app.classList.toggle('pinned', !value);
    collapse.setAttribute('aria-expanded', String(!value));
    collapse.setAttribute('aria-label', value ? 'باز کردن نوار کناری' : 'جمع کردن نوار کناری');
    if (persist) try { localStorage.setItem('flux-design-v2-sidebar-collapsed', String(value)); } catch (_) {}
  }
  setWidth(width);
  setCollapsed(app.classList.contains('collapsed'));

  collapse.addEventListener('click', () => {
    if (narrow.matches) {
      app.classList.toggle('drawer');
      if (backdrop) backdrop.hidden = !app.classList.contains('drawer');
      return;
    }
    setCollapsed(!app.classList.contains('collapsed'), true);
  });
  menu.addEventListener('click', () => {
    app.classList.toggle('drawer');
    if (backdrop) backdrop.hidden = !app.classList.contains('drawer');
  });
  backdrop?.addEventListener('click', () => {
    app.classList.remove('drawer');
    backdrop.hidden = true;
  });
  side.addEventListener('click', event => {
    if (event.target.closest('a') && narrow.matches) {
      app.classList.remove('drawer');
      if (backdrop) backdrop.hidden = true;
    }
  });

  let startX = 0, startWidth = width, pointer = null;
  grip.addEventListener('pointerdown', event => {
    if (narrow.matches) return;
    event.preventDefault();
    pointer = event.pointerId;
    startX = event.clientX;
    startWidth = width;
    grip.setPointerCapture(pointer);
    setCollapsed(false, true);
    document.body.classList.add('resizing-sidebar');
  });
  grip.addEventListener('pointermove', event => {
    if (pointer !== event.pointerId) return;
    setWidth(startWidth + startX - event.clientX);
  });
  const finish = event => {
    if (pointer !== event.pointerId) return;
    pointer = null;
    setWidth(width, true);
    document.body.classList.remove('resizing-sidebar');
  };
  grip.addEventListener('pointerup', finish);
  grip.addEventListener('pointercancel', finish);
  grip.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? min : event.key === 'End' ? max : width + (event.key === 'ArrowLeft' ? 16 : -16);
    setWidth(next, true);
    setCollapsed(false, true);
  });
  narrow.addEventListener('change', () => {
    app.classList.remove('drawer');
    if (backdrop) backdrop.hidden = true;
  });
})();
