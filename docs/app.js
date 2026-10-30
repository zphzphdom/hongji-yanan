(function () {
  'use strict';
  var E = window.RedEngine;
  var $ = function (s) { return document.querySelector(s); };
  var KB = window.RED_KB, idx = null, mode = 'fact', lastAnswer = null, qrImg = null, LLM = null, sending = false;

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

    var tags = [];
    if (r.mode === 'research') tags.push('研学讲解词');
    if (r.mode === 'moment') tags.push('一句话');
    if (r.degraded) tags.push('本地兜底');
    if (r.model) tags.push(r.model + ' 生成');
    if (r.usedWeb) tags.push('已联网补充');
    if (r.imageSource) tags.push('配图：' + r.imageSource);
    if (tags.length) b.appendChild(el('div', 'mode-note', tags.join(' · ')));

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
    // 先图后文：图片能立刻给出讲的是哪个点，正文随后出
    if (r.imageUrl || r.image) {
      var pic = {
        src: ((window.RED_IMAGES || {})[r.image] || {}).file || r.imageUrl,
        alt: r.imageAlt || r.image || '',
        credit: r.imageCredit || ('配图：' + (r.image || '')),
        fallback: ((window.RED_IMAGES || {})[r.image] || {}).file
      };
      if (pic.src) b.appendChild(imageBlock(pic));
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
    // 网络补图（与本地图并列展示，标注来源）
    if (r.imageUrl) {
      var wImg = imageBlock({
        src: r.imageUrl, alt: r.imageAlt || '', credit: r.imageCredit || '图源：网络',
        fallback: ((window.RED_IMAGES || {})[r.image] || {}).file
      });
      if (wImg.firstChild) {
        wImg.classList.add('img-web');
        b.appendChild(wImg);
      }
    }

    if (r.web && r.web.length) {
      var wr = el('div', 'web-row');
      r.web.slice(0, 2).forEach(function (w) {
        var t = el('span', 'web-tag', '联网 · ' + (w.site || w.title).slice(0, 16));
        t.title = w.title + ' ' + (w.url || '');
        wr.appendChild(t);
      });
      b.appendChild(wr);
    }

    // 核查结论（知识库只做辨真伪，不直接作答）
    if (r.verdict) b.appendChild(verdictBlock(r.verdict));

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

  /* ---------------- 提问：全部交给服务端（知识库 + DeepSeek 联网 + 模型整合） ---------------- */
  function ask(text) {
    text = String(text || '').trim();
    if (!text || sending) return;
    var intro = $('#intro');
    if (intro) intro.remove();
    addUser(text);
    $('#input').value = '';
    $('#input').style.height = 'auto';
    var tip = addTyping();
    sending = true;

    function render(r) {
      tip.remove();
      r.mode = mode;
      addAnswer(r, text);
      lastAnswer = { r: r, q: text };
      sending = false;
    }

    api('/api/ask', { question: text, mode: mode }).then(function (j) {
      if (j && j.ok) {
        render(j);
      } else {
        // 服务端不可用时才退回本地引擎，保证"永远答得出来"
        var r;
        try { r = E.ask(idx, text, mode); } catch (e) { r = { refused: true, text: '服务暂不可用，请稍后重试。', sources: [] }; }
        if (!r.image) r.image = '宝塔山';
        r.degraded = true;
        render(r);
      }
    }).catch(function () {
      var r;
      try { r = E.ask(idx, text, mode); } catch (e) { r = { refused: true, text: '网络异常，请重试。', sources: [] }; }
      if (!r.image) r.image = '宝塔山';
      r.degraded = true;
      render(r);
    });
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

  /* ---------------- 配图（本地图 / 联网图都用同一结构） ---------------- */
  function imageSrc(meta) {
    return meta.src || meta.file;
  }

  function imageBlock(meta) {
    var wrap = el('div', 'img-wrap');
    if (!meta || !imageSrc(meta)) return wrap;
    var img = document.createElement('img');
    img.className = 'kb-img';
    img.src = imageSrc(meta);
    img.alt = meta.alt || '';
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer';
    img.onerror = function () {
      // 网络图挂了就退回本地占位，不留白
      if (meta.fallback && img.src.indexOf(meta.fallback) < 0) img.src = meta.fallback;
    };
    img.onclick = function () { openLightbox(meta); };
    wrap.appendChild(img);
    if (meta.credit) wrap.appendChild(el('div', 'img-credit', meta.credit));
    return wrap;
  }

  function openLightbox(meta) {
    var box = $('#lightbox');
    if (!box) return;
    box.innerHTML = '';

    var closeBtn = el('button', 'lb-close', '✕ 关闭');
    closeBtn.setAttribute('aria-label', '关闭大图');
    closeBtn.onclick = function (e) { e.stopPropagation(); closeLightbox(); };
    box.appendChild(closeBtn);

    var img = document.createElement('img');
    img.src = imageSrc(meta);
    img.alt = meta.alt || '';
    img.referrerPolicy = 'no-referrer';
    img.onerror = function () {
      box.innerHTML = '';
      box.appendChild(closeBtn);
      box.appendChild(el('div', 'lb-credit', '图片加载失败，可能已被源站删除。'));
    };
    box.appendChild(img);
    box.appendChild(el('div', 'lb-credit', meta.credit || ''));
    box.appendChild(el('div', 'lb-tip', '点击图片、空白处或右上角关闭'));

    // 点空白处 / 点图片都能关
    box.onclick = function (e) {
      if (e.target === box || e.target.tagName === 'IMG') closeLightbox();
    };
    box.classList.remove('hidden');
    document.addEventListener('keydown', escClose);
  }

  function closeLightbox() {
    var box = $('#lightbox');
    if (!box) return;
    box.classList.add('hidden');
    box.innerHTML = '';
    box.onclick = null;
    document.removeEventListener('keydown', escClose);
  }

  function escClose(e) {
    if (e.key === 'Escape') closeLightbox();
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /* ---------------- 核查结论：知识库只辨真伪 ---------------- */
  var VERDICT = {
    support: { label: '知识库支持', cls: 'ok', hint: '与库内权威记载一致' },
    conflict: { label: '与知识库冲突', cls: 'bad', hint: '以库内来源为准' },
    unknown: { label: '知识库无记载', cls: 'warn', hint: '已联网生成，未见库内佐证' }
  };

  function verdictBlock(v) {
    var meta = VERDICT[v.level] || VERDICT.unknown;
    var box = el('div', 'verdict ' + meta.cls);
    var head = el('div', 'verdict-head');
    head.appendChild(el('span', 'verdict-tag', meta.label));
    head.appendChild(el('span', 'verdict-hint', meta.hint));
    box.appendChild(head);

    if (v.matched && v.matched.length) {
      var list = el('div', 'verdict-list');
      v.matched.forEach(function (m) {
        var it = el('div', 'verdict-item');
        it.appendChild(el('span', 'verdict-q', m.q));
        if (m.cited) it.appendChild(el('span', 'verdict-flag', '已引用'));
        it.onclick = function () { openEntry(m); };
        list.appendChild(it);
      });
      box.appendChild(list);
    }
    if (v.conflicts && v.conflicts.length) {
      var cl = el('div', 'verdict-list');
      v.conflicts.forEach(function (c) {
        var it = el('div', 'verdict-item conflict');
        it.appendChild(el('span', 'verdict-q', '库内：' + (c.entry || c)));
        cl.appendChild(it);
      });
      box.appendChild(cl);
    }
    if (v.note) box.appendChild(el('div', 'verdict-note', v.note));
    return box;
  }

  function openEntry(m) {
    $('#srcTitle').textContent = '知识库条目';
    var box = $('#srcBody');
    box.innerHTML = '';
    var d = el('div', 'src-item');
    d.innerHTML = '<div class="k">问题</div><div class="t">' + esc(m.q) + '</div>' +
      '<div class="k" style="margin-top:8px">知识库记载</div><div class="t">' + esc(m.a || '') + '</div>' +
      (m.sources && m.sources.length ? '<div class="d">来源：' + esc(m.sources[0].org || '') + '《' +
        esc(m.sources[0].doc || '') + '》' + esc(m.sources[0].date || '') + '</div>' : '');
    box.appendChild(d);
    $('#srcMask').classList.remove('hidden');
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
    // 卡片文案走服务端：每次联网现生成，并保证不与历史卡片重复
    api('/api/card', { question: question, answer: r.text, mode: r.mode, image: r.image || '' })
      .then(function (j) {
        if (j && j.ok && j.lines && j.lines.length) {
          r.cardLines = j.lines;
          r.cardId = j.id;
          r.cardSeen = j.seen;
          lastAnswer.r = r;
          drawCard(r, question);
        }
      }).catch(function () {});
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
    var textLines = (r.cardLines && r.cardLines.length) ? r.cardLines : [body.replace(/\n/g, ' ')];
    var used = 0;
    for (var li = 0; li < textLines.length && used < 4; li++) {
      var yBefore = y;
      y = wrap(g, textLines[li], 80, y, 920, 54, Math.min(2, 4 - used));
      used += Math.max(1, Math.round((y - yBefore) / 54));
    }
    y += 20;

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

    // 配图（放在二维码上方，回答有图才画）
    var picTop = H - 80 - 250 - 40 - 300;
    if (cardImg && cardImg.complete && cardImg.naturalWidth && y < picTop - 20) {
      var pw = 560, ph = 300, px0 = W - 80 - pw;
      g.save();
      g.beginPath();
      if (g.roundRect) { g.roundRect(px0, picTop, pw, ph, 14); } else { g.rect(px0, picTop, pw, ph); }
      g.clip();
      // 等比裁剪填充
      var ir = cardImg.naturalWidth / cardImg.naturalHeight, br = pw / ph;
      var sw, sh, sx, sy;
      if (ir > br) { sh = cardImg.naturalHeight; sw = sh * br; sx = (cardImg.naturalWidth - sw) / 2; sy = 0; }
      else { sw = cardImg.naturalWidth; sh = sw / br; sx = 0; sy = (cardImg.naturalHeight - sh) / 2; }
      g.drawImage(cardImg, sx, sy, sw, sh, px0, picTop, pw, ph);
      g.restore();
      g.strokeStyle = '#E7DCD3'; g.lineWidth = 2;
      g.strokeRect(px0, picTop, pw, ph);
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
    if (r.cardLines && r.cardLines.length) {
      var tail = r.sources && r.sources[0]
        ? '（来源：' + r.sources[0].id + ' ' + r.sources[0].org + '《' + r.sources[0].doc + '》' + r.sources[0].date + '）'
        : '（联网实时生成，可扫码核对）';
      return r.cardLines.join('') + tail;
    }
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
    initAuth();
  }

  /* ================= 登录与后台 ================= */
  // 手机通过局域网 IP 打开时不是安全上下文，localStorage 可能直接抛异常：
  // 全部走 memory 兜底，保证登录流程不因存储问题中断。
  var MEM = {};
  var store = {
    get: function (k) {
      try { return window.localStorage.getItem(k); } catch (e) { return MEM[k] || null; }
    },
    set: function (k, v) {
      MEM[k] = v;
      try { window.localStorage.setItem(k, v); } catch (e) { /* 忽略：已有内存副本 */ }
    },
    del: function (k) {
      delete MEM[k];
      try { window.localStorage.removeItem(k); } catch (e) { /* 忽略 */ }
    }
  };
  var token = store.get('hy_token') || '';
  var me = null;

  function api(path, body) {
    var opt = { headers: { 'Content-Type': 'application/json' } };
    if (body) { opt.method = 'POST'; opt.body = JSON.stringify(body); }
    else opt.method = 'GET';
    return fetch(path, opt).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: 'HTTP ' + r.status }; });
    });
  }

  function enterApp() {
    $('#consoleView').classList.add('hidden');
    $('#appView').classList.remove('hidden');
    var allowConsole = true;
    var btn = $('#consoleBtn');
    if (btn) btn.classList.toggle('hidden', !allowConsole);
  }

  function openConsole() {
    $('#appView').classList.add('hidden');
    $('#consoleView').classList.remove('hidden');
    loadTab('dash');
  }

  function loadTab(tab) {
    [].forEach.call($('#consoleTabs').children, function (b) {
      b.classList.toggle('on', b.dataset.tab === tab);
    });
    $('#tab-dash').classList.toggle('hidden', tab !== 'dash');
    $('#tab-logs').classList.toggle('hidden', tab !== 'logs');
    $('#tab-kb').classList.toggle('hidden', tab !== 'kb');
    if (tab === 'dash') loadDash();
    if (tab === 'logs') loadLogs();
    if (tab === 'kb') loadKbConsole();
  }

  function statCard(label, value, note) {
    return '<div class="stat"><div class="stat-v">' + value + '</div>' +
      '<div class="stat-l">' + label + '</div>' +
      (note ? '<div class="stat-n">' + note + '</div>' : '') + '</div>';
  }

  function loadDash() {
    api('/api/console/dashboard').then(function (d) {
      if (!d || d.error) { $('#tab-dash').innerHTML = '<div class="empty">无权访问</div>'; return; }
      var byMode = Object.keys(d.byMode || {}).map(function (k) {
        return '<span class="pill">' + k + ' ' + d.byMode[k] + '</span>';
      }).join('');
      var recent = (d.recent || []).map(function (r) {
        return '<div class="logline"><span class="log-t">' + (r.t || '') + '</span>' +
          '<span class="log-u">' + (r.user || '-') + '</span>' +
          '<span class="log-q">' + esc(r.q || ('[' + (r.event || '') + ']')) + '</span>' +
          '<span class="log-m">' + (r.mode || '') + (r.image ? ' · 图' : '') +
          (r.web ? ' · 联网' : '') + (r.ms ? ' · ' + r.ms + 'ms' : '') + '</span></div>';
      }).join('');
      $('#tab-dash').innerHTML =
        '<div class="section-title">总览</div><div class="stats">' +
        statCard('问答总数', d.total, '日志条数') +
        statCard('配图覆盖率', d.imageRate + '%', d.withImage + ' 条带图') +
        statCard('联网补充率', d.webRate + '%', d.usedWeb + ' 条用了联网') +
        statCard('拒答数', d.refused, '占比 ' + d.refusedRate + '%') +
        statCard('P50 时延', d.p50 + 'ms', 'P90 ' + d.p90 + 'ms') +
        statCard('知识库', (d.kb.count || '-') + ' 条', (d.kb.sources || '-') + ' 个来源 · v' + (d.kb.version || '')) +
        '</div>' +
        '<div class="section-title">模式分布</div><div class="pills">' + (byMode || '<span class="muted">暂无</span>') + '</div>' +
        '<div class="section-title">来源可用性</div><div class="muted">' +
        (d.sourceHealth && d.sourceHealth.total ?
          ('最近校验 ' + d.sourceHealth.checked + '：' + d.sourceHealth.ok + '/' + d.sourceHealth.total + ' 可打开') :
          '尚未校验') + '</div>' +
        '<div class="section-title">最近提问</div><div class="loglist">' + (recent || '<div class="muted">暂无</div>') + '</div>';
    });
  }

  function loadLogs() {
    api('/api/console/logs?limit=100').then(function (d) {
      var rows = (d.logs || []).map(function (r) {
        return '<tr><td>' + (r.t || '') + '</td><td>' + (r.user || '-') + '</td><td class="q">' +
          esc(r.q || ('[' + (r.event || '') + ']')) + '</td><td>' + (r.mode || '') + '</td><td>' +
          (r.kb ? (Array.isArray(r.kb) ? r.kb.join(',') : r.kb) : '') + '</td><td>' +
          (r.image || '') + '</td><td>' + (r.web ? '是' : '') + '</td><td>' + (r.ms || '') + '</td></tr>';
      }).join('');
      $('#tab-logs').innerHTML = '<div class="section-title">提问日志（最近 100 条）</div>' +
        '<div class="table-wrap"><table class="log-table"><thead><tr><th>时间</th><th>账号</th><th>问句</th>' +
        '<th>模式</th><th>命中</th><th>配图</th><th>联网</th><th>ms</th></tr></thead><tbody>' +
        (rows || '<tr><td colspan="8" class="muted">暂无记录</td></tr>') + '</tbody></table></div>';
    });
  }

  function loadKbConsole() {
    api('/api/console/kb').then(function (kb) {
      var rows = (kb.entries || []).map(function (e) {
        var s = (e.sources || [{}])[0];
        return '<tr><td>' + e.id + '</td><td class="q">' + esc(e.q) + '</td><td class="q">' +
          esc(String(e.a || '').slice(0, 60)) + '…</td><td>' + (e.kind || '') + '</td><td>' +
          (e.image || '') + '</td><td>' + esc(s.org || '') + '<br><span class="muted">' + esc(s.date || '') + '</span></td></tr>';
      }).join('');
      $('#tab-kb').innerHTML = '<div class="section-title">知识库 · ' + kb.count + ' 条 / ' + kb.sources +
        ' 个来源 · v' + kb.version + '</div>' +
        '<div class="table-wrap"><table class="log-table"><thead><tr><th>编号</th><th>问题</th><th>标准回答</th>' +
        '<th>类型</th><th>配图</th><th>来源</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    });
  }

  // 静态托管（GitHub Pages）时没有 /api：提示用 Render 地址，而不是把用户卡在登录页
  function staticFallback() {
    var box = document.querySelector('.login-form');
    if (!box || box.querySelector('.static-note')) return;
    var n = document.createElement('div');
    n.className = 'static-note';
    n.innerHTML = '当前是静态页面（无后端）。语音/账号/联网生成请访问 ' +
      '<a href="https://hongji-yanan.onrender.com" target="_blank" rel="noopener">hongji-yanan.onrender.com</a>。';
    box.appendChild(n);
  }

  function initAuth() {
    bindAuth();
    enterApp();
    if ($('#consoleWho')) $('#consoleWho').textContent = '设计者视图';
    if ($('#statusHint')) $('#statusHint').textContent = 'DeepSeek 联网生成中…';
  }

  function bindAuth() {
    // 隐藏入口：连点页脚文字 5 次，或地址栏加 #admin
    var taps = 0, timer = null;
    var dot = $('#secretDot');
    if (dot) {
      dot.onclick = function () {
        taps++;
        clearTimeout(timer);
        timer = setTimeout(function () { taps = 0; }, 1600);
        if (taps >= 5) { taps = 0; openConsole(); }
      };
    }
    if (location.hash === '#admin') openConsole();
    var back = $('#backBtn');
    if (back) back.onclick = function () {
      $('#consoleView').classList.add('hidden');
      $('#appView').classList.remove('hidden');
    };
    var cb = $('#consoleBtn');
    if (cb) cb.onclick = openConsole;
    var tabs = $('#consoleTabs');
    if (tabs) tabs.addEventListener('click', function (e) {
      var b = e.target.closest('.mode');
      if (b) loadTab(b.dataset.tab);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
