# -*- coding: utf-8 -*-
"""问答卡：联网文案 + 配图。"""

import io
import re

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\web\app.js"
s = io.open(P, encoding="utf-8").read()

# 1) openCard：拉取服务端生成的不重复文案
old_open = """  function openCard(r, question) {
    lastAnswer = { r: r, q: question };
    drawCard(r, question);
    $('#cardMask').classList.remove('hidden');
  }"""
new_open = """  function openCard(r, question) {
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
  }"""
if "api('/api/card'" not in s:
    assert old_open in s, "openCard anchor missing"
    s = s.replace(old_open, new_open)

# 2) 正文：优先用服务端文案（多行）
old_body = """    g.fillStyle = '#3A2E29';
    g.font = '400 34px "PingFang SC","Microsoft YaHei",sans-serif';
    var body = r.text || r.raw || '';
    y = wrap(g, body.replace(/\\n/g, ' '), 80, y, 920, 54, 5) + 26;"""
new_body = """    g.fillStyle = '#3A2E29';
    g.font = '400 34px "PingFang SC","Microsoft YaHei",sans-serif';
    var body = r.text || r.raw || '';
    var textLines = (r.cardLines && r.cardLines.length) ? r.cardLines : [body.replace(/\\n/g, ' ')];
    var used = 0;
    for (var li = 0; li < textLines.length && used < 4; li++) {
      var yBefore = y;
      y = wrap(g, textLines[li], 80, y, 920, 54, Math.min(2, 4 - used));
      used += Math.max(1, Math.round((y - yBefore) / 54));
    }
    y += 20;"""
if "var textLines = (r.cardLines" not in s:
    assert old_body in s, "body anchor missing"
    s = s.replace(old_body, new_body)

# 3) 卡片文案复制也带上生成结果
old_text = """  function cardText(r, q) {
    var s = r.sources && r.sources[0];"""
new_text = """  function cardText(r, q) {
    if (r.cardLines && r.cardLines.length) {
      var tail = r.sources && r.sources[0]
        ? '（来源：' + r.sources[0].id + ' ' + r.sources[0].org + '《' + r.sources[0].doc + '》' + r.sources[0].date + '）'
        : '（联网实时生成，可扫码核对）';
      return r.cardLines.join('') + tail;
    }
    var s = r.sources && r.sources[0];"""
if "if (r.cardLines && r.cardLines.length) {" not in s.split("function cardText")[1][:200]:
    assert old_text in s, "cardText anchor missing"
    s = s.replace(old_text, new_text)

io.open(P, "w", encoding="utf-8").write(s)
print("card patched:", "api('/api/card'" in s, "textLines" in s, "cardLines.join" in s)
