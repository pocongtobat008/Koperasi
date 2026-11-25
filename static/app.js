/* Koperasi Sejahtera: shared navigation and form enhancement. */
(function () {
  'use strict';

  var state = { busy: false, request: 0, timer: null, controller: null };
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
    if (button) { button.setAttribute('aria-expanded', 'false'); button.setAttribute('aria-label', 'Buka menu'); }
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
    enhanceSelects();
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
    if (state.controller) state.controller.abort();
    if (state.timer) window.clearTimeout(state.timer);
    state.controller = window.AbortController ? new AbortController() : null;
    setBusy(true);
    state.timer = window.setTimeout(function () {
      if (requestId === state.request) {
        if (state.controller) state.controller.abort();
        setBusy(false);
        showError('Waktu muat habis. Periksa koneksi lalu coba lagi.');
      }
    }, 10000);
    try {
      var response = await fetch(url, {
        method: options.method || 'GET',
        body: options.body,
        credentials: 'same-origin',
        signal: state.controller ? state.controller.signal : undefined,
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'text/html' }
      });
      if (requestId !== state.request) return;
      if (response.redirected && !isInternal(response.url)) { window.location.assign(response.url); return; }
      if (!response.ok) throw new Error('Server merespons ' + response.status);
      replacePage(await response.text(), response.url || url, options.push !== false);
    } catch (error) {
      if (requestId === state.request) showError('Periksa koneksi lalu coba lagi.');
    } finally {
      if (requestId === state.request) {
        if (state.timer) window.clearTimeout(state.timer);
        state.timer = null;
        state.controller = null;
        setBusy(false);
      }
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

  function cancelNavigation() {
    state.request += 1;
    if (state.controller) state.controller.abort();
    state.controller = null;
    if (state.timer) window.clearTimeout(state.timer);
    state.timer = null;
    setBusy(false);
  }

  window.toggleSidebar = function () {
    cancelNavigation();
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    var button = document.getElementById('hamburger-btn');
    if (!sidebar || !overlay || !button) return false;
    var open = !sidebar.classList.contains('open');
    sidebar.classList.toggle('open', open);
    overlay.classList.toggle('open', open);
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
    button.setAttribute('aria-label', open ? 'Tutup menu' : 'Buka menu');
    return false;
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


// Searchable dropdowns without external dependencies.
function enhanceSelects() { document.querySelectorAll('select:not([data-search-ready])').forEach(function(select) { select.setAttribute('data-search-ready','true'); if (select.options.length < 3) return; var wrap=document.createElement('div'); wrap.className='select-search-wrap'; select.parentNode.insertBefore(wrap,select); wrap.appendChild(select); var input=document.createElement('input'); input.className='field select-search'; input.placeholder='Cari pilihan...'; input.setAttribute('aria-label','Cari pilihan'); wrap.insertBefore(input,select); input.addEventListener('input',function(){ var q=input.value.toLowerCase(); Array.from(select.options).forEach(function(o){o.hidden=q && o.text.toLowerCase().indexOf(q)<0;}); }); }); }
document.addEventListener('DOMContentLoaded', function () { enhanceSelects(); });
