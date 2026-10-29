(function () {
  'use strict';
  var E = window.RedEngine;
  var $ = function (s) { return document.querySelector(s); };
  var KB = window.RED_KB, idx = null, mode = 'fact', lastAnswer = null, qrImg = null, LLM = null;

  var CHIPS = ['A01', 'A09', 'A04', 'A18', 'A10', 'B05', 'C01', 'E04'];

  /* ---------------- 知识库载入与热更新 ---------------- */
  function boot(kb) {
    KB = kb;
    idx = E.createIndex(kb);
    var meta = '知识库 v' + kb.version + ' · ' + kb.count + ' 条 · ' + kb.sources +
      ' 个来源 · 更新于 ' + kb.updated;
    if (LLM) meta += ' · 在线模型 ' + LLM;
    $('#kbMeta').textContent = meta;
    renderChips();
    var st = window.__SELFTEST__;
    $('#aboutStat').textContent = st
      ? ('自测：' + st.selfHit + '/' + st.total + ' 条自身问法命中；越界提问拒答 ' + st.oosRefused + '/' + st.oosTotal + '。')
      : ('知识库 ' + kb.count + ' 条，每条可追溯到原文。');
  }

  function refresh() {
    fetch('api/kb', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (kb) {
        if (kb && kb.version && (!window.RED_KB || kb.version !== window.RED_KB.version)) {
          var first = !window.RED_KB;
          window.RED_KB = kb;
          boot(kb);
          if (!first) toast('知识库已更新至 v' + kb.version);
        }
      }).catch(function () { /* 离线：用内嵌副本 */ });
  }

  /* ---------------- 渲染 ---------------- */
  function renderChips() {
    var box = $('#chips');
    box.innerHTML = '';
    CHIPS.forEach(function (id) {
      var e = KB.entries.filter(function (x) { return x.id === id; })[0];
      if (!e) return;
      var b = document.createElement('button');
      b.className = 'chip';
      b.textContent = e.q.replace(/？$/, '');
      b.onclick = function () { ask(e.q); };
      box.appendChild(b);
    });
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function addUser(text) {
    var m = el('div', 'msg me');
    m.appendChild(el('div', 'bubble', text));
    $('#chat').appendChild(m);
    scroll();
  }

  function addTyping() {
    var m = el('div', 'msg');
    var b = el('div', 'bubble');
    var t = el('div', 'typing');
    t.innerHTML = '<i></i><i></i><i></i>';
    b.appendChild(t);
    m.appendChild(b);
    m.id = 'typingMsg';
    $('#chat').appendChild(m);
    scroll();
    return m;
  }

  function scroll() {
    var c = $('#chat');
    requestAnimationFrame(function () { c.scrollTop = c.scrollHeight; });
  }

  function addAnswer(r, question) {
    var m = el('div', 'msg');
    var b = el('div', 'bubble' + (r.refused ? ' refused' : ''));

    if (r.mode === 'research') b.appendChild(el('div', 'mode-note', '研学讲解词'));
    if (r.mode === 'moment') b.appendChild(el('div', 'mode-note', '一句话'));
    if (r.llm) b.appendChild(el('div', 'mode-note', '在线模型 ' + r.llm + ' 改写 · 事实来自知识库'));

    var a = el('div', 'answer');
    if (r.refused) {
      a.textContent = r.text;
    } else {
      // 把「看什么：」这类前缀加粗
      r.text.split('\n').forEach(function (line, i) {
        var p = el('div');
        var mm = line.match(/^(看什么|为什么重要|想一想)[:：]/);
        if (mm) {
          p.appendChild(el('span', 'lbl', mm[1] + '：'));
          p.appendChild(document.createTextNode(line.slice(mm[0].length)));
        } else {
          p.textContent = line;
        }
        a.appendChild(p);
      });
    }
    b.appendChild(a);

    if (r.sources && r.sources.length) {
      var row = el('div', 'src-row');
      r.sources.forEach(function (s) {
        var t = el('span', 'src-tag', s.id + ' · ' + s.org);
        t.onclick = function () { showSource(s); };
        row.appendChild(t);
      });
      b.appendChild(row);
    }

    if (!r.refused) {
      var acts = el('div', 'acts');
      var b1 = el('button', 'act', '生成问答卡');
      b1.onclick = function () { openCard(r, question); };
      var b2 = el('button', 'act', '复制文案');
      b2.onclick = function () { copyText(r, question); };
      acts.appendChild(b1); acts.appendChild(b2);
      b.appendChild(acts);
    } else {
      var acts2 = el('div', 'acts');
      var b3 = el('button', 'act', '换个问法试试');
      b3.onclick = function () { $('#input').focus(); };
      acts2.appendChild(b3);
      b.appendChild(acts2);
    }

    m.appendChild(b);
    $('#chat').appendChild(m);
    scroll();
  }

  /* ---------------- 提问 ---------------- */
  function ask(text) {
    text = String(text || '').trim();
    if (!text) return;
    var intro = $('#intro');
    if (intro) intro.remove();
    addUser(text);
    $('#input').value = '';
    $('#input').style.height = 'auto';
    var tip = addTyping();

    setTimeout(function () {
      var r;
      try { r = E.ask(idx, text, mode); }
      catch (err) { r = { refused: true, text: '引擎出了点问题，请刷新重试。', sources: [] }; }
      r.mode = mode;

      function render() {
        tip.remove();
        addAnswer(r, text);
        lastAnswer = { r: r, q: text };
        log(text, r);
      }

      // 有服务端模型时：只把"已核对的答案"交给模型改写，事实仍由知识库决定
      if (LLM && !r.refused && r.raw) {
        fetch('api/chat', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: text, answer: r.raw, mode: mode, id: r.entryId, score: r.score })
        }).then(function (x) { return x.ok ? x.json() : null; })
          .then(function (j) {
            if (j && j.ok && j.answer) { r.text = j.answer; r.llm = j.model; r.llmMs = j.ms; }
            render();
          })
          .catch(function () { render(); });
      } else {
        render();
      }
    }, 300);
  }

  function log(q, r) {
    try {
      fetch('api/log', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q: q, mode: mode, id: r.entryId || null, refused: !!r.refused, score: r.score || 0 })
      }).catch(function () {});
    } catch (e) {}
  }

  /* ---------------- 来源详情 ---------------- */
  function showSource(s) {
    $('#srcTitle').textContent = '来源 ' + s.id;
    var box = $('#srcBody');
    box.innerHTML = '';
    var d = el('div', 'src-item');
    d.innerHTML = '<div class="k">发布机构</div><div class="t">' + esc(s.org) + '</div>' +
      '<div class="k" style="margin-top:8px">文件 / 页面</div><div class="t">' + esc(s.doc) + '</div>' +
      '<div class="d">发布日期：' + esc(s.date) + '</div>' +
      (s.url ? '<div class="d"><a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.url) + '</a></div>' : '');
    box.appendChild(d);
    $('#srcMask').classList.remove('hidden');
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /* ---------------- 问答卡 ---------------- */
  function firstSentence(t, max) {
    var s = String(t || '').replace(/\s+/g, '');
    var m = s.match(/^[^。！？；]*[。！？；]?/);
    var out = (m ? m[0] : s) || s;
    return out.length > max ? out.slice(0, max - 1) + '…' : out;
  }

  function openCard(r, question) {
    lastAnswer = { r: r, q: question };
    drawCard(r, question);
    $('#cardMask').classList.remove('hidden');
  }

  function wrap(ctx, text, x, y, maxW, lh, maxLines) {
    var line = '', lines = 0;
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if (ch === '\n') { ctx.fillText(line, x, y); y += lh; line = ''; lines++; if (lines >= maxLines) return y; continue; }
      var test = line + ch;
      if (ctx.measureText(test).width > maxW && line) {
        ctx.fillText(line, x, y);
        y += lh; line = ch; lines++;
        if (lines >= maxLines) { ctx.fillText(line.slice(0, -1) + '…', x, y); return y; }
      } else line = test;
    }
    if (line) { ctx.fillText(line, x, y); y += lh; }
    return y;
  }

  function drawCard(r, question) {
    var c = $('#cardCanvas'), g = c.getContext('2d');
    var W = c.width, H = c.height;
    g.clearRect(0, 0, W, H);

    // 底
    g.fillStyle = '#FAF5EF'; g.fillRect(0, 0, W, H);
    var grad = g.createLinearGradient(0, 0, W, 360);
    grad.addColorStop(0, '#8C1F28'); grad.addColorStop(1, '#6B1219');
    g.fillStyle = grad; g.fillRect(0, 0, W, 300);
    g.fillStyle = '#B0863A'; g.fillRect(0, 300, W, 4);

    // 头部
    g.fillStyle = '#FFFFFF';
    g.font = '700 74px "Songti SC","SimSun",serif';
    g.fillText('红迹·延安', 80, 140);
    g.fillStyle = 'rgba(250,245,239,.86)';
    g.font = '400 30px "PingFang SC","Microsoft YaHei",sans-serif';
    g.fillText('AI 讲解员 · 延小讲｜在延安，问一句有出处的话', 80, 196);
    g.fillStyle = 'rgba(176,134,58,.95)';
    g.font = '400 24px "PingFang SC",sans-serif';
    g.fillText('延安 · 1935—1948', 80, 250);

    var y = 388;
    g.fillStyle = '#B0863A';
    g.font = '600 24px "PingFang SC",sans-serif';
    g.fillText('我问了', 80, y); y += 62;

    g.fillStyle = '#211A17';
    g.font = '700 44px "Songti SC","SimSun",serif';
    y = wrap(g, '「' + question + '」', 80, y, 920, 62, 2) + 32;

    g.fillStyle = '#B0863A';
    g.font = '600 24px "PingFang SC",sans-serif';
    g.fillText('它说', 80, y); y += 58;

    g.fillStyle = '#3A2E29';
    g.font = '400 34px "PingFang SC","Microsoft YaHei",sans-serif';
    var body = r.text || r.raw || '';
    y = wrap(g, body.replace(/\n/g, ' '), 80, y, 920, 54, 5) + 26;

    // 来源条
    if (r.sources && r.sources.length) {
      var s = r.sources[0];
      g.fillStyle = 'rgba(176,134,58,.10)';
      g.fillRect(64, y - 34, W - 128, 96);
      g.fillStyle = '#8C1F28';
      g.font = '600 22px "PingFang SC",sans-serif';
      g.fillText('来源 ' + s.id + ' · ' + s.org, 88, y + 4);
      g.fillStyle = '#6E625C';
      g.font = '400 20px "PingFang SC",sans-serif';
      var doc = s.doc.length > 30 ? s.doc.slice(0, 29) + '…' : s.doc;
      g.fillText(doc + '　' + s.date, 88, y + 38);
      y += 96;
    }

    // 二维码
    var qs = 250, qx = W - 80 - qs, qy = H - 80 - qs;
    g.fillStyle = '#FFFFFF';
    g.fillRect(qx - 14, qy - 14, qs + 28, qs + 28);
    g.strokeStyle = '#E7DCD3'; g.lineWidth = 2; g.strokeRect(qx - 14, qy - 14, qs + 28, qs + 28);
    if (qrImg && qrImg.complete && qrImg.naturalWidth) {
      g.drawImage(qrImg, qx, qy, qs, qs);
    } else {
      g.strokeStyle = '#D9C9C9'; g.setLineDash([8, 8]);
      g.strokeRect(qx, qy, qs, qs); g.setLineDash([]);
      g.fillStyle = '#A6978E'; g.font = '400 22px "PingFang SC",sans-serif';
      g.fillText('二维码位', qx + 62, qy + 128);
    }
    g.fillStyle = '#6E625C'; g.font = '400 22px "PingFang SC",sans-serif';
    g.fillText('扫码继续问', qx + 58, qy + qs + 46);

    // 左下角
    g.fillStyle = '#211A17';
    g.font = '400 26px "PingFang SC",sans-serif';
    g.fillText('我问到了什么，也留下了出处。', 80, H - 120);
    g.fillStyle = '#A6978E';
    g.font = '400 20px "PingFang SC",sans-serif';
    g.fillText('红迹·延安 · 只答有来源的史实', 80, H - 78);

    // 角标
    g.fillStyle = 'rgba(140,31,40,.9)';
    g.beginPath(); g.arc(W - 120, 120, 66, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#F3D9B8';
    g.font = '700 30px "Songti SC",serif';
    g.textAlign = 'center';
    g.fillText('延安', W - 120, 118);
    g.font = '400 18px "PingFang SC",sans-serif';
    g.fillText('1935—1948', W - 120, 146);
    g.textAlign = 'left';
  }

  function cardText(r, q) {
    var s = r.sources && r.sources[0];
    var summary = firstSentence(r.text || r.raw, 52);
    return '我问了「' + q + '」，它告诉我：' + summary +
      '——来自延安 AI 讲解员「延小讲」，扫码继续问。' +
      (s ? '（来源：' + s.id + ' ' + s.org + '《' + s.doc + '》' + s.date + '）' : '');
  }

  function copyText(r, q) {
    var txt = cardText(r, q);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(function () { toast('文案已复制'); },
        function () { fallbackCopy(txt); });
    } else fallbackCopy(txt);
  }

  function fallbackCopy(txt) {
    var ta = document.createElement('textarea');
    ta.value = txt; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); toast('文案已复制'); } catch (e) { toast('复制失败，请长按选择'); }
    ta.remove();
  }

  function toast(msg) {
    var t = $('#toast');
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.remove('on'); }, 1900);
  }

  /* ---------------- 事件 ---------------- */
  function bind() {
    $('#sendBtn').onclick = function () { ask($('#input').value); };
    $('#input').addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask($('#input').value); }
    });
    $('#input').addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 110) + 'px';
    });
    $('#modes').addEventListener('click', function (e) {
      var b = e.target.closest('.mode');
      if (!b) return;
      mode = b.dataset.mode;
      [].forEach.call(this.children, function (x) { x.classList.toggle('on', x === b); });
      toast(mode === 'fact' ? '史实问答：直接给结论和来源' :
        mode === 'research' ? '研学讲解词：看什么—为什么重要—想一想' : '一句话：适合直接发朋友圈');
    });
    $('#srcClose').onclick = function () { $('#srcMask').classList.add('hidden'); };
    $('#srcMask').onclick = function (e) { if (e.target === this) this.classList.add('hidden'); };
    $('#cardClose').onclick = function () { $('#cardMask').classList.add('hidden'); };
    $('#cardMask').onclick = function (e) { if (e.target === this) this.classList.add('hidden'); };
    $('#aboutBtn').onclick = function () { $('#aboutMask').classList.remove('hidden'); };
    $('#aboutClose').onclick = function () { $('#aboutMask').classList.add('hidden'); };
    $('#aboutMask').onclick = function (e) { if (e.target === this) this.classList.add('hidden'); };
    $('#dlBtn').onclick = function () {
      var c = $('#cardCanvas');
      c.toBlob(function (blob) {
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = '红迹延安-问答卡.png';
        a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
        toast('已保存到相册/下载目录');
      }, 'image/png');
    };
    $('#copyBtn').onclick = function () {
      if (lastAnswer) copyText(lastAnswer.r, lastAnswer.q);
    };
  }

  function init() {
    bind();
    if (KB) boot(KB);
    refresh();
    setInterval(refresh, 45000);
    fetch('api/capabilities', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (c) {
        if (c && c.llm) { LLM = c.model; if (KB) boot(KB); }
      }).catch(function () {});
    fetch('api/selftest', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s || !s.self) return;
        window.__SELFTEST__ = {
          selfHit: s.self.hit, total: s.self.total,
          oosRefused: s.outOfScope.refused, oosTotal: s.outOfScope.total
        };
        if (KB) boot(KB);
      }).catch(function () {});
    qrImg = new Image();
    qrImg.onload = function () { if (lastAnswer) drawCard(lastAnswer.r, lastAnswer.q); };
    qrImg.src = 'qr.png';
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
