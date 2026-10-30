# -*- coding: utf-8 -*-
"""前端：党员电子导览改为分段播放（含语音朗读）。"""

import io

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\web\learn.js"
s = io.open(P, encoding="utf-8").read()

# 1) 替换 renderTask 里的 party 渲染
old_head = """    var script = $('#partyScript');
    if (task.script) {
      script.classList.remove('hidden');
      script.textContent = task.script;
    } else script.classList.add('hidden');"""
new_head = """    var script = $('#partyScript');
    if (task.mode === 'party' && task.tour && task.tour.length) {
      script.classList.remove('hidden');
      renderTour(task.tour);
    } else {
      script.classList.add('hidden');
      script.innerHTML = '';
      stopSpeak();
    }"""
assert old_head in s, "party script 锚点缺失"
s = s.replace(old_head, new_head, 1)

# 2) 插入导览渲染与朗读逻辑
helper = r"""
  /* ---------------- 电子导览：分段播放 ---------------- */
  var tourState = { list: [], i: 0, timer: null, speaking: false };

  function stopSpeak() {
    try { if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch (e) {}
    tourState.speaking = false;
  }

  function speak(text) {
    if (!window.speechSynthesis) { toast('当前浏览器不支持朗读，可阅读文字'); return; }
    try {
      window.speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(text);
      u.lang = 'zh-CN';
      u.rate = 0.95;
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
    tourState.list = tour;
    tourState.i = 0;
    var box = $('#partyScript');
    box.innerHTML = '';

    var head = document.createElement('div');
    head.className = 'tour-head';
    head.innerHTML = '<span class="tour-badge">电子导览</span>' +
      '<span class="tour-count" id="tourCount"></span>';
    box.appendChild(head);

    var body = document.createElement('div');
    body.className = 'tour-body';
    body.id = 'tourBody';
    box.appendChild(body);

    var bar = document.createElement('div');
    bar.className = 'tour-bar';
    bar.innerHTML = '<button class="tour-btn" id="tourPrev">上一段</button>' +
      '<button class="tour-btn main" id="tourSpeak">▶ 朗读本段</button>' +
      '<button class="tour-btn" id="tourNext">下一段</button>';
    box.appendChild(bar);

    var tip = document.createElement('div');
    tip.className = 'tour-tip';
    tip.textContent = '跟读或默读都可以；听完再点「领判断题」。';
    box.appendChild(tip);

    $('#tourPrev').onclick = function () { goTour(-1); };
    $('#tourNext').onclick = function () { goTour(1); };
    $('#tourSpeak').onclick = function () {
      if (tourState.speaking) { stopSpeak(); syncSpeakBtn(); return; }
      var seg = tourState.list[tourState.i];
      if (seg) speak(seg[0] + '。' + seg[1]);
    };
    showTourSegment(0, true);
  }

  function goTour(d) {
    var n = tourState.i + d;
    if (n < 0) { toast('已经是第一段'); return; }
    if (n >= tourState.list.length) { toast('导览已结束，可以领判断题了'); return; }
    showTourSegment(n, true);
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
    if (autoSpeak) speak(seg[0] + '。' + seg[1]);
  }
"""
anchor = "  function renderTask(task) {"
assert anchor in s, "renderTask 锚点缺失"
s = s.replace(anchor, helper + "\n" + anchor, 1)

# 3) 切换点位/离开时停止朗读
s = s.replace("  function show(id) {", "  function show(id) {\n    if (id !== 'stepTask') stopSpeak();")

io.open(P, "w", encoding="utf-8").write(s)
print("电子导览前端已更新")
