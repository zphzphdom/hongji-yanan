(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };

  var VISITOR = (function () {
    var k = 'hy_visitor', v = null;
    try { v = localStorage.getItem(k); } catch (e) { v = null; }
    if (!v) {
      v = 'v' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
      try { localStorage.setItem(k, v); } catch (e) {}
    }
    return v;
  })();

  var REGION = (function () {
    try {
      var m = new URLSearchParams(location.search).get('r');
      if (m) { localStorage.setItem('hy_region', m); return m; }
      return localStorage.getItem('hy_region') || 'yanan';
    } catch (e) { return 'yanan'; }
  })();
  var REGIONS = [];

  var state = {
    site: null, sites: [], task: null, progress: null, lastImage: null,
    identity: 'student', stage: 'middle', interest: '', days: 1, note: '', scope: [],
    plan: null, route: [], routeIdx: 0, justCompleted: false, afterFinish: null
  };

  var STAGES = { primary: '小学', middle: '初中', high: '高中', college: '大学' };
  var IDENTS = { student: '学生', teacher: '教师', party: '党员', public: '群众' };
  var INTERESTS = {
    history: '革命旧址与事件', spirit: '延安精神与作风',
    nature: '自然风光与黄河', art: '文艺与新闻出版', family: '亲子与研学'
  };

  // 山西版：问题与选项都换成山西的说法
  var REGION_TALK = {
    yanan: {
      askIdentity: '你好，我是延小讲。先问一句：你是以什么身份来延安的？',
      askStage: '在读哪个学段？我按学段给你配任务。',
      askInterest: '这趟最想带走什么？',
      askDays: '打算在延安待几天？（1—7 天，直接填数字）',
      askNote: '还有什么想说的？（可以直接跳过，我这就排线路）',
      interests: {
        history: '革命旧址与事件', spirit: '延安精神与作风',
        nature: '自然风光与黄河', art: '文艺与新闻出版', family: '亲子与研学'
      }
    },
    shanxi: {
      askIdentity: '你好，我是晋小讲。先问一句：你是以什么身份来山西的？',
      askStage: '在读哪个学段？我按学段给你配任务。',
      askInterest: '这趟最想看哪一类？',
      askDays: '打算在山西待几天？（1—7 天，直接填数字）',
      askNote: '还有什么想说的？（比如想重点看平型关或太行纪念馆）',
      interests: {
        history: '八路军抗战旧址', spirit: '太行精神与作风',
        nature: '太行山水与关隘', art: '抗战文艺与报刊', family: '亲子与研学'
      }
    }
  };

  function talk() {
    return REGION_TALK[REGION] || REGION_TALK.yanan;
  }

  function api(path, body) {
    var payload = body || {};
    payload.visitor = VISITOR;
    return fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Visitor': VISITOR },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json(); });
  }

  function getJSON(url) {
    return fetch(url, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  function toast(msg) {
    var t = $('#toast');
    t.textContent = msg; t.classList.add('on');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.remove('on'); }, 2000);
  }

  function show(id) {
    if (id !== 'stepTask') stopSpeak();
    ['stepChat', 'stepPlan', 'stepIntro', 'stepTask', 'stepFeedback', 'stepFinish'].forEach(function (k) {
      var el = $('#' + k);
      if (el) el.classList.toggle('hidden', k !== id);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }



  function applyLearnRegion(r) {
    if (!r) return;
    var brand = r.brand || ('红迹·' + (r.name || '延安'));
    var ai = r.aiName || '延小讲';
    document.title = (r.title || brand) + ' · 点位学习';
    var bn = document.querySelector('.brand-name');
    if (bn) bn.textContent = brand;
    var sub = document.querySelector('.brand-sub');
    if (sub) sub.textContent = ai + ' · 陪你走' + (r.name || '延安');
    document.documentElement.style.setProperty('--region-accent', r.accent || '#8C1F28');
    var head = document.querySelector('.learn-top .brand');
    if (head) head.setAttribute('data-region', r.id || '');
  }

  /* ---------------- 地区切换 ---------------- */
  function renderRegionBar() {
    var bar = $('#regionBar');
    if (!bar || !REGIONS.length) return;
    bar.innerHTML = '';
    REGIONS.forEach(function (r) {
      var b = document.createElement('button');
      b.className = 'region-pill' + (r.id === REGION ? ' on' : '');
      b.innerHTML = '<span class="rp-name">' + r.name + '</span>' +
        '<span class="rp-meta">' + (r.count || 0) + ' 条 · ' +
        Math.round((r.chars || 0) / 1000) + 'k 字</span>';
      b.onclick = function () {
        if (r.id === REGION) return;
        REGION = r.id;
        try { localStorage.setItem('hy_region', r.id); } catch (e) {}
        document.documentElement.style.setProperty('--region-accent', r.accent || '#8C1F28');
        renderRegionBar();
        toast('已切换到「' + r.name + '」，重新生成线路即可');
        state.route = [];
        state.scope = [];
        chatIdx = 0;
        startChat();
        show('stepChat');
      };
      bar.appendChild(b);
    });
  }

  function bootRegions() {
    fetch('api/regions', { cache: 'no-store' }).then(function (r) { return r.json(); })
      .then(function (d) {
        REGIONS = (d && d.regions) || [];
        if (!REGIONS.some(function (x) { return x.id === REGION; })) {
          REGION = REGIONS.length ? REGIONS[0].id : 'yanan';
        }
        applyLearnRegion(REGIONS.filter(function (x) { return x.id === REGION; })[0]);
        renderRegionBar();
      }).catch(function () {});
  }

  /* ---------------- 一、对话式开场 ---------------- */
  function bubble(text, who) {
    var log = $('#chatLog');
    var d = document.createElement('div');
    d.className = 'bubble ' + (who || 'ai');
    d.textContent = text;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  function optButtons(opts, onPick) {
    var box = $('#chatOpts');
    box.innerHTML = '';
    Object.keys(opts).forEach(function (k) {
      var b = document.createElement('button');
      b.className = 'chat-opt';
      b.textContent = opts[k];
      b.onclick = function () { box.innerHTML = ''; onPick(k, opts[k]); };
      box.appendChild(b);
    });
  }

  function startChat() {
    $('#chatLog').innerHTML = '';
    $('#chatInputBox').classList.add('hidden');
    bubble(talk().askIdentity, 'ai');
    optButtons(IDENTS, function (k, label) {
      state.identity = k;
      bubble(label, 'me');
      if (k === 'student') {
        bubble(talk().askStage, 'ai');
        optButtons(STAGES, function (sk, sl) {
          state.stage = sk;
          bubble(sl, 'me');
          askInterest();
        });
      } else {
        askInterest();
      }
    });
  }

  function askInterest() {
    bubble(talk().askInterest, 'ai');
    optButtons(talk().interests, function (k, label) {
      state.interest = k;
      bubble(label, 'me');
      askDays();
    });
  }

  function clearInput() {
    var input = $('#chatInput');
    if (!input) return;
    input.value = '';
    input.removeAttribute('inputmode');
    input.placeholder = '比如：想带孩子看南泥湾，半天时间';
  }

  function askDays() {
    bubble(talk().askDays, 'ai');
    var box = $('#chatOpts');
    box.innerHTML = '';
    $('#chatInputBox').classList.remove('hidden');
    var input = $('#chatInput');
    input.value = String(state.days || 1);
    input.setAttribute('inputmode', 'numeric');
    input.placeholder = '比如 2';
    var send = $('#chatSend');
    send.textContent = '确定';
    send.onclick = function () { confirmDays(); };
    input.onkeydown = function (e) {
      if (e.key === 'Enter') { e.preventDefault(); confirmDays(); }
    };
  }

  function confirmDays() {
    var v = parseInt(($('#chatInput').value || '').replace(/[^0-9]/g, ''), 10);
    if (!v || v < 1) { toast('请填 1—7 之间的天数'); return; }
    if (v > 7) { toast('最多 7 天'); v = 7; }
    state.days = v;
    bubble(v + ' 天', 'me');
    $('#chatOpts').innerHTML = '';
    clearInput();                            // 发送后清空，避免沿用到下一问
    $('#chatInputBox').classList.add('hidden');
    askNote();
  }

  function askNote() {
    bubble(talk().askNote, 'ai');
    $('#chatOpts').innerHTML = '';
    clearInput();
    $('#chatInputBox').classList.remove('hidden');
    var send = $('#chatSend');
    send.textContent = '发送';
    send.onclick = function () { sendNote(); };
  }

  function sendNote() {
    var input = $('#chatInput');
    if (!input) return;
    var v = (input.value || '').trim();
    state.note = (state.note ? state.note + '；' : '') + v;
    if (v) bubble(v, 'me');
    clearInput();
    $('#chatInputBox').classList.add('hidden');
    buildPlan();
  }

  /* ---------------- 二、任务 + 线路 ---------------- */
  function buildPlan() {
    if (state._planning) return;
    state._planning = true;
    bubble('好，我去查资料，给你排一条线路……', 'ai');
    api('/api/plan', {
      identity: state.identity, stage: state.stage, region: REGION,
      interest: state.interest || 'history', days: state.days, note: state.note
    }).then(function (j) {
      state._planning = false;
      if (!j || !j.ok) { toast('线路生成失败，请重试'); return; }
      state.plan = j;
      state.route = j.route || [];
      state.routeIdx = 0;
      state.scope = (j.scope && j.scope.length) ? j.scope : state.route.map(function (r) { return r.siteId; });
      if (j.progress) renderProgress(j.progress);
      renderPlan(j);
      show('stepPlan');
    }).catch(function () {
      state._planning = false;
      toast('网络异常，请重试');
    });
  }

  function renderPlan(j) {
    $('#planLabel').textContent = j.label || '主题线路';
    $('#planTitle').textContent = j.title || '';
    $('#planIntro').textContent = j.intro || '';
    $('#taskSummary').textContent = (j.task && j.task.summary) || '';
    $('#routeCount').textContent = '(' + state.route.length + ' 个点位)';

    renderGallery(j.images || [], j.webImages || []);
    renderWebBrief(j.webBrief || []);
    renderSocial(j.social || []);
    var rt = state.route || [];
    enrichRouteGeo(rt, function () {
      // 相邻点位直线距离
      for (var k = 0; k < rt.length - 1; k++) {
        if (rt[k].geo && rt[k + 1].geo) {
          rt[k].legKm = haversineKm(rt[k].geo, rt[k + 1].geo).toFixed(1);
        }
      }
      initRouteMap(rt);
    });

    var list = $('#routeList');
    list.innerHTML = '';
    var lastDay = 0;
    state.route.forEach(function (r, i) {
      if (r.day && r.day !== lastDay) {
        lastDay = r.day;
        var dh = document.createElement('div');
        dh.className = 'route-day';
        dh.textContent = '第 ' + (r.day || '-') + ' 天';
        list.appendChild(dh);
      }
      var d = document.createElement('div');
      d.className = 'route-item';
      var mins = r.minutes ? r.minutes + ' 分钟' : '';
      d.innerHTML = '<span class="route-no">' + (r.order || (i + 1)) + '</span>' +
        '<div class="route-main"><div class="route-name">' + (r.name || '未命名点位') +
        '<span class="route-lv">' + (r.level || '') + '</span></div>' +
        '<div class="route-why">' + (r.why || '') + '</div>' +
        (r.county ? '<div class="route-county">' + r.county + '</div>' : '') +
        '</div><span class="route-min">' + mins + '</span>';
      d.onclick = function () { openSite(r.siteId, i); };
      list.appendChild(d);
    });
  }

  function renderSocial(items) {
    var box = $('#socialBox');
    if (!box) return;
    if (!items || !items.length) { box.classList.add('hidden'); box.innerHTML = ''; return; }
    box.classList.remove('hidden');
    var head = document.createElement('div');
    head.className = 'sb-head';
    head.textContent = '年轻人最近的讨论（小红书/抖音/B站公开页面）';
    box.appendChild(head);
    items.forEach(function (x) {
      var a = document.createElement('a');
      a.className = 'sb-row';
      a.href = x.url || '#';
      a.target = '_blank';
      a.rel = 'noopener';
      a.innerHTML = '<span class=sb-p>' + (x.platform || '') + '</span>' +
        '<span class=sb-t>' + (x.title || '') + '</span>';
      box.appendChild(a);
    });
  }

  function renderWebBrief(items) {
    var box = $('#webBrief');
    if (!box) return;
    if (!items.length) { box.classList.add('hidden'); box.innerHTML = ''; return; }
    box.classList.remove('hidden');
    var head = document.createElement('div');
    head.className = 'wb-head';
    head.textContent = '刚刚联网查到的最新相关信息';
    box.appendChild(head);
    items.forEach(function (x) {
      var row = document.createElement('a');
      row.className = 'wb-row';
      row.href = x.url || '#';
      row.target = '_blank';
      row.rel = 'noopener';
      row.innerHTML = '<span class=wb-title>' + (x.title || '') + '</span>' +
        '<span class=wb-site>' + (x.site || '') + (x.date ? ' · ' + x.date : '') + '</span>';
      box.appendChild(row);
    });
  }

  /* ---------------- 动态图片带 ---------------- */
  var galleryTimer = null;
  var galleryIdx = 0;

  function renderGallery(local, web) {
    var g = $('#gallery');
    if (!g) return;
    g.innerHTML = '';
    clearInterval(galleryTimer);
    var items = [];
    // 只使用联网图，不再回落到本地图库
    (web || []).forEach(function (x) {
      if (x.url) items.push({ src: x.url, alt: x.alt || '延安', credit: x.credit || '图源：网络' });
    });
    if (!items.length) { g.classList.add('hidden'); return; }
    g.classList.remove('hidden');

    var track = document.createElement('div');
    track.className = 'gallery-track';
    items.forEach(function (it) {
      var fig = document.createElement('figure');
      fig.className = 'gallery-item';
      var img = document.createElement('img');
      img.src = it.src; img.alt = it.alt; img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      img.onerror = function () { fig.classList.add('broken'); };
      img.onclick = function () { zoom(it.src, it.alt, it.credit); };
      fig.appendChild(img);
      if (it.credit) {
        var cap = document.createElement('figcaption');
        cap.textContent = it.credit;
        fig.appendChild(cap);
      }
      track.appendChild(fig);
    });
    g.appendChild(track);

    galleryIdx = 0;
    track.style.transform = 'translateX(0)';
    if (items.length > 2) {
      galleryTimer = setInterval(function () {
        var first = track.firstChild;
        var w = first ? first.offsetWidth + 10 : 220;
        var maxShift = Math.max(0, items.length - 2);
        galleryIdx = galleryIdx >= maxShift ? 0 : galleryIdx + 1;
        track.style.transform = 'translateX(' + (-galleryIdx * w) + 'px)';
      }, 3200);
    }
  }

  /* ---------------- 图片放大 ---------------- */
  function zoom(src, alt, credit) {
    var mask = $('#zoomMask');
    if (!mask || !src) return;
    $('#zoomImg').src = src;
    $('#zoomImg').alt = alt || '';
    $('#zoomCap').textContent = credit || '';
    mask.classList.remove('hidden');
    document.addEventListener('keydown', zoomEsc);
  }

  function zoomClose() {
    var mask = $('#zoomMask');
    if (!mask) return;
    mask.classList.add('hidden');
    $('#zoomImg').src = '';
    document.removeEventListener('keydown', zoomEsc);
  }

  function zoomEsc(e) { if (e.key === 'Escape') zoomClose(); }



  /* ---------------- 点位真实地图 ---------------- */
  var smap = null, smarkers = [];

  function initSiteMap(g) {
    var box = $('#siteMap');
    if (!box) return;
    var tip = $('#siteMapTip');
    if (typeof L === 'undefined') {
      box.innerHTML = '<div class="map-fallback">地图组件未加载，可点下方按钮用高德查看。</div>';
      return;
    }
    if (smap) { smap.remove(); smap = null; }
    smap = L.map(box, { zoomControl: true, attributionControl: false }).setView([g.lat, g.lng], 14);
    var amap = L.tileLayer(
      'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
      { subdomains: '1234', maxZoom: 18 });
    var osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 });
    var swapped = false;
    amap.on('tileerror', function () {
      if (swapped) return;
      swapped = true;
      smap.removeLayer(amap); osm.addTo(smap);
      if (tip) tip.textContent = '已切换备用瓦片';
    });
    amap.addTo(smap);

    var html = '<div class="mp"><div class="mp-t">' + (g.name || '') + '</div>' +
      (g.addr ? '<div class="mp-a">' + g.addr + '</div>' : '') +
      '<div class="mp-acts">' +
      '<a class="mp-btn primary" target="_blank" rel="noopener" href="' + (g.amap.navFrom || g.amap.nav) + '">开始导航</a>' +
      '<a class="mp-btn" target="_blank" rel="noopener" href="' + (g.amap.search || g.amap.marker) + '">按名称搜</a>' +
      '</div></div>';
    L.marker([g.lat, g.lng], {
      icon: L.divIcon({ className: 'mp-pin', html: '<span>1</span>', iconSize: [28, 28], iconAnchor: [14, 14] })
    }).addTo(smap).bindPopup(html, { maxWidth: 250 }).openPopup();
    smarkers = [];

    // 定位
    if (geoState.pos) {
      addMe(g);
    } else if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(function (p) {
        geoState.pos = { lat: p.coords.latitude, lng: p.coords.longitude };
        addMe(g);
      }, function () {
        if (tip) tip.textContent = '未授权定位 · 可点「开始导航」由高德定位';
      }, { timeout: 6000, maximumAge: 300000 });
    }
    setTimeout(function () { if (smap) smap.invalidateSize(); }, 200);
  }

  function addMe(g) {
    if (!smap || !geoState.pos) return;
    var me = [geoState.pos.lat, geoState.pos.lng];
    L.marker(me, { icon: L.divIcon({ className: 'mp-me', html: '<span>我</span>',
                                     iconSize: [26, 26], iconAnchor: [13, 13] }) })
      .addTo(smap).bindPopup('我的位置');
    var km = haversineKm(geoState.pos, { lat: g.lat, lng: g.lng });
    smap.fitBounds(L.latLngBounds([[g.lat, g.lng], me]).pad(0.3));
    var tip = $('#siteMapTip');
    if (tip) tip.textContent = '距你约 ' + km.toFixed(1) + ' 公里 · 点标点可导航';
  }

  /* ---------------- 位置卡与导航 ---------------- */
  var geoState = { data: null, pos: null };

  function haversineKm(a, b) {
    var R = 6371, toR = Math.PI / 180;
    var dLat = (b.lat - a.lat) * toR, dLng = (b.lng - a.lng) * toR;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(a.lat * toR) * Math.cos(b.lat * toR) *
            Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function loadGeo(siteId) {
    var card = $('#geoCard');
    if (!card) return;
    var q = '/api/geo?site=' + encodeURIComponent(siteId);
    function paint(pos) {
      if (pos) {
        geoState.pos = pos;
        q += '&lat=' + pos.lat + '&lng=' + pos.lng;
      }
      getJSON(q).then(function (g) {
        if (!g || !g.ok) {
          card.classList.add('hidden');
          return;
        }
        geoState.data = g;
        card.classList.remove('hidden');
        initSiteMap(g);
        var bits = [];
        bits.push('<b>' + g.name + '</b>');
        var place = [g.city, g.county].filter(Boolean).join(' · ');
        if (place) bits.push(place);
        if (g.addr) bits.push(g.addr);
        bits.push('坐标 ' + g.lat.toFixed(4) + ', ' + g.lng.toFixed(4) + (g.approx ? '（约，县区中心）' : '（约）'));
        if (g.distanceKm != null) {
          bits.push('直线距离 ' + g.distanceKm + ' 公里 · 车程约 ' + g.driveMin + ' 分钟');
        }
        $('#geoInfo').innerHTML = bits.map(function (x) { return '<div>' + x + '</div>'; }).join('');
        var nav = $('#geoNav'), open = $('#geoOpen'), search = $('#geoSearch');
        if (nav) nav.href = g.amap.navFrom || g.amap.nav;
        if (open) open.href = g.amap.marker;
        if (search) search.href = g.amap.search || g.amap.marker;
        var tip = $('#geoTip');
        if (tip) {
          if (!g.amap.precise) {
            tip.textContent = '该点坐标为县区级近似；点「按名称搜」可让高德按景点名精确定位。';
            return;
          }
          tip.textContent = g.distanceKm != null
            ? '点击「开始导航」会用高德地图规划驾车路线；手机端会尝试直接唤起高德 App。'
            : '未获取定位，导航将以下车地点为起点规划。允许定位可显示距离与车程。';
        }
      }).catch(function () { card.classList.add('hidden'); });
    }

    // 浏览器定位（可选）：失败就直接按坐标展示
    if (navigator.geolocation) {
      var done = false;
      var timer = setTimeout(function () { if (!done) { done = true; paint(null); } }, 4000);
      navigator.geolocation.getCurrentPosition(function (p) {
        if (done) return;
        done = true; clearTimeout(timer);
        paint({ lat: p.coords.latitude, lng: p.coords.longitude });
      }, function () {
        if (done) return;
        done = true; clearTimeout(timer);
        paint(null);
      }, { timeout: 3500, maximumAge: 60000 });
    } else {
      paint(null);
    }
  }

  function mapTile(url, opts) { return L.tileLayer(url, opts); }

  function initRouteMap(route) {
    var box = $('#routeMap');
    if (!box) return;
    if (typeof L === 'undefined') {
      box.innerHTML = '<div class="map-fallback">地图组件未加载，已显示点位列表；' +
        '可点下方「开始导航」用高德地图查看。</div>';
      var tip0 = $('#mapTip'); if (tip0) tip0.textContent = '示意图模式';
      return;
    }
    if (rmap) { rmap.remove(); rmap = null; }
    rlayers = [];
    rmap = L.map(box, { zoomControl: true, attributionControl: false }).setView([36.6, 109.5], 7);

    // 高德瓦片（GCJ-02，无需 Key），失败退回 OSM
    var amap = mapTile(
      'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
      { subdomains: '1234', maxZoom: 18, detectRetina: false });
    var osm = mapTile('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 });
    var switched = false;
    amap.on('tileerror', function () {
      if (switched) return;
      switched = true;
      rmap.removeLayer(amap);
      osm.addTo(rmap);
      var t = $('#mapTip'); if (t) t.textContent = '已切换备用瓦片';
    });
    amap.addTo(rmap);

    var pts = [];
    (route || []).forEach(function (r, i) {
      var g = r.geo;
      if (!g) return;
      var latlng = [g.lat, g.lng];
      pts.push(latlng);
      var dist = r.legKm != null ? ('距下一点约 ' + r.legKm + ' 公里') : '';
      var html = '<div class="mp"><div class="mp-t">' + (i + 1) + '. ' + (r.name || '') + '</div>' +
        '<div class="mp-d">' + (r.why || '') + '</div>' +
        (g.addr ? '<div class="mp-a">' + g.addr + '</div>' : '') +
        (dist ? '<div class="mp-a">' + dist + '</div>' : '') +
        '<div class="mp-acts">' +
        '<a class="mp-btn primary" target="_blank" rel="noopener" href="' + (g.navFrom || g.nav) + '">开始导航</a>' +
        '<a class="mp-btn" target="_blank" rel="noopener" href="' + (g.search || g.marker) + '">按名称搜</a>' +
        '</div></div>';
      var m = L.marker(latlng, {
        icon: L.divIcon({ className: 'mp-pin', html: '<span>' + (i + 1) + '</span>',
                          iconSize: [28, 28], iconAnchor: [14, 14] })
      }).addTo(rmap).bindPopup(html, { maxWidth: 260 });
      rlayers.push(m);
    });

    if (pts.length > 1) {
      var line = L.polyline(pts, { color: '#8C1F28', weight: 3, opacity: .85, dashArray: '6 6' })
        .addTo(rmap);
      rlayers.push(line);
    }
    if (pts.length) {
      rmap.fitBounds(L.latLngBounds(pts).pad(0.25));
    }

    // 设备定位：加一个「我的位置」标记，并刷新各点距离
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(function (p) {
        var me = [p.coords.latitude, p.coords.longitude];
        if (userMarker) rmap.removeLayer(userMarker);
        userMarker = L.marker(me, { icon: L.divIcon({ className: 'mp-me', html: '<span>我</span>',
                                                     iconSize: [26, 26], iconAnchor: [13, 13] }) })
          .addTo(rmap).bindPopup('我的位置');
        rlayers.push(userMarker);
        rmap.fitBounds(L.latLngBounds(pts.concat([me])).pad(0.2));
        var t = $('#mapTip');
        if (t) t.textContent = '已定位 · 点到点距离见标点弹窗';
      }, function () {
        var t = $('#mapTip');
        if (t) t.textContent = '未授权定位 · 仍可查看线路';
      }, { timeout: 5000, maximumAge: 60000 });
    } else {
      var t2 = $('#mapTip');
      if (t2) t2.textContent = '设备不支持定位';
    }

    setTimeout(function () { if (rmap) rmap.invalidateSize(); }, 200);
  }

  // 给线路补上坐标与相邻距离
  function enrichRouteGeo(route, done) {
    var i = 0;
    function next() {
      if (i >= route.length) { done(); return; }
      var r = route[i];
      getJSON('/api/geo?site=' + encodeURIComponent(r.siteId)).then(function (g) {
        if (g && g.ok) r.geo = g;
      }).catch(function () {}).then(function () {
        i += 1;
        next();
      });
    }
    next();
  }

  /* ---------------- 三、点位讲解 ---------------- */
  function openSite(sid, idx) {
    if (typeof idx === 'number') state.routeIdx = idx;
    api('/api/site', { site: sid, scope: state.scope }).then(function (j) {
      if (!j || !j.ok) { toast('点位不存在'); return; }
      state.site = j.site;
      state.sites = j.sites;
      renderProgress(j.progress);
      $('#siteName').textContent = j.site.name;
      $('#introNo').textContent = j.site.no < 10 ? '0' + j.site.no : j.site.no;
      $('#introName').textContent = j.site.name;
      $('#introLevel').textContent = (j.site.level || '') + ' 级景区 · 点位 ' + (j.site.no || '');
      $('#introText').textContent = j.site.intro;
      show('stepIntro');
      loadGeo(j.site.id);
    });
  }

  function renderProgress(p) {
    if (!p) return;
    state.progress = p;
    $('#progFill').style.width = p.percent + '%';
    $('#progTxt').textContent = p.done + '/' + p.total;
  }

  /* ---------------- 电子导览 ---------------- */
  var tourState = { list: [], i: 0, speaking: false };

  function stopSpeak() {
    try { if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch (e) {}
    tourState.speaking = false;
  }

  function speak(text) {
    if (!window.speechSynthesis) { toast('当前浏览器不支持朗读，可阅读文字'); return; }
    try {
      window.speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(text);
      u.lang = 'zh-CN'; u.rate = 0.95;
      u.onend = function () { tourState.speaking = false; syncSpeakBtn(); };
      window.speechSynthesis.speak(u);
      tourState.speaking = true;
      syncSpeakBtn();
    } catch (e) { toast('朗读失败，可阅读文字'); }
  }

  function syncSpeakBtn() {
    var b = $('#tourSpeak');
    if (b) b.textContent = tourState.speaking ? '■ 停止朗读' : '▶ 朗读本段';
  }

  function renderTour(tour) {
    tourState.list = tour; tourState.i = 0;
    var box = $('#partyScript');
    box.innerHTML = '';
    var head = document.createElement('div');
    head.className = 'tour-head';
    head.innerHTML = '<span class="tour-badge">电子导览</span><span class="tour-count" id="tourCount"></span>';
    box.appendChild(head);
    var body = document.createElement('div');
    body.className = 'tour-body'; body.id = 'tourBody';
    box.appendChild(body);
    var bar = document.createElement('div');
    bar.className = 'tour-bar';
    bar.innerHTML = '<button class="tour-btn" id="tourPrev">上一段</button>' +
      '<button class="tour-btn main" id="tourSpeak">▶ 朗读本段</button>' +
      '<button class="tour-btn" id="tourNext">下一段</button>';
    box.appendChild(bar);
    var tip = document.createElement('div');
    tip.className = 'tour-tip';
    tip.textContent = '可点「朗读本段」听语音讲解，也可直接读文字。';
    box.appendChild(tip);

    $('#tourPrev').onclick = function () { goTour(-1); };
    $('#tourNext').onclick = function () { goTour(1); };
    $('#tourSpeak').onclick = function () {
      if (tourState.speaking) { stopSpeak(); syncSpeakBtn(); return; }
      var seg = tourState.list[tourState.i];
      if (seg) speak(seg[0] + '。' + seg[1]);
    };
    showTourSegment(0);
  }

  function goTour(d) {
    var n = tourState.i + d;
    if (n < 0) { toast('已经是第一段'); return; }
    if (n >= tourState.list.length) { toast('导览已结束，可以答判断题了'); return; }
    showTourSegment(n, tourState.speaking);
  }

  function showTourSegment(i, autoSpeak) {
    tourState.i = i;
    var seg = tourState.list[i];
    var body = $('#tourBody');
    if (!seg || !body) return;
    body.innerHTML = '<div class="tour-title">' + (i + 1) + '. ' + seg[0] + '</div>' +
      '<div class="tour-text">' + seg[1] + '</div>';
    body.classList.remove('fade');
    void body.offsetWidth;
    body.classList.add('fade');
    var c = $('#tourCount');
    if (c) c.textContent = (i + 1) + ' / ' + tourState.list.length;
    var prev = $('#tourPrev'), next = $('#tourNext');
    if (prev) prev.disabled = i === 0;
    if (next) next.textContent = i === tourState.list.length - 1 ? '导览结束' : '下一段';
    if (autoSpeak === true) speak(seg[0] + '。' + seg[1]);
  }

  /* ---------------- 四、任务 ---------------- */
  function renderTask(task) {
    state.task = task;
    try { renderTaskInner(task); } catch (e) {
      if (window.console && console.error) console.error('renderTask', e);
      toast('页面渲染异常，已降级显示');
      show('stepTask');
    }
  }

  function renderTaskInner(task) {
    $('#taskKind').textContent = task.kind;
    $('#taskHint').textContent = task.mode === 'party'
      ? '电子导览 + 判断题' : '可交选择题 / 文本 / 图片';
    var script = $('#partyScript');
    if (task.mode === 'party' && task.tour && task.tour.length) {
      script.classList.remove('hidden');
      renderTour(task.tour);
    } else {
      script.classList.add('hidden');
      script.innerHTML = '';
      stopSpeak();
    }

    var qc = $('#questionCard');
    qc.innerHTML = '';
    if (task.mode === 'party') {
      task.questions.forEach(function (q, qi) {
        var box = document.createElement('div');
        box.className = 'q-block';
        box.innerHTML = '<div class="q-title">第 ' + (qi + 1) + ' 题：' + (q.q || '') + '</div>';
        var opts = document.createElement('div');
        opts.className = 'q-opts';
        q.options.forEach(function (o, oi) {
          var b = document.createElement('button');
          b.className = 'q-opt';
          b.textContent = o;
          b.onclick = function () {
            [].forEach.call(opts.children, function (x) { x.classList.toggle('on', x === b); });
            opts.dataset.picked = String(oi);
          };
          opts.appendChild(b);
        });
        box.appendChild(opts);
        qc.appendChild(box);
      });
    } else {
      var q = task.question;
      var ttype = task.taskType || q.type || 'choice';
      var box2 = document.createElement('div');
      box2.className = 'q-block';
      box2.innerHTML = '<div class="q-title">' + (task.prompt || '') + '</div>' +
        '<div class="q-text">' + (q.q || '') + '</div>';
      if (ttype === 'choice') {
        var opts2 = document.createElement('div');
        opts2.className = 'q-opts';
        (q.options || []).forEach(function (o, oi) {
          var b = document.createElement('button');
          b.className = 'q-opt';
          b.textContent = o;
          b.onclick = function () {
            [].forEach.call(opts2.children, function (x) { x.classList.toggle('on', x === b); });
            opts2.dataset.picked = String(oi);
          };
          opts2.appendChild(b);
        });
        box2.appendChild(opts2);
      } else {
        var hint = document.createElement('div');
        hint.className = 'q-kind-hint';
        hint.textContent = ttype === 'photo'
          ? '这一题：上传一张现场照片 + 一句说明'
          : '这一题：用文字写下你的观察（写到年份或数字更好）';
        box2.appendChild(hint);
      }
      qc.appendChild(box2);
    }
    var ttype = task.taskType || (task.question && task.question.type) || 'choice';
    var allow = task.allow || (task.mode === 'party' ? [] : ['choice']);
    // 文本/照片题才显示输入区；照片题必须上传图
    var showInput = task.mode !== 'party' && (ttype === 'text' || ttype === 'photo');
    $('#textAreaBox').classList.toggle('hidden', !showInput);
    var ta = $('#textAns');
    if (ta) {
      ta.placeholder = ttype === 'photo'
        ? '补一句说明：照片里是什么、写了什么字'
        : '写下你在展板上看到的细节、年份或数字……';
    }
    var up = $('#imgFile');
    if (up && up.parentNode) up.parentNode.classList.toggle('hidden', ttype !== 'photo');
    $('#taskErr').textContent = '';
    show('stepTask');
  }

  function collect() {
    var out = { site: state.site.id, identity: state.identity, stage: state.stage,
                scope: state.scope };
    if (state.task.mode === 'party') {
      var picks = [];
      var blocks = document.querySelectorAll('#questionCard .q-opts');
      for (var i = 0; i < blocks.length; i++) {
        if (blocks[i].dataset.picked === undefined) return { err: '还有题目没有选择答案' };
        picks.push(Number(blocks[i].dataset.picked));
      }
      out.choice = picks;
      return out;
    }
    var ttype = state.task.taskType || (state.task.question && state.task.question.type) || 'choice';
    if (ttype === 'choice') {
      var opts = document.querySelector('#questionCard .q-opts');
      if (!opts || opts.dataset.picked === undefined) return { err: '请先选择一个答案' };
      out.choice = [Number(opts.dataset.picked)];
      return out;
    }
    var ta = $('#textAns');
    if (ta && ta.value.trim()) out.text = ta.value.trim();
    if (state.lastImage) out.image = state.lastImage;
    if (ttype === 'photo') {
      if (!out.image) return { err: '这一题需要上传一张现场照片' };
      if (!out.text) return { err: '照片配一句说明再提交' };
      return out;
    }
    if (!out.text) return { err: '请写下你的观察再提交' };
    return out;
  }

  function submit() {
    var body = collect();
    if (body.err) { $('#taskErr').textContent = body.err; return; }
    $('#submitBtn').disabled = true;
    api('/api/submit', body).then(function (j) {
      $('#submitBtn').disabled = false;
      if (!j || !j.ok) { $('#taskErr').textContent = '提交失败，请重试'; return; }
      renderProgress(j.progress);
      var r = j.result;
      state.lastImage = null;
      var ta2 = $('#textAns'); if (ta2) ta2.value = '';
      var nm = $('#imgName'); if (nm) nm.textContent = '';
      var last = state.routeIdx >= state.route.length - 1;
      // 文本题/照片题一律视为完成（后端也已如此判定）
      var ttype = (state.task && (state.task.taskType ||
                   (state.task.question && state.task.question.type))) || 'choice';
      var done = r.ok || ttype === 'text' || ttype === 'photo';
      $('#fbTitle').textContent = done ? '这一站完成 ✓' : '还需要再想想';
      $('#fbBody').textContent = (r.feedback || '') + (r.guide ? '\n\n' + r.guide : '');
      $('#retryBtn').classList.toggle('hidden', done);
      $('#continueBtn').classList.toggle('hidden', !done);
      $('#continueBtn').textContent = last ? '完成线路' : '下一个点位';
      show('stepFeedback');
      if (done) {
        state.justCompleted = true;
        state.afterFinish = function () {
          if (j.progress.allDone) { showFinish(j.progress); return; }
          if (last) { showRouteEnd(j.progress); return; }
          openSite(state.route[state.routeIdx + 1].siteId, state.routeIdx + 1);
        };
      }
    }).catch(function () {
      $('#submitBtn').disabled = false;
      $('#taskErr').textContent = '网络异常，请重试';
    });
  }

  function showRouteEnd(p) {
    var left = (p.total || 0) - (p.done || 0);
    $('#finishTitle').textContent = '线路走完，还有 ' + left + ' 个点位没做';
    $('#finishSub').textContent = '已完成 ' + (p.done || 0) + '/' + (p.total || 0) +
      ' 个点位。可以回线路继续补做，或先生成当前进度的纪念卡。';
    var stats = $('#finishStats');
    stats.innerHTML = '';
    (p.sites || []).forEach(function (s) {
      var d = document.createElement('div');
      d.className = 'stat' + (s.done ? '' : ' stat-todo');
      d.innerHTML = '<div class="stat-v">' + (s.done ? (s.score || 0) : '未完成') +
        '</div><div class="stat-l">' + (s.name || '') + '</div>';
      stats.appendChild(d);
    });
    show('stepFinish');
  }

  function showFinish(p) {
    $('#finishTitle').textContent = '线路全部完成';
    var done = (p.sites || []).filter(function (s) { return s.done; });
    var avg = done.reduce(function (a, s) { return a + (s.score || 0); }, 0) / Math.max(1, done.length);
    $('#finishSub').textContent = '已完成 ' + (p.done || done.length) + '/' + (p.total || 6) +
      ' 个点位，平均得分 ' + Math.round(avg) + ' 分。';
    var stats = $('#finishStats');
    stats.innerHTML = '';
    done.forEach(function (s) {
      var d = document.createElement('div');
      d.className = 'stat';
      d.innerHTML = '<div class="stat-v">' + (s.score || 0) + '</div><div class="stat-l">' + (s.name || '') + '</div>';
      stats.appendChild(d);
    });
    show('stepFinish');
  }

  /* ---------------- 纪念卡 ---------------- */
  var lastName = '';

  function signerName() {
    var v = '';
    try { v = localStorage.getItem('hy_signer') || ''; } catch (e) {}
    var el = $('#memName');
    if (el && el.value.trim()) v = el.value.trim();
    return (v || '').trim().slice(0, 12);
  }

  var memQr = null;
  (function loadMemQr() {
    memQr = new Image();
    memQr.onload = function () { if (lastName) drawMemorial(lastName); };
    memQr.src = 'qr.png';
  })();

  function openMemorial(siteId) {
    api('/api/memorial', { site: siteId || '', name: signerName(), scope: state.scope, region: REGION }).then(function (j) {
      if (!j || !j.ok) return;
      lastName = j.card;
      var el = $('#memName');
      if (el) {
        el.value = signerName();
        if (!el.value) setTimeout(function () { try { el.focus(); } catch (e) {} }, 260);
      }
      drawMemorial(j.card);
      $('#memMask').classList.remove('hidden');
    });
  }

  function refreshMemorialName() {
    var name = signerName();
    try { localStorage.setItem('hy_signer', name); } catch (e) {}
    if (!lastName) return;
    var card = {};
    for (var k in lastName) card[k] = lastName[k];
    card.user = name;
    drawMemorial(card);
  }

  function drawMemorial(c) {
    var cv = $('#memCanvas'), g = cv.getContext('2d');
    var W = cv.width, H = cv.height;
    g.clearRect(0, 0, W, H);
    g.fillStyle = '#FAF5EF'; g.fillRect(0, 0, W, H);
    var grad = g.createLinearGradient(0, 0, W, 360);
    grad.addColorStop(0, '#8C1F28'); grad.addColorStop(1, '#6B1219');
    g.fillStyle = grad; g.fillRect(0, 0, W, 320);
    g.fillStyle = '#B0863A'; g.fillRect(0, 320, W, 4);
    g.fillStyle = '#fff';
    g.font = '700 66px "Songti SC",serif';
    g.fillText(c.title, 80, 140);
    g.font = '400 28px "PingFang SC",sans-serif';
    g.fillStyle = 'rgba(250,245,239,.9)';
    g.fillText((c.cardHead) || ((c.brand || '红迹·延安') + ' · 点位学习'), 80, 196);
    g.fillStyle = '#F3D9B8';
    g.font = '700 44px "Songti SC",serif';
    g.fillText(c.badge, 80, 268);

    g.fillStyle = '#211A17';
    g.font = '700 42px "Songti SC",serif';
    var y = 420, line = c.line;
    for (var i = 0; i < line.length; i += 16) { g.fillText(line.slice(i, i + 16), 80, y); y += 58; }
    y += 20;
    g.fillStyle = '#E7DCD3'; g.fillRect(80, y, W - 160, 26);
    g.fillStyle = '#8C1F28'; g.fillRect(80, y, (W - 160) * (c.percent / 100), 26);
    g.font = '700 30px "PingFang SC",sans-serif';
    g.fillText((c.done || 0) + ' / ' + (c.total || 0) + ' 个点位完成', 80, y + 76);
    y += 130;
    g.fillStyle = '#6E625C';
    g.font = '400 26px "PingFang SC",sans-serif';
    var det = c.detail;
    for (var j = 0; j < det.length; j += 20) { g.fillText(det.slice(j, j + 20), 80, y); y += 40; }
    // 右下角：二维码（占 H-300 ~ H-110 的右侧区域）
    if (memQr && memQr.complete && memQr.naturalWidth) {
      var qs = 190, qx = W - 80 - qs, qy = H - 110 - qs;
      g.fillStyle = '#FFFFFF';
      g.fillRect(qx - 12, qy - 12, qs + 24, qs + 24);
      g.strokeStyle = '#E7DCD3'; g.lineWidth = 2;
      g.strokeRect(qx - 12, qy - 12, qs + 24, qs + 24);
      g.drawImage(memQr, qx, qy, qs, qs);
      g.fillStyle = '#6E625C';
      g.font = '400 20px "PingFang SC",sans-serif';
      g.textAlign = 'center';
      g.fillText('扫码继续问', qx + qs / 2, qy + qs + 26);
      g.textAlign = 'left';
    }

    // 左下角：署名（与二维码左右分开，不重叠）
    var sign = (c.user || '').trim();
    var signY = H - 210;
    g.textAlign = 'left';
    g.fillStyle = '#A6978E';
    g.font = '400 20px "PingFang SC",sans-serif';
    g.fillText('署名', 80, signY - 34);
    if (sign) {
      g.fillStyle = '#8C1F28';
      g.font = '700 38px "Songti SC",serif';
      g.fillText(sign, 80, signY);
    } else {
      g.fillStyle = '#C4B8AE';
      g.font = '400 24px "PingFang SC",sans-serif';
      g.fillText('（在上方填上名字）', 80, signY);
    }
    g.fillStyle = '#A6978E';
    g.font = '400 22px "PingFang SC",sans-serif';
    g.fillText((c.brand || '红迹·延安') + ' · ' + new Date().toLocaleDateString('zh-CN'), 80, H - 120);
    g.fillText('扫码继续参观', 80, H - 80);
  }

  /* ---------------- 绑定 ---------------- */
  function primeGeo() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(function (p) {
      geoState.pos = { lat: p.coords.latitude, lng: p.coords.longitude };
      if (smap && geoState.data) addMe(geoState.data);
    }, function () {}, { timeout: 6000, maximumAge: 300000 });
  }

  function bind() {
    primeGeo();
    bootRegions();
    startChat();
    api('/api/progress', { scope: state.scope }).then(function (j) {
      if (j && j.ok) { state.sites = j.sites || []; renderProgress(j.progress); }
    });

    $('#chatSend').onclick = function () { sendNote(); };
    $('#chatInput').onkeydown = function (e) {
      if (e.key === 'Enter') { e.preventDefault(); sendNote(); }
    };
    function refine(text) {
      var t = String(text || '').trim();
      if (!t) { toast('先写一句要求'); return; }
      bubble(t, 'me');
      state.note = (state.note ? state.note + '；' : '') + t;
      state._planning = false;
      buildPlan();
      $('#refineNote').value = '';
    }
    $('#refineBtn').onclick = function () { refine($('#refineNote').value); };
    $('#refineNote').onkeydown = function (e) {
      if (e.key === 'Enter') { e.preventDefault(); refine($('#refineNote').value); }
    };
    var tags = document.querySelectorAll('.refine-tags .tag');
    [].forEach.call(tags, function (b) {
      b.onclick = function () { refine(b.dataset.tag); };
    });
    $('#startRoute').onclick = function () {
      if (!state.route.length) { toast('线路为空'); return; }
      openSite(state.route[0].siteId, 0);
    };
    $('#reChat').onclick = function () { show('stepChat'); startChat(); };
    var zc = $('#zoomClose');
    if (zc) zc.onclick = function (e) { e.stopPropagation(); zoomClose(); };
    var zm = $('#zoomMask');
    if (zm) zm.onclick = function (e) { if (e.target === this) zoomClose(); };
    $('#toTask2').onclick = function () {
      api('/api/task', { site: state.site.id, identity: state.identity, stage: state.stage, scope: state.scope })
        .then(function (j) {
          if (!j || !j.ok) { toast('任务下发失败'); return; }
          renderTask(j.task);
        });
    };
    $('#backPlan').onclick = function () { show('stepPlan'); };
    $('#submitBtn').onclick = submit;
    $('#retryBtn').onclick = function () { show('stepTask'); };
    $('#continueBtn').onclick = function () {
      if (state.afterFinish) { var f = state.afterFinish; state.afterFinish = null; f(); }
      else show('stepPlan');
    };
    $('#cardBtn').onclick = function () { openMemorial(''); };
    $('#finalCardBtn').onclick = function () { openMemorial(''); };
    var nameEl = $('#memName');
    if (nameEl) {
      nameEl.addEventListener('input', refreshMemorialName);
      nameEl.addEventListener('change', refreshMemorialName);
      try { nameEl.value = localStorage.getItem('hy_signer') || ''; } catch (e) {}
    }
    $('#memClose').onclick = function () { $('#memMask').classList.add('hidden'); };
    $('#memMask').onclick = function (e) { if (e.target === this) this.classList.add('hidden'); };
    $('#memSave').onclick = function () {
      $('#memCanvas').toBlob(function (blob) {
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = '红迹延安-学习纪念卡.png';
        a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
      }, 'image/png');
    };
    $('#imgFile').addEventListener('change', function (e) {
      var f = e.target.files && e.target.files[0];
      if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        state.lastImage = String(rd.result).slice(0, 600000);
        $('#imgName').textContent = '已选择：' + f.name;
      };
      rd.readAsDataURL(f);
    });

    // 扫码直达某点位（?site=P2）：跳过对话，直接进该点位
    var q = new URLSearchParams(location.search).get('site');
    if (q) {
      state.route = [{ siteId: q, name: '', why: '', order: 1, level: '' }];
      state.routeIdx = 0;
      state.identity = 'public';
      openSite(q, 0);
    }
  }

  bind();
})();
