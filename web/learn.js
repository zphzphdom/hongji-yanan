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

  function api(path, body) {
    var payload = body || {};
    payload.visitor = VISITOR;
    return fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Visitor': VISITOR },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json(); });
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
    bubble('你好，我是延小讲。先问一句：你是以什么身份来延安的？', 'ai');
    optButtons(IDENTS, function (k, label) {
      state.identity = k;
      bubble(label, 'me');
      if (k === 'student') {
        bubble('在读哪个学段？我按学段给你配任务。', 'ai');
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
    bubble('这趟最想带走什么？', 'ai');
    optButtons(INTERESTS, function (k, label) {
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
    bubble('打算玩几天？（1—7 天，直接填数字）', 'ai');
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
    bubble('还有什么想说的？（可以直接跳过，我这就排线路）', 'ai');
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
      identity: state.identity, stage: state.stage,
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

    var list = $('#routeList');
    list.innerHTML = '';
    var lastDay = 0;
    state.route.forEach(function (r, i) {
      if (r.day && r.day !== lastDay) {
        lastDay = r.day;
        var dh = document.createElement('div');
        dh.className = 'route-day';
        dh.textContent = '第 ' + r.day + ' 天';
        list.appendChild(dh);
      }
      var d = document.createElement('div');
      d.className = 'route-item';
      var mins = r.minutes ? r.minutes + ' 分钟' : '';
      d.innerHTML = '<span class="route-no">' + r.order + '</span>' +
        '<div class="route-main"><div class="route-name">' + r.name +
        '<span class="route-lv">' + (r.level || '') + '</span></div>' +
        '<div class="route-why">' + (r.why || '') + '</div>' +
        (r.county ? '<div class="route-county">' + r.county + '</div>' : '') +
        '</div><span class="route-min">' + mins + '</span>';
      d.onclick = function () { openSite(r.siteId, i); };
      list.appendChild(d);
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
      $('#introLevel').textContent = j.site.level + ' 级景区 · 点位 ' + j.site.no;
      $('#introText').textContent = j.site.intro;
      show('stepIntro');
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
        box.innerHTML = '<div class="q-title">第 ' + (qi + 1) + ' 题：' + q.q + '</div>';
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
      box2.innerHTML = '<div class="q-title">' + task.prompt + '</div>' +
        '<div class="q-text">' + q.q + '</div>';
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
      $('#fbTitle').textContent = r.ok ? '这一站完成 ✓' : '还需要再想想';
      $('#fbBody').textContent = r.feedback + (r.guide ? '\n\n' + r.guide : '');
      $('#retryBtn').classList.toggle('hidden', r.ok);
      $('#continueBtn').classList.toggle('hidden', !r.ok);
      $('#continueBtn').textContent = last ? '完成线路' : '下一个点位';
      show('stepFeedback');
      if (r.ok) {
        state.justCompleted = true;
        state.afterFinish = function () {
          if (j.progress.allDone || last) showFinish(j.progress);
          else openSite(state.route[state.routeIdx + 1].siteId, state.routeIdx + 1);
        };
      }
    }).catch(function () {
      $('#submitBtn').disabled = false;
      $('#taskErr').textContent = '网络异常，请重试';
    });
  }

  function showFinish(p) {
    var done = (p.sites || []).filter(function (s) { return s.done; });
    var avg = done.reduce(function (a, s) { return a + (s.score || 0); }, 0) / Math.max(1, done.length);
    $('#finishSub').textContent = '已完成 ' + (p.done || done.length) + '/' + (p.total || 6) +
      ' 个点位，平均得分 ' + Math.round(avg) + ' 分。';
    var stats = $('#finishStats');
    stats.innerHTML = '';
    done.forEach(function (s) {
      var d = document.createElement('div');
      d.className = 'stat';
      d.innerHTML = '<div class="stat-v">' + (s.score || 0) + '</div><div class="stat-l">' + s.name + '</div>';
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
    api('/api/memorial', { site: siteId || '', name: signerName(), scope: state.scope }).then(function (j) {
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
    g.fillText('红迹·延安 · 展览点位学习', 80, 196);
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
    g.fillText(c.done + ' / ' + c.total + ' 个点位完成', 80, y + 76);
    y += 130;
    g.fillStyle = '#6E625C';
    g.font = '400 26px "PingFang SC",sans-serif';
    var det = c.detail;
    for (var j = 0; j < det.length; j += 20) { g.fillText(det.slice(j, j + 20), 80, y); y += 40; }
    // 二维码：右下角，扫码回到问答/线路页
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

    var sign = (c.user || '').trim();
    g.textAlign = 'right';
    if (sign) {
      g.fillStyle = '#8C1F28';
      g.font = '700 34px "Songti SC",serif';
      g.fillText('—— ' + sign, W - 80, H - 190);
    } else {
      g.fillStyle = '#C4B8AE';
      g.font = '400 24px "PingFang SC",sans-serif';
      g.fillText('（在上方填上你的名字）', W - 80, H - 190);
    }
    g.textAlign = 'left';
    g.fillStyle = '#A6978E';
    g.font = '400 22px "PingFang SC",sans-serif';
    g.fillText('红迹·延安 · ' + new Date().toLocaleDateString('zh-CN'), 80, H - 150);
    g.fillText('扫码继续参观', 80, H - 100);
  }

  /* ---------------- 绑定 ---------------- */
  function bind() {
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
