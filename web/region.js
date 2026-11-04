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
