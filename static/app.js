/* Koperasi Sejahtera: shared navigation and form enhancement. */
(function () {
  'use strict';

  var state = { busy: false, request: 0 };
  var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function isInternal(url) {
    try {
      var parsed = new URL(url, window.location.href);
      return parsed.origin === window.location.origin && parsed.pathname.indexOf('/login') !== 0 && parsed.pathname.indexOf('/logout') !== 0;
    } catch (error) { return false; }
  }

  function setBusy(busy) {
    state.busy = busy;
    var main = document.getElementById('main-content');
    var bar = document.getElementById('navigation-progress');
    if (main) main.setAttribute('aria-busy', busy ? 'true' : 'false');
    if (bar) bar.classList.toggle('is-active', busy);
  }

  function closeSidebar() {
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    var button = document.getElementById('hamburger-btn');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
    if (button) button.setAttribute('aria-expanded', 'false');
  }

  function showError(message) {
    var main = document.getElementById('main-content');
    if (!main) return;
    var current = main.querySelector('[data-navigation-error]');
    if (current) current.remove();
    var alert = document.createElement('div');
    alert.className = 'flash flash-error navigation-error';
    alert.setAttribute('role', 'alert');
    alert.setAttribute('data-navigation-error', 'true');
    alert.innerHTML = '<strong>Halaman belum termuat.</strong> ' + message + ' <button type="button" class="btn btn-secondary btn-xs" data-retry-navigation>Coba lagi</button>';
    main.prepend(alert);
  }

  function replacePage(html, url, push) {
    var parsed = new DOMParser().parseFromString(html, 'text/html');
    var incoming = parsed.getElementById('main-content');
    var current = document.getElementById('main-content');
    if (!incoming || !current) throw new Error('Struktur halaman tidak lengkap');
    current.replaceChildren.apply(current, Array.prototype.slice.call(incoming.childNodes));
    var incomingTitle = parsed.getElementById('topbar-title');
    var currentTitle = document.getElementById('topbar-title');
    if (incomingTitle && currentTitle) currentTitle.innerHTML = incomingTitle.innerHTML;
    var title = parsed.querySelector('title');
    if (title) document.title = title.textContent;
    if (push) window.history.pushState({ ajax: true }, '', url);
    updateActiveNav(url);
    closeSidebar();
    window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' });
    bindContent();
  }

  function updateActiveNav(url) {
    var path = new URL(url, window.location.href).pathname.replace(/^\/+/, '');
    var section = path.split('/')[0] || 'dashboard';
    document.querySelectorAll('.sidebar .nav-item[data-nav-section]').forEach(function (item) {
      item.classList.toggle('active', item.getAttribute('data-nav-section') === section);
    });
  }

  async function loadPage(url, options) {
    options = options || {};
    if (state.busy) return;
    var requestId = ++state.request;
    setBusy(true);
    try {
      var response = await fetch(url, {
        method: options.method || 'GET',
        body: options.body,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'text/html' }
      });
      if (requestId !== state.request) return;
      if (response.redirected && !isInternal(response.url)) { window.location.assign(response.url); return; }
      if (!response.ok) throw new Error('Server merespons ' + response.status);
      replacePage(await response.text(), response.url || url, options.push !== false);
    } catch (error) {
      if (requestId === state.request) showError('Periksa koneksi lalu coba lagi.');
    } finally {
      if (requestId === state.request) setBusy(false);
    }
  }

  function bindContent() {
    document.querySelectorAll('a[href]').forEach(function (link) {
      if (link.dataset.ajaxBound || link.target === '_blank' || link.hasAttribute('download')) return;
      if (!isInternal(link.href)) return;
      link.dataset.ajaxBound = 'true';
      link.addEventListener('click', function (event) {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        loadPage(link.href, { push: true });
      });
    });
    document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(function (form) {
      if (form.dataset.ajaxBound || !isInternal(form.action || window.location.href)) return;
      form.dataset.ajaxBound = 'true';
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        loadPage(form.action || window.location.href, { method: 'POST', body: new FormData(form), push: true });
      });
    });
  }

  window.toggleSidebar = function () {
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    var button = document.getElementById('hamburger-btn');
    if (!sidebar || !overlay || !button) return;
    var open = sidebar.classList.toggle('open');
    overlay.classList.toggle('open', open);
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
  };

  window.addEventListener('popstate', function () { loadPage(window.location.href, { push: false }); });
  document.addEventListener('click', function (event) {
    var retry = event.target.closest('[data-retry-navigation]');
    if (retry) loadPage(window.location.href, { push: false });
    var nav = event.target.closest('.sidebar .nav-item');
    if (nav && window.innerWidth < 1024) closeSidebar();
  });
  document.addEventListener('DOMContentLoaded', function () { bindContent(); updateActiveNav(window.location.href); });
})();
