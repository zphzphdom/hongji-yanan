/* 单点位子页：讲解 + 真实地图 + 任务 + 导航 */
(function () {
  'use strict';
  var A = window.APP;
  var sid = A.qs.get('site') || A.qs.get('s') || '';
  var $ = A.$;
  var map = null, geo = null, task = null, pos = null;

  function load() {
    if (!sid) { $('#siteBody').innerHTML = '<div class="empty">缺少点位参数</div>'; return; }
    A.post('/api/site', { site: sid }).then(function (j) {
      if (!j || !j.ok) { $('#siteBody').innerHTML = '<div class="empty">点位不存在</div>'; return; }
      var s = j.site;
      $('#siteHead').innerHTML = '<div class="sh-no">' + (s.no || '') + '</div>' +
        '<h1 class="subh1">' + A.esc(s.name) + '</h1>' +
        '<div class="sh-meta">' + A.esc(s.level || '') + '</div>';
      $('#siteBody').innerHTML =
        '<div class="card">' + A.esc(s.intro || '') + '</div>' +
        '<div class="map-card"><div class="map-head"><span>位置与导航</span>' +
        '<span class="map-tip" id="mtip">加载中…</span></div>' +
        '<div id="smap" class="route-map"></div>' +
        '<div class="geo-acts" id="gacts"></div></div>' +
        '<div class="card"><div class="brief-title">本点位任务</div><div id="taskBox">加载中…</div></div>';
      loadGeo(s);
      loadTask();
    });
  }

  function loadGeo(s) {
    function go(qs) {
      A.get('/api/geo?site=' + encodeURIComponent(sid) + (qs || '')).then(function (g) {
        if (!g || !g.ok) { $('#mtip').textContent = '暂无坐标'; return; }
        geo = g;
        drawMap(g);
        var acts = $('#gacts');
        acts.innerHTML = '<a class="geo-btn primary" target="_blank" rel="noopener" href="' +
          A.esc(g.amap.navFrom || g.amap.nav) + '">开始导航</a>' +
          '<a class="geo-btn" target="_blank" rel="noopener" href="' +
          A.esc(g.amap.search || g.amap.marker) + '">按名称搜</a>';
      });
    }
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(function (p) {
        pos = { lat: p.coords.latitude, lng: p.coords.longitude };
        go('&lat=' + pos.lat + '&lng=' + pos.lng);
      }, function () { go(''); }, { timeout: 6000, maximumAge: 300000 });
    } else go('');
  }

  function drawMap(g) {
    if (typeof L === 'undefined') {
      if (window.MiniMap) {
        window.MiniMap($('#smap'), [{ lat: g.lat, lng: g.lng, name: g.name, addr: g.addr,
          nav: (g.amap || {}).navFrom || (g.amap || {}).nav, search: (g.amap || {}).search }],
          { height: 300 });
      }
      return;
    }
    map = L.map('smap', { zoomControl: true, attributionControl: false })
      .setView([g.lat, g.lng], 14);
    var std = L.tileLayer('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
      { subdomains: '1234', maxZoom: 18 });
    var sat = L.tileLayer('https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
      { subdomains: '1234', maxZoom: 18 });
    var osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 });
    std.addTo(map);
    L.control.layers({ '标准': std, '卫星': sat, 'OSM': osm }, null,
      { position: 'topright', collapsed: true }).addTo(map);
    L.marker([g.lat, g.lng], {
      icon: L.divIcon({ className: 'mp-pin', html: '<span>1</span>', iconSize: [28, 28], iconAnchor: [14, 14] })
    }).addTo(map).bindPopup(A.esc(g.name), { maxWidth: 220 }).openPopup().bindTooltip(g.name, {
      permanent: true, direction: 'top', offset: [0, -14], className: 'mp-label'
    });
    if (pos) {
      L.marker([pos.lat, pos.lng], {
        icon: L.divIcon({ className: 'mp-me', html: '<span>我</span>', iconSize: [26, 26], iconAnchor: [13, 13] })
      }).addTo(map).bindPopup('我的位置');
      map.fitBounds([[g.lat, g.lng], [pos.lat, pos.lng]]).pad && map.pad(0.2);
      $('#mtip').textContent = '已定位';
    } else {
      $('#mtip').textContent = '未授权定位';
    }
    setTimeout(function () { map.invalidateSize(); }, 200);
  }

  function loadTask() {
    A.post('/api/task', { site: sid, identity: 'public', stage: 'middle' }).then(function (j) {
      task = (j && j.task) || null;
      var box = $('#taskBox');
      if (!task) { box.textContent = '暂无任务'; return; }
      var q = task.question || {};
      var html = '<div class="q-title">' + A.esc(task.prompt || '') + '</div>' +
        '<div class="q-text">' + A.esc(q.q || '') + '</div>';
      if ((task.taskType || 'choice') === 'choice') {
        html += '<div class="q-opts">' + (q.options || []).map(function (o, i) {
          return '<button class="q-opt" data-i="' + i + '">' + A.esc(o) + '</button>';
        }).join('') + '</div>';
      } else {
        html += '<textarea id="stext" rows="3" placeholder="写一句你的观察"></textarea>';
      }
      html += '<button class="btn-primary" id="ssubmit">提交</button>' +
        '<div class="err" id="serr"></div><div id="sres" class="qa-a"></div>';
      box.innerHTML = html;
      bindSubmit();
    });
  }

  function bindSubmit() {
    var picked = null;
    [].forEach.call(document.querySelectorAll('.q-opt'), function (b) {
      b.onclick = function () {
        picked = Number(b.dataset.i);
        [].forEach.call(document.querySelectorAll('.q-opt'), function (x) {
          x.classList.toggle('on', x === b);
        });
      };
    });
    $('#ssubmit').onclick = function () {
      var body = { site: sid, identity: 'public', stage: 'middle' };
      var t = task.taskType || 'choice';
      if (t === 'choice') {
        if (picked == null) { $('#serr').textContent = '请先选择'; return; }
        body.choice = [picked];
      } else {
        var v = ($('#stext') && $('#stext').value || '').trim();
        if (!v) { $('#serr').textContent = '写一句再提交'; return; }
        body.text = v;
      }
      A.post('/api/submit', body).then(function (j) {
        var r = (j && j.result) || {};
        $('#sres').textContent = (r.feedback || '') + (r.guide ? '\n' + r.guide : '');
      });
    };
  }

  load();
})();
