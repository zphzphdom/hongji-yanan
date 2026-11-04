/* 导航子页：地图上展示该地区所有点位，可点选导航 */
(function () {
  'use strict';
  var A = window.APP;
  var map = null, items = [], pos = null;

  A.post('/api/progress', {}).then(function (j) {
    items = (j.sites || []).filter(function (s) { return !s.region || s.region === A.region; });
    renderList();
    loadGeos();
  }).catch(function () {
    document.getElementById('goList').innerHTML = '<div class="empty">加载失败</div>';
  });

  function renderList() {
    var box = document.getElementById('goList');
    box.innerHTML = items.map(function (s) {
      return '<div class="gocard" data-id="' + A.esc(s.id) + '">' +
        '<b>' + A.esc(s.name) + '</b>' +
        '<span class="gc-meta">' + A.esc(s.level || '') + '</span>' +
        '<div class="gc-acts"><a class="mp-btn primary" href="#" target="_blank" rel="noopener">导航</a>' +
        '<a class="mp-btn" href="#" target="_blank" rel="noopener">地图</a></div></div>';
    }).join('');
    [].forEach.call(box.querySelectorAll('.gocard'), function (card) {
      card.onclick = function () {
        var g = items.filter(function (x) { return x.id === card.dataset.id; })[0];
        if (g && g.geo) focus(g.geo);
      };
    });
  }

  function loadGeos() {
    var i = 0;
    function next() {
      if (i >= items.length) { draw(); return; }
      var it = items[i];
      A.get('/api/geo?site=' + encodeURIComponent(it.id)).then(function (g) {
        if (g && g.ok) it.geo = g;
      }).catch(function () {}).then(function () { i += 1; next(); });
    }
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(function (p) {
        pos = { lat: p.coords.latitude, lng: p.coords.longitude };
        next();
      }, function () { next(); }, { timeout: 6000, maximumAge: 300000 });
    } else next();
  }

  function whenVisible(el, cb, tries) {
    tries = tries == null ? 40 : tries;
    (function check() {
      var r = el.getBoundingClientRect();
      if (r.width > 20 && r.height > 20) { cb(); return; }
      if (tries-- <= 0) { cb(); return; }
      setTimeout(check, 150);
    })();
  }

  function draw() {
    if (typeof L === 'undefined') {
      document.getElementById('goMap').innerHTML = '<div class="map-fallback">地图组件未加载</div>';
      return;
    }
    var pts = items.filter(function (x) { return x.geo; });
    if (!pts.length) return;
    var host = document.getElementById('goMap');
    if (host) whenVisible(host, function () { buildGoMap(pts); });
  }

  function buildGoMap(pts) {
    map = L.map('goMap', { zoomControl: true, attributionControl: false });
    var std = L.tileLayer('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
      { subdomains: '1234', maxZoom: 18 });
    var sat = L.tileLayer('https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
      { subdomains: '1234', maxZoom: 18 });
    std.addTo(map);
    L.control.layers({ '标准': std, '卫星': sat }, null, { position: 'topright', collapsed: true }).addTo(map);

    pts.forEach(function (it, i) {
      var g = it.geo;
      var m = L.marker([g.lat, g.lng], {
        icon: L.divIcon({ className: 'mp-pin', html: '<span>' + (i + 1) + '</span>',
                          iconSize: [28, 28], iconAnchor: [14, 14] })
      }).addTo(map).bindPopup('<div class="mp"><div class="mp-t">' + A.esc(it.name) + '</div>' +
        '<div class="mp-acts"><a class="mp-btn primary" target="_blank" rel="noopener" href="' +
        A.esc(g.amap.navFrom || g.amap.nav) + '">开始导航</a></div></div>', { maxWidth: 220 })
        .bindTooltip(it.name, { permanent: false });
      it._marker = m;
    });
    if (pos) {
      L.marker([pos.lat, pos.lng], {
        icon: L.divIcon({ className: 'mp-me', html: '<span>我</span>', iconSize: [26, 26], iconAnchor: [13, 13] })
      }).addTo(map).bindPopup('我的位置');
    }
    var all = pts.map(function (x) { return [x.geo.lat, x.geo.lng]; });
    if (pos) all.push([pos.lat, pos.lng]);
    map.fitBounds(all, { padding: [30, 30] });
    [60, 200, 500, 900].forEach(function (ms) {
      setTimeout(function () { try { map.invalidateSize(); } catch (e) {} }, ms);
    });
  }

  function focus(g) {
    if (!map) return;
    map.setView([g.lat, g.lng], 15);
  }
})();
