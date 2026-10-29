# -*- coding: utf-8 -*-
"""红迹·延安 —— 本地服务（标准库，无依赖）。

  python run.py            → http://127.0.0.1:8788
  python run.py --port 9000 --host 0.0.0.0

路由：
  /                 前端页面（web/index.html）
  /api/kb           知识库（每次现读 data/kb.json，外部同步后页面自动热更新）
  /api/version      轻量版本号
  /api/log          POST 记录一次问答（用于测试统计）
  /api/selftest     自测结果（docs/selftest.json）
"""
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")
LOCK = threading.Lock()


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ---------------- 大模型（可选）：Key 只从环境变量或 data/config.json 读，绝不进仓库 ----------------
CFG_PATH = os.path.join(DATA, "config.json")
DEFAULT_BASE = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-flash"


def llm_config():
    cfg = read_json(CFG_PATH, {}) or {}
    key = os.environ.get("DEEPSEEK_API_KEY") or cfg.get("api_key") or ""
    return {
        "key": key.strip(),
        "model": os.environ.get("DEEPSEEK_MODEL") or cfg.get("model") or MODEL,
        "url": os.environ.get("DEEPSEEK_URL") or cfg.get("url") or DEFAULT_BASE,
    }


MODE_HINT = {
    "fact": "史实问答：先给结论，再补一句解释；3—5 句，不超过 120 字。",
    "research": "研学讲解词：按「看什么／为什么重要／想一想」三段写，每段一到两句，最后给一个学生能现场观察的问题。",
    "moment": "朋友圈一句话：一行以内、不超过 60 字，句末带 #延安红色之旅，不用「震惊／必看／天花板」这类词。",
}

SYSTEM = (
    "你是延安的 AI 讲解员「延小讲」。下面给你一条**已核对过的知识库答案**和对应问题。"
    "你的任务只是把它改写成指定模式，不得增删任何事实。\n"
    "硬规则：\n"
    "1. 只能使用给定答案里的事实，不得引入任何新的数字、日期、人名、地名、事件、评价。\n"
    "2. 所有数字、日期、专有名词必须逐字保留，不换算、不约整、不补充。\n"
    "3. 不加感叹、不加营销词、不写「作为AI」「希望以上回答」这类话。\n"
    "4. 如果给定答案本身是拒答或边界说明，原样输出，不要改写、不要软化。\n"
    "5. 只输出改写后的正文，不要解释过程。\n"
    "6. 一律使用简体中文，不得输出繁体字；不得使用 Markdown 标记（如 **、##、-）。"
)

# 常见繁体字（用于拦截模型漂移；命中 2 个以上就不采用改写结果，退回知识库原文）
TRAD = set("個這說時為國會後學實現點東車馬長門問間樣麼幾還開關頭區單獨風飛書筆義傳體聲廣場廠條"
           "務員親愛歡迎歲歷應當與軍農業產黨團鐵銀錢買賣讀寫聽讓認識記憶約級給華萬億兩隻雙對錯難"
           "簡據處證灣醫療藝術範圍導遊覽資訊網絡聯繫電話號碼")


def _numbers(s):
    return set(re.findall(r"\d+(?:\.\d+)?", s or ""))


def call_llm(cfg, question, answer, mode, force_short=False):
    if not cfg["key"]:
        return None, "no_key"
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "问题：%s\n输出模式：%s\n知识库答案：%s%s" %
                                        (question, MODE_HINT.get(mode, MODE_HINT["fact"]), answer,
                                         "\n（只输出一句话，20—50 字，不要任何前缀）" if force_short else "")},
        ],
        "temperature": 0.7 if force_short else 0.3,
        "max_tokens": 520,
        "stream": False,
    }
    req = urllib.request.Request(
        cfg["url"], data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + cfg["key"]},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
    usage = data.get("usage", {})

    out = re.sub(r"(?m)^\s*#{1,6}\s*", "", out).replace("**", "")
    out = "\n".join(ln.strip(" -·\t") if ln.strip().startswith(("-", "·")) else ln.strip()
                    for ln in out.splitlines()).strip()

    if not out:
        return None, "empty"
    # 繁体漂移：命中两个以上就不采用
    if len(set(out) & TRAD) >= 2:
        return None, "traditional_chars:" + "".join(sorted(set(out) & TRAD))[:6]
    # 事实护栏：改写里不能出现答案里没有的数字
    extra = _numbers(out) - _numbers(answer)
    if extra:
        return None, "ungrounded:" + ",".join(sorted(extra)[:5])
    if len(out) > max(360, len(answer) * 3 + 120):
        return None, "too_long"
    return {"text": out, "ms": int((time.time() - t0) * 1000),
            "tokens": usage.get("total_tokens"), "model": cfg["model"]}, None


class Handler(SimpleHTTPRequestHandler):
    server_version = "HongjiYanan/1.0"

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB, **kw)

    def log_message(self, fmt, *args):  # 静音默认访问日志
        pass

    def _json(self, obj, code=200, cache="no-store"):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        if self.path.endswith((".js", ".css", ".html")) or self.path in ("/", ""):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/kb":
            kb = read_json(os.path.join(DATA, "kb.json"), {})
            return self._json(kb)
        if path == "/api/version":
            kb = read_json(os.path.join(DATA, "kb.json"), {})
            return self._json({"version": kb.get("version"), "updated": kb.get("updated")})
        if path == "/api/selftest":
            return self._json(read_json(os.path.join(DOCS, "selftest.json"), {}))
        if path == "/api/capabilities":
            cfg = llm_config()
            kb = read_json(os.path.join(DATA, "kb.json"), {})
            return self._json({
                "llm": bool(cfg["key"]), "model": cfg["model"] if cfg["key"] else None,
                "kb": {"count": kb.get("count"), "sources": kb.get("sources"), "version": kb.get("version")},
            })
        if path == "/api/health":
            return self._json({"ok": True, "t": int(time.time())})
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path not in ("/api/log", "/api/chat"):
            return self._json({"ok": False}, 404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return self._json({"ok": False}, 400)

        if path == "/api/chat":
            q = str(body.get("question") or "")[:300]
            a = str(body.get("answer") or "")[:2000]
            mode = str(body.get("mode") or "fact")
            if not q or not a:
                return self._json({"ok": False, "error": "empty"}, 400)
            cfg = llm_config()
            try:
                out, err = call_llm(cfg, q, a, mode)
                if not out and err == "empty":
                    out, err = call_llm(cfg, q, a, mode, force_short=True)
            except Exception as e:
                out, err = None, type(e).__name__ + ":" + str(e)[:120]
            if not out:
                return self._json({"ok": False, "fallback": True, "error": err}, 200)
            self._append_log({"q": q, "mode": mode, "id": body.get("id"), "refused": False,
                              "score": body.get("score") or 0, "llm": out["model"],
                              "ms": out["ms"], "tokens": out["tokens"]})
            return self._json({"ok": True, "answer": out["text"], "model": out["model"],
                               "ms": out["ms"], "tokens": out["tokens"]})

        rec = {
            "t": time.strftime("%Y-%m-%d %H:%M:%S"),
            "q": str(body.get("q", ""))[:120],
            "mode": body.get("mode"),
            "id": body.get("id"),
            "refused": bool(body.get("refused")),
            "score": round(float(body.get("score") or 0), 3),
            "ip": self.client_address[0],
        }
        self._append_log(rec)
        return self._json({"ok": True})

    def _append_log(self, rec):
        rec = dict(rec)
        rec.setdefault("t", time.strftime("%Y-%m-%d %H:%M:%S"))
        rec.setdefault("ip", self.client_address[0])
        os.makedirs(DATA, exist_ok=True)
        with LOCK:
            with open(os.path.join(DATA, "usage.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    port = 8788
    host = "0.0.0.0"
    args = sys.argv[1:]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    if "--host" in args:
        host = args[args.index("--host") + 1]
    srv = ThreadingHTTPServer((host, port), Handler)
    print("红迹·延安 已启动：")
    print("  本机   http://127.0.0.1:%d" % port)
    for ip in _lan_ips():
        print("  局域网 http://%s:%d   （手机扫码用这个）" % (ip, port))
    print("Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


def _lan_ips():
    import socket
    out = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("223.5.5.5", 80))
        out.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return out


if __name__ == "__main__":
    main()
