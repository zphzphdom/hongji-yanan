# -*- coding: utf-8 -*-
"""知识库联网校验：逐条打开来源链接，记录可达性与校验时间。

  python tools/sync_kb.py            一次性校验
  python tools/sync_kb.py --watch 6  每 6 小时校验一次

只写 data/kb_health.json，不改 kb.json，因此不会因为"校验过"而无谓改变版本号；
内容真变了，再由 build/build_kb.py 重新生成并升版本。
"""
import json
import os
import ssl
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, "data", "kb.json")
HEALTH = os.path.join(ROOT, "data", "kb_health.json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; HongjiYanan/1.0; +local)"}
CTX = ssl.create_default_context()


def check(url, timeout=15):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            r.read(2048)
            code = r.status
        return {"ok": 200 <= code < 400, "code": code, "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "code": None, "ms": int((time.time() - t0) * 1000), "err": type(e).__name__}


def run_once():
    kb = json.load(open(KB, encoding="utf-8"))
    src = kb.get("sourceIndex", {})
    urls = [(sid, s["url"]) for sid, s in src.items() if s.get("url")]
    print("校验 %d 个来源…" % len(urls))
    results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(check, u): (sid, u) for sid, u in urls}
        for f in futs:
            sid, u = futs[f]
            results[sid] = f.result()
            r = results[sid]
            print("  %s %-4s %5sms  %s" % (sid, r["code"] or "ERR", r["ms"], u[:70]))

    ok = sum(1 for v in results.values() if v["ok"])
    payload = {
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kb_version": kb.get("version"),
        "total": len(urls),
        "ok": ok,
        "failed": len(urls) - ok,
        "results": results,
    }
    old = {}
    try:
        old = json.load(open(HEALTH, encoding="utf-8"))
    except Exception:
        pass
    hist = old.get("history", [])[-29:] + [{"at": payload["checked_at"], "ok": ok, "total": len(urls)}]
    payload["history"] = hist
    with open(HEALTH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("可打开 %d/%d，结果写入 data/kb_health.json" % (ok, len(urls)))
    return ok, len(urls)


def main():
    if "--watch" in sys.argv:
        hours = float(sys.argv[sys.argv.index("--watch") + 1])
        while True:
            try:
                run_once()
            except Exception as e:
                print("校验失败：", e)
            time.sleep(hours * 3600)
    else:
        run_once()


if __name__ == "__main__":
    main()
