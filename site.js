// Small progressive enhancements shared by every page. No dependencies.
// Each feature checks for its own markup and does nothing when it isn't there.
(function () {
  var lang = (document.documentElement.lang || 'ru').slice(0, 2);
  var T = {
    ru: { toc: 'Содержание', copy: 'Копировать', copied: 'Скопировано', search: 'Поиск по статьям',
          found: function (n, all) { return 'Найдено: ' + n + ' из ' + all; }, none: 'Ничего не нашлось. Попробуйте другое слово.',
          dark: 'Тёмная тема', light: 'Светлая тема' },
    en: { toc: 'Contents', copy: 'Copy', copied: 'Copied', search: 'Search articles',
          found: function (n, all) { return n + ' of ' + all; }, none: 'Nothing found. Try another word.',
          dark: 'Dark theme', light: 'Light theme' },
    it: { toc: 'Indice', copy: 'Copia', copied: 'Copiato', search: 'Cerca negli articoli',
          found: function (n, all) { return n + ' su ' + all; }, none: 'Nessun risultato. Prova con un’altra parola.',
          dark: 'Tema scuro', light: 'Tema chiaro' }
  }[lang] || null;
  if (!T) T = { toc: 'Contents', copy: 'Copy', copied: 'Copied', search: 'Search', found: function (n, a) { return n + '/' + a; }, none: 'Nothing found.', dark: 'Dark theme', light: 'Light theme' };

  // Comments (giscus, GitHub Discussions) and privacy-friendly stats (GoatCounter).
  // Both stay off until their ids are filled in.
  var GISCUS = { repo: 'dalerank/dalerank.github.io', repoId: 'R_kgDONxj8cg', category: 'Comments', categoryId: '' };
  var GOATCOUNTER = ''; // e.g. 'dalerank' for https://dalerank.goatcounter.com

  var root = document.documentElement;
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} }
  };

  // ---------- theme toggle ----------
  var systemDark = window.matchMedia('(prefers-color-scheme: dark)');
  function effectiveTheme() {
    return root.getAttribute('data-theme') || (systemDark.matches ? 'dark' : 'light');
  }
  var actions = document.querySelector('.topbar .actions');
  if (actions) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'theme-toggle';
    btn.innerHTML = '<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="10" cy="10" r="7.25" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M10 2.75a7.25 7.25 0 0 1 0 14.5z" fill="currentColor"/></svg>';
    var label = function () { btn.setAttribute('aria-label', effectiveTheme() === 'dark' ? T.light : T.dark); btn.title = btn.getAttribute('aria-label'); };
    label();
    btn.addEventListener('click', function () {
      var next = effectiveTheme() === 'dark' ? 'light' : 'dark';
      // choosing what the system already prefers means "follow the system" again
      if ((next === 'dark') === systemDark.matches) { root.removeAttribute('data-theme'); store.set('theme', null); }
      else { root.setAttribute('data-theme', next); store.set('theme', next); }
      label();
      syncGiscusTheme();
    });
    systemDark.addEventListener && systemDark.addEventListener('change', function () { label(); syncGiscusTheme(); });
    actions.insertBefore(btn, actions.firstChild);
  }

  var prose = document.querySelector('main.article .prose');

  // ---------- table of contents for long articles ----------
  if (prose && document.querySelector('.article-head')) {
    var heads = Array.prototype.filter.call(prose.querySelectorAll('h2'), function (h) { return !h.closest('.related'); });
    var hasToc = Array.prototype.some.call(prose.querySelectorAll('details'), function (d) { return d.querySelector('a[href^="#"]'); });
    if (heads.length >= 4 && !hasToc) {
      var toc = document.createElement('details');
      toc.className = 'toc';
      var ol = document.createElement('ol');
      heads.forEach(function (h, i) {
        if (!h.id) h.id = 'section-' + (i + 1);
        var li = document.createElement('li');
        var a = document.createElement('a');
        a.href = '#' + h.id;
        a.textContent = h.textContent;
        li.appendChild(a);
        ol.appendChild(li);
      });
      toc.innerHTML = '<summary>' + T.toc + '</summary>';
      toc.appendChild(ol);
      prose.insertBefore(toc, prose.firstChild);
      // ids were just assigned, so a shared #section-N link has nothing to scroll to yet
      var target = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target) {
        var go = function () { target.scrollIntoView({ behavior: 'instant', block: 'start' }); };
        go();
        window.addEventListener('load', go); // again once images above it have their size
      }
    }
  }

  // ---------- copy button on code blocks ----------
  if (prose && navigator.clipboard) {
    Array.prototype.forEach.call(prose.querySelectorAll('pre'), function (pre) {
      var wrap = document.createElement('div');
      wrap.className = 'codewrap';
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'copy';
      b.textContent = T.copy;
      b.addEventListener('click', function () {
        navigator.clipboard.writeText(pre.innerText.replace(/\n$/, '')).then(function () {
          b.textContent = T.copied;
          setTimeout(function () { b.textContent = T.copy; }, 1600);
        });
      });
      wrap.appendChild(b);
    });
  }

  // ---------- search on article lists ----------
  var list = document.querySelector('ul.artlist');
  if (list && list.children.length > 8) {
    var items = Array.prototype.slice.call(list.children);
    var norm = function (s) { return s.toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' '); };
    var texts = items.map(function (li) { return norm(li.textContent); });
    var box = document.createElement('div');
    box.className = 'search';
    box.innerHTML = '<input type="search" autocomplete="off" spellcheck="false"><p class="search-status" aria-live="polite"></p>';
    var input = box.firstChild, status = box.lastChild;
    input.placeholder = T.search;
    input.setAttribute('aria-label', T.search);
    list.parentNode.insertBefore(box, list);
    var run = function () {
      var words = norm(input.value).trim().split(' ').filter(Boolean);
      var shown = 0;
      items.forEach(function (li, i) {
        var ok = words.every(function (w) { return texts[i].indexOf(w) !== -1; });
        li.hidden = !ok;
        if (ok) shown++;
      });
      status.textContent = !words.length ? '' : shown ? T.found(shown, items.length) : T.none;
      var url = new URL(location.href);
      if (words.length) url.searchParams.set('q', input.value); else url.searchParams.delete('q');
      history.replaceState(null, '', url);
    };
    input.addEventListener('input', run);
    var q = new URLSearchParams(location.search).get('q');
    if (q) { input.value = q; run(); }
  }

  // ---------- comments ----------
  function giscusTheme() { return effectiveTheme() === 'dark' ? 'dark_dimmed' : 'light'; }
  function syncGiscusTheme() {
    var f = document.querySelector('iframe.giscus-frame');
    if (f) f.contentWindow.postMessage({ giscus: { setConfig: { theme: giscusTheme() } } }, 'https://giscus.app');
  }
  if (prose && GISCUS.categoryId && document.querySelector('.article-head')) {
    var c = document.createElement('section');
    c.className = 'comments';
    var s = document.createElement('script');
    s.src = 'https://giscus.app/client.js';
    var cfg = {
      'data-repo': GISCUS.repo, 'data-repo-id': GISCUS.repoId,
      'data-category': GISCUS.category, 'data-category-id': GISCUS.categoryId,
      'data-mapping': 'pathname', 'data-strict': '1', 'data-reactions-enabled': '1',
      'data-input-position': 'top', 'data-theme': giscusTheme(), 'data-lang': lang, 'data-loading': 'lazy'
    };
    for (var k in cfg) s.setAttribute(k, cfg[k]);
    s.crossOrigin = 'anonymous';
    s.async = true;
    c.appendChild(s);
    prose.parentNode.insertBefore(c, prose.nextSibling);
  }

  // ---------- stats ----------
  if (GOATCOUNTER && location.protocol === 'https:') {
    var g = document.createElement('script');
    g.async = true;
    g.src = 'https://gc.zgo.at/count.js';
    g.setAttribute('data-goatcounter', 'https://' + GOATCOUNTER + '.goatcounter.com/count');
    document.head.appendChild(g);
  }
})();
