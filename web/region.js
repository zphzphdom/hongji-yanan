/* 子页面共用：地区 + 接口 */
(function () {
  'use strict';
  var q = new URLSearchParams(location.search);
  var r = q.get('r') || (function () { try { return localStorage.getItem('hy_region') || 'yanan'; } catch (e) { return 'yanan'; } })();
  try { localStorage.setItem('hy_region', r); } catch (e) {}
  var VISITOR = (function () {
    try {
      var v = localStorage.getItem('hy_visitor');
      if (!v) { v = 'v' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8); localStorage.setItem('hy_visitor', v); }
      return v;
    } catch (e) { return 'anon'; }
  })();

  window.APP = {
    region: r,
    visitor: VISITOR,
    qs: q,
    get: function (path) {
      return fetch(path, { cache: 'no-store' }).then(function (x) { return x.json(); });
    },
    post: function (path, body) {
      var b = Object.assign({ visitor: VISITOR, region: r }, body || {});
      return fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Visitor': VISITOR },
        body: JSON.stringify(b)
      }).then(function (x) { return x.json(); });
    },
    esc: function (s) {
      return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
      });
    },
    $: function (s) { return document.querySelector(s); },
    setBrand: function (meta) {
      if (!meta) return;
      var b = document.querySelector('.subnav-brand');
      if (b) b.textContent = meta.brand || '红迹';
      document.title = (meta.brand || '红迹') + ' · ' + document.title.split('·').pop().trim();
      document.documentElement.style.setProperty('--region-accent', meta.accent || '#8C1F28');
    }
  };

  // 地区切换链接保留 ?r=
  [].forEach.call(document.querySelectorAll('.subnav a'), function (a) {
    var u = a.getAttribute('href') || '';
    if (u && u.indexOf('r=') < 0 && u.indexOf('http') !== 0) {
      a.setAttribute('href', u + (u.indexOf('?') >= 0 ? '&' : '?') + 'r=' + encodeURIComponent(r));
    }
  });

  fetch('api/regions', { cache: 'no-store' }).then(function (x) { return x.json(); })
    .then(function (d) {
      var meta = ((d && d.regions) || []).filter(function (x) { return x.id === r; })[0];
      window.APP.regionMeta = meta;
      window.APP.setBrand(meta);
    }).catch(function () {});
})();


/* 定位询问（由 region.js 统一初始化） */
(function () {
  if (window.__geoAskInit) return;
  window.__geoAskInit = true;

  var KEY = 'hy_geo_choice';
  var POS = 'hy_geo_pos';

  function loadPos() {
    try {
      var v = JSON.parse(localStorage.getItem(POS) || 'null');
      if (v && typeof v.lat === 'number') return v;
    } catch (e) {}
    return null;
  }

  function savePos(p) {
    try { localStorage.setItem(POS, JSON.stringify(p)); } catch (e) {}
  }

  function bar() {
    var el = document.createElement('div');
    el.className = 'geo-ask';
    el.innerHTML = '<span class="ga-text">允许定位，线路会按你当前位置排序，导航可一键从这里出发。</span>' +
      '<button class="ga-yes">允许</button><button class="ga-no">以后</button>';
    document.body.appendChild(el);
    el.querySelector('.ga-no').onclick = function () {
      try { localStorage.setItem(KEY, 'no'); } catch (e) {}
      el.classList.add('out');
      setTimeout(function () { el.remove(); }, 300);
    };
    el.querySelector('.ga-yes').onclick = function () {
      el.querySelector('.ga-text').textContent = '正在获取定位…';
      request(true, function () { el.classList.add('out'); setTimeout(function () { el.remove(); }, 300); });
    };
    return el;
  }

  function request(force, done) {
    if (!navigator.geolocation) { done && done(null); return; }
    navigator.geolocation.getCurrentPosition(function (p) {
      var v = { lat: p.coords.latitude, lng: p.coords.longitude, t: Date.now() };
      savePos(v);
      try { localStorage.setItem(KEY, 'yes'); } catch (e) {}
      window.APP_GEO = v;
      document.dispatchEvent(new CustomEvent('geo:ready', { detail: v }));
      done && done(v);
    }, function () {
      try { localStorage.setItem(KEY, 'no'); } catch (e) {}
      done && done(null);
    }, { timeout: 8000, maximumAge: 300000, enableHighAccuracy: false });
  }

  window.APP_GEO = loadPos();
  window.askGeo = request;

  // 已授权则静默刷新一次；未选择则弹出询问条
  var choice = null;
  try { choice = localStorage.getItem(KEY); } catch (e) {}
  if (choice === 'yes') {
    request(false, null);
  } else if (choice !== 'no') {
    setTimeout(function () { bar(); }, 800);
  }
})();
