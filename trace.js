// Homepage trace: every article as a span on its topic lane, in publication order,
// span length = reading time. Data comes from <script id="trace-data">, which
// tools/build_home.py regenerates from articles/index.html. No dependencies.
(function () {
  var fig = document.querySelector('.trace');
  var src = document.getElementById('trace-data');
  if (!fig || !src) return;
  var DATA = JSON.parse(src.textContent);
  if (!DATA.length) return;

  var grid = fig.querySelector('.trace-grid');
  var labels = Array.prototype.slice.call(grid.querySelectorAll('.lane-label'));
  var lanes = labels.map(function (a) { return a.getAttribute('data-lane'); });
  var laneName = {};
  labels.forEach(function (a) { laneName[a.getAttribute('data-lane')] = a.textContent; });
  var unit = fig.getAttribute('data-unit') || 'min';
  var mobile = window.matchMedia('(max-width:640px)');
  var LANE_H = 26, GAP = 6, LABEL_H = 20;

  var total = 0;
  DATA.forEach(function (a) { a.start = total; total += a.min; });

  var tracks = document.createElement('div');
  tracks.className = 'tracks';
  tracks.tabIndex = 0;
  tracks.setAttribute('role', 'slider');
  tracks.setAttribute('aria-label', fig.getAttribute('data-label') || '');
  tracks.setAttribute('aria-valuemin', '1');
  tracks.setAttribute('aria-valuemax', String(DATA.length));

  var trackEls = {};
  lanes.forEach(function (l) {
    var t = document.createElement('div');
    t.className = 'track';
    trackEls[l] = t;
    tracks.appendChild(t);
  });

  var spans = DATA.map(function (a) {
    var s = document.createElement('div');
    s.className = 'span lane-' + a.lane;
    s.style.left = (a.start / total * 100) + '%';
    s.style.width = (a.min / total * 100) + '%';
    (trackEls[a.lane] || trackEls[lanes[0]]).appendChild(s);
    return s;
  });

  var head = document.createElement('div');
  head.className = 'playhead';
  tracks.appendChild(head);
  grid.appendChild(tracks);

  var axis = document.createElement('div');
  axis.className = 'axis';
  axis.setAttribute('aria-hidden', 'true');
  grid.appendChild(axis);
  var ticks = [], maxYear = 0;
  DATA.forEach(function (a) { if (a.year > maxYear) { maxYear = a.year; ticks.push(a); } });

  var readout = document.createElement('div');
  readout.className = 'readout';
  readout.setAttribute('aria-live', 'polite');
  readout.innerHTML = '<div class="what"></div><a></a><div class="when"></div>';
  grid.appendChild(readout);

  // caption: "{n}" and "{h}" with plural forms from data-n / data-h ("one|few|many" or "one|other")
  var cap = fig.querySelector('figcaption');
  if (cap) {
    grid.appendChild(cap);
    var lang = document.documentElement.lang || 'en';
    var rules = window.Intl && Intl.PluralRules ? new Intl.PluralRules(lang) : null;
    var plural = function (n, forms) {
      forms = (forms || '').split('|');
      var cat = rules ? rules.select(n) : (n === 1 ? 'one' : 'other');
      var idx = forms.length === 3 ? { one: 0, few: 1, many: 2, other: 2 }[cat] : (cat === 'one' ? 0 : 1);
      return n + ' ' + (forms[idx] || forms[forms.length - 1] || '');
    };
    var hours = Math.round(total / 60);
    cap.textContent = cap.getAttribute('data-tpl')
      .replace('{n}', plural(DATA.length, cap.getAttribute('data-n')))
      .replace('{h}', plural(hours, cap.getAttribute('data-h')));
  }

  function layout() {
    var m = mobile.matches;
    lanes.forEach(function (l, i) {
      trackEls[l].style.top = (m ? i * (LANE_H + LABEL_H) + LABEL_H : i * (LANE_H + GAP)) + 'px';
      labels[i].style.gridRow = m ? 'auto' : String(i + 1);
    });
    tracks.style.height = (m ? lanes.length * (LANE_H + LABEL_H) : lanes.length * (LANE_H + GAP) - GAP) + 'px';
    // year ticks, skipping labels that would collide
    axis.innerHTML = '';
    var w = tracks.clientWidth, last = -1e9;
    ticks.forEach(function (a) {
      var x = a.start / total * w;
      if (x - last < 40) return;
      last = x;
      var s = document.createElement('span');
      s.style.left = x + 'px';
      s.textContent = a.year;
      axis.appendChild(s);
    });
  }

  var cur = -1;
  function select(i) {
    i = Math.max(0, Math.min(DATA.length - 1, i));
    if (i === cur) return;
    if (cur >= 0) spans[cur].classList.remove('on');
    cur = i;
    var a = DATA[i];
    spans[i].classList.add('on');
    head.style.left = ((a.start + a.min / 2) / total * 100) + '%';
    readout.className = 'readout lane-' + a.lane;
    readout.children[0].textContent = laneName[a.lane] || '';
    readout.children[1].textContent = a.title;
    readout.children[1].href = a.href;
    readout.children[2].textContent = a.date + ', ' + a.min + ' ' + unit;
    tracks.setAttribute('aria-valuenow', String(i + 1));
    tracks.setAttribute('aria-valuetext', a.title);
  }

  function indexAt(clientX) {
    var r = tracks.getBoundingClientRect();
    var m = (clientX - r.left) / r.width * total;
    var lo = 0, hi = DATA.length - 1;
    while (lo < hi) {
      var mid = (lo + hi + 1) >> 1;
      if (DATA[mid].start <= m) lo = mid; else hi = mid - 1;
    }
    return lo;
  }

  tracks.addEventListener('pointermove', function (e) { select(indexAt(e.clientX)); });
  tracks.addEventListener('pointerdown', function (e) { select(indexAt(e.clientX)); });
  // mouse click opens the article; on touch the tap only selects, the title link opens it
  tracks.addEventListener('click', function (e) {
    if (e.pointerType === 'mouse') location.href = DATA[cur].href;
  });
  tracks.addEventListener('keydown', function (e) {
    var step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (step) { select(cur + step); e.preventDefault(); }
    else if (e.key === 'Home') { select(0); e.preventDefault(); }
    else if (e.key === 'End') { select(DATA.length - 1); e.preventDefault(); }
    else if (e.key === 'Enter') { location.href = DATA[cur].href; }
  });

  layout();
  if (mobile.addEventListener) mobile.addEventListener('change', layout);
  window.addEventListener('resize', layout);
  select(DATA.length - 1);
  fig.classList.add('sweep');
})();
