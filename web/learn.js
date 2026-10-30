(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var state = {
    site: null, sites: [], stage: 'middle', identity: 'student',
    task: null, progress: null, lastImage: null, afterFinish: null
  };
  var STAGES = { primary: '小学', middle: '初中', high: '高中', college: '大学' };
  var IDENTS = { student: '学生', teacher: '教师', party: '党员', public: '群众' };

  function api(path, body) {
    var opt = { headers: { 'Content-Type': 'application/json' }, method: 'POST' };
    var tok = null;
    try { tok = localStorage.getItem('hy_token'); } catch (e) { tok = null; }
    if (tok) opt.headers.Authorization = 'Bearer ' + tok;
    opt.body = JSON.stringify(body || {});
    return fetch(path, opt).then(function (r) { return r.json(); });
  }

  function toast(msg) {
    var t = $('#toast');
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.remove('on'); }, 2000);
  }

  function show(id) {
    ['stepPick', 'stepIntro', 'stepIdentity', 'stepTask', 'stepFeedback', 'stepFinish'].forEach(function (k) {
      $('#' + k).classList.toggle('hidden', k !== id);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function renderProgress(p) {
    if (!p) return;
    $('#progFill').style.width = p.percent + '%';
    $('#progTxt').textContent = p.done + '/' + p.total;
    var grid = $('#siteGrid');
    grid.innerHTML = '';
    p.sites.forEach(function (s) {
      var d = document.createElement('button');
      d.className = 'site-chip' + (s.done ? ' done' : '');
      d.innerHTML = '<span class="chip-no">' + (s.no < 10 ? '0' + s.no : s.no) + '</span>' +
        '<span class="chip-name">' + s.name + '</span>' +
        (s.done ? '<span class="chip-ok">✓</span>' : '');
      d.onclick = function () { openSite(s.id); };
      grid.appendChild(d);
    });
    if (p.allDone) {
      setTimeout(function () { showFinish(p); }, 260);
    }
  }

  function openSite(sid) {
    api('/api/site', { site: sid }).then(function (j) {
      if (!j || !j.ok) { toast('点位不存在'); return; }
      state.site = j.site;
      state.sites = j.sites;
      state.progress = j.progress;
      renderProgress(j.progress);
      $('#siteName').textContent = j.site.name;
      $('#introNo').textContent = j.site.no < 10 ? '0' + j.site.no : j.site.no;
      $('#introName').textContent = j.site.name;
      $('#introLevel').textContent = j.site.level + ' 级景区 · 点位 ' + j.site.no;
      $('#introText').textContent = j.site.intro;
      show('stepIntro');
    });
  }

  function bindOpts() {
    var io = $('#identOpts'), so = $('#stageOpts');
    Object.keys(IDENTS).forEach(function (k) {
      var b = document.createElement('button');
      b.className = 'opt' + (k === state.identity ? ' on' : '');
      b.textContent = IDENTS[k];
      b.dataset.k = k;
      b.onclick = function () {
        state.identity = k;
        [].forEach.call(io.children, function (x) { x.classList.toggle('on', x === b); });
        $('#stageLabel').classList.toggle('hidden', k === 'party');
        so.classList.toggle('hidden', k === 'party');
      };
      io.appendChild(b);
    });
    Object.keys(STAGES).forEach(function (k) {
      var b = document.createElement('button');
      b.className = 'opt' + (k === state.stage ? ' on' : '');
      b.textContent = STAGES[k];
      b.dataset.k = k;
      b.onclick = function () {
        state.stage = k;
        [].forEach.call(so.children, function (x) { x.classList.toggle('on', x === b); });
      };
      so.appendChild(b);
    });
  }

  function renderTask(task) {
    state.task = task;
    $('#taskKind').textContent = task.kind;
    $('#taskHint').textContent = task.mode === 'party'
      ? '电子讲解 + 判断题' : '可交选择题 / 文本 / 图片';
    var script = $('#partyScript');
    if (task.script) {
      script.classList.remove('hidden');
      script.textContent = task.script;
    } else script.classList.add('hidden');

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
            b.dataset.sel = '1';
            opts.dataset.picked = String(oi);
          };
          opts.appendChild(b);
        });
        box.appendChild(opts);
        qc.appendChild(box);
      });
    } else {
      var q = task.question;
      var box2 = document.createElement('div');
      box2.className = 'q-block';
      box2.innerHTML = '<div class="q-title">' + task.prompt + '</div>';
      var opts2 = document.createElement('div');
      opts2.className = 'q-opts';
      q.options.forEach(function (o, oi) {
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
      qc.appendChild(box2);
    }
    $('#textAreaBox').classList.toggle('hidden', task.allow.indexOf('text') < 0);
    $('#taskErr').textContent = '';
    show('stepTask');
  }

  function collect() {
    var out = { site: state.site.id, identity: state.identity, stage: state.stage };
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
    var opts = document.querySelector('#questionCard .q-opts');
    if (opts && opts.dataset.picked !== undefined) out.choice = [Number(opts.dataset.picked)];
    var ta = $('#textAns');
    if (ta && ta.value.trim()) out.text = ta.value.trim();
    if (state.lastImage) out.image = state.lastImage;
    if (!out.choice && !out.text && !out.image) return { err: '请至少选择或填写一项' };
    return out;
  }

  function submit() {
    var body = collect();
    if (body.err) { $('#taskErr').textContent = body.err; return; }
    $('#submitBtn').disabled = true;
    api('/api/submit', body).then(function (j) {
      $('#submitBtn').disabled = false;
      if (!j || !j.ok) { $('#taskErr').textContent = '提交失败，请重试'; return; }
      state.progress = j.progress;
      renderProgress(j.progress);
      var r = j.result;
      $('#fbTitle').textContent = r.ok ? '这一站完成 ✓' : '还需要再想想';
      $('#fbBody').textContent = r.feedback + (r.guide ? '\n\n' + r.guide : '');
      $('#retryBtn').classList.toggle('hidden', r.ok);
      $('#continueBtn').classList.toggle('hidden', !r.ok);
      show('stepFeedback');
      if (r.ok && j.progress.allDone) {
        state.afterFinish = function () { showFinish(j.progress); };
      }
    }).catch(function () {
      $('#submitBtn').disabled = false;
      $('#taskErr').textContent = '网络异常，请重试';
    });
  }

  function showFinish(p) {
    var done = p.sites.filter(function (s) { return s.done; });
    var avg = done.reduce(function (a, s) { return a + (s.score || 0); }, 0) / Math.max(1, done.length);
    $('#finishSub').textContent = '你完成了全部 ' + p.total + ' 个展览点位，平均得分 ' + Math.round(avg) + ' 分。';
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
  function openMemorial(siteId) {
    api('/api/memorial', { site: siteId || '' }).then(function (j) {
      if (!j || !j.ok) return;
      drawMemorial(j.card);
      $('#memMask').classList.remove('hidden');
    });
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
    var line = c.line;
    var y = 420;
    for (var i = 0; i < line.length; i += 16) {
      g.fillText(line.slice(i, i + 16), 80, y);
      y += 58;
    }
    y += 20;

    // 进度条
    g.fillStyle = '#E7DCD3';
    g.fillRect(80, y, W - 160, 26);
    g.fillStyle = '#8C1F28';
    g.fillRect(80, y, (W - 160) * (c.percent / 100), 26);
    g.fillStyle = '#8C1F28';
    g.font = '700 30px "PingFang SC",sans-serif';
    g.fillText(c.done + ' / ' + c.total + ' 个点位完成', 80, y + 76);
    y += 130;

    g.fillStyle = '#6E625C';
    g.font = '400 26px "PingFang SC",sans-serif';
    var det = c.detail;
    for (var j = 0; j < det.length; j += 20) {
      g.fillText(det.slice(j, j + 20), 80, y);
      y += 40;
    }

    g.fillStyle = '#A6978E';
    g.font = '400 22px "PingFang SC",sans-serif';
    g.fillText('账号：' + c.user + ' · 生成于 ' + new Date().toLocaleDateString('zh-CN'), 80, H - 150);
    g.fillText('扫码继续参观', 80, H - 100);
  }

  function bind() {
    if (state.sites.length === 0) {
      api('/api/progress', {}).then(function (j) {
        if (!j || !j.ok) return;
        state.sites = j.sites;
        renderProgress(j.progress);
        var q = new URLSearchParams(location.search).get('site');
        if (q) openSite(q);
      });
    }
    $('#toIdentity').onclick = function () { show('stepIdentity'); };
    $('#toTask').onclick = function () {
      api('/api/task', { site: state.site.id, identity: state.identity, stage: state.stage })
        .then(function (j) {
          if (!j || !j.ok) { toast('任务下发失败'); return; }
          renderTask(j.task);
        });
    };
    $('#submitBtn').onclick = submit;
    $('#retryBtn').onclick = function () { show('stepTask'); };
    $('#continueBtn').onclick = function () {
      if (state.afterFinish) { state.afterFinish(); state.afterFinish = null; }
      else show('stepPick');
    };
    $('#cardBtn').onclick = function () { openMemorial(''); };
    $('#finalCardBtn').onclick = function () { openMemorial(''); };
    $('#memClose').onclick = function () { $('#memMask').classList.add('hidden'); };
    $('#memMask').onclick = function (e) { if (e.target === this) this.classList.add('hidden'); };
    $('#memSave').onclick = function () {
      var cv = $('#memCanvas');
      cv.toBlob(function (blob) {
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
  }

  bindOpts();
  bind();
})();
