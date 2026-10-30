# -*- coding: utf-8 -*-
"""去掉账号密码登录：问答页直接可用；后台改为隐藏入口，免登录但不可被轻易发现。

改三处：
  1. index.html：删除登录面板，app 视图默认可见，页脚加隐藏触发点
  2. app.js：去掉登录流程，改为启动即进入问答；后台用暗号进入
  3. server.py：/api/console/* 不再要求登录
"""

import io
import re

ROOT = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan"

# ---------------------------------------------------------------- 1. index.html
P_HTML = ROOT + r"\web\index.html"
h = io.open(P_HTML, encoding="utf-8").read()

# 删除整块登录面板
h2 = re.sub(r"<!-- 登录 -->\s*<div class=\"login\" id=\"loginView\">.*?\n</div>\n\n", "", h, flags=re.S)
if h2 == h:  # 兜底：按 id 区间删
    start = h.find('<div class="login" id="loginView">')
    if start > 0:
        end = h.find("<!-- 应用 -->", start)
        h2 = h[:start] + h[end:]
h = h2

# app 视图默认可见
h = h.replace('<div class="app hidden" id="appView">', '<div class="app" id="appView">')

# 顶栏：去掉"后台"和"退出"按钮，只保留隐藏触发的关于点
h = h.replace(
    '<div class="top-actions">\n        <button class="ghost-btn" id="consoleBtn">后台</button>\n'
    '        <button class="icon-btn" id="logoutBtn" aria-label="退出">⎋</button>\n      </div>',
    '<div class="top-actions">\n        <a class="ghost-btn" href="/learn.html">点位学习</a>\n      </div>')

# 页脚加隐藏触发点（连点 5 次进入后台）
h = h.replace(
    '<div class="hint" id="statusHint">DeepSeek 生成中…</div>',
    '<div class="hint" id="statusHint">DeepSeek 生成中…</div>\n'
    '    <div class="hint" id="secretDot" title="">红迹·延安 · 1935—1948</div>')

io.open(P_HTML, "w", encoding="utf-8").write(h)
print("index.html：登录面板已移除 =", 'id="loginView"' not in h,
      "| app 默认可见 =", '<div class="app" id="appView">' in h,
      "| 隐藏触发点 =", 'id="secretDot"' in h)

# ---------------------------------------------------------------- 2. app.js
P_JS = ROOT + r"\web\app.js"
s = io.open(P_JS, encoding="utf-8").read()

# api：不再带 token，也不再因 401 跳登录
s = re.sub(
    r"  function api\(path, body, opts\) \{.*?\n  \}\n",
    """  function api(path, body) {
    var opt = { headers: { 'Content-Type': 'application/json' } };
    if (body) { opt.method = 'POST'; opt.body = JSON.stringify(body); }
    else opt.method = 'GET';
    return fetch(path, opt).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: 'HTTP ' + r.status }; });
    });
  }
""", s, count=1, flags=re.S)

# 删除登录相关函数
for fn in ("showLogin", "setLoginError"):
    s = re.sub(r"  function %s\([^)]*\) \{.*?\n  \}\n\n?" % fn, "", s, count=1, flags=re.S)

# showApp 改成 enterApp：无账号
s = re.sub(
    r"  function showApp\(user\) \{.*?\n  \}\n",
    """  function enterApp() {
    $('#consoleView').classList.add('hidden');
    $('#appView').classList.remove('hidden');
    var allowConsole = true;
    var btn = $('#consoleBtn');
    if (btn) btn.classList.toggle('hidden', !allowConsole);
  }
""", s, count=1, flags=re.S)

# doLogin 整个删掉，bindAuth 重写
s = re.sub(r"  function doLogin\(\) \{.*?\n  \}\n\n?", "", s, count=1, flags=re.S)
s = re.sub(
    r"  function bindAuth\(\) \{.*?\n  \}\n",
    """  function bindAuth() {
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
""", s, count=1, flags=re.S)

# initAuth：直接进应用
s = re.sub(
    r"  function initAuth\(\) \{.*?\n  \}\n",
    """  function initAuth() {
    bindAuth();
    enterApp();
    if ($('#consoleWho')) $('#consoleWho').textContent = '设计者视图';
    if ($('#statusHint')) $('#statusHint').textContent = 'DeepSeek 联网生成中…';
  }
""", s, count=1, flags=re.S)

# 移除静态托管提示分支（已无登录）
s = re.sub(r"    if \(location\.hostname\.endsWith\('github\.io'\)\) \{[^}]*\}\n", "", s)

io.open(P_JS, "w", encoding="utf-8").write(s)
print("app.js：登录流程已移除 =", "doLogin" not in s and "showLogin" not in s,
      "| 隐藏入口 =", "secretDot" in s)

# ---------------------------------------------------------------- 3. server.py
P_PY = ROOT + r"\server.py"
p = io.open(P_PY, encoding="utf-8").read()
old = """    def _need(self, allow="console"):
        u = whoami(self)
        if not u:
            self._json({"ok": False, "error": "unauthorized"}, 401)
            return None
        if allow not in u["allow"] and not u["admin"]:
            self._json({"ok": False, "error": "forbidden"}, 403)
            return None
        return u"""
new = """    def _need(self, allow="console"):
        # 后台改为隐藏入口：不校验账号，任何人拿到入口都能看（只读）
        return {"user": "designer", "role": "admin", "admin": True, "allow": ["chat", "console"]}"""
assert old in p, "server _need 锚点未找到"
p = p.replace(old, new, 1)
io.open(P_PY, "w", encoding="utf-8").write(p)
import ast
ast.parse(p)
print("server.py：后台免登录 =", "不再校验账号" in p)
