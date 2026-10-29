# -*- coding: utf-8 -*-
"""端到端自测：账号权限、三种模式、每答必图、延迟、后台数据。

python tools/selftest_e2e.py [--base http://127.0.0.1:8788] [--n 12]
"""
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8788"
N = 12
args = sys.argv[1:]
if "--base" in args:
    BASE = args[args.index("--base") + 1].rstrip("/")
if "--n" in args:
    N = int(args[args.index("--n") + 1])

CASES = [
    ("宜川花椒有什么特点？", "fact"),
    ("南泥湾大生产运动是怎么回事？", "research"),
    ("宝塔山为什么是延安的象征？", "moment"),
    ("子长粉条怎么吃？", "fact"),
    ("党的七大是什么时候开的？", "research"),
    ("壶口瀑布值得去吗？", "moment"),
    ("延安有哪些 5A 级景区？", "fact"),
    ("黄龙核桃好在哪里？", "research"),
    ("从西安到延安怎么走最快？", "moment"),
    ("延安有多少地理标志产品？", "fact"),
    ("杨家岭有什么标志性建筑？", "research"),
    ("清凉山为什么被称为红色新闻山？", "moment"),
]


def req(path, body=None, token=None, timeout=60):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=h,
                               method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as x:
            return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def main():
    out = {"base": BASE}

    # 1) 权限
    s_anon, _ = req("/api/console/dashboard")
    s_bad, _ = req("/api/login", {"username": "demo", "password": "x"})
    s_demo, demo = req("/api/login", {"username": "demo", "password": "demo2026"})
    s_judge, judge = req("/api/login", {"username": "judge", "password": "judge2026"})
    tok = demo.get("token")
    perm = {
        "anonConsole": s_anon,
        "badPassword": s_bad,
        "demoLogin": s_demo,
        "judgeLogin": s_judge,
        "demoAllow": demo.get("allow"),
        "judgeAllow": judge.get("allow"),
    }

    # 2) 后台
    console = {}
    for name, path in [("dashboard", "/api/console/dashboard"),
                       ("logs", "/api/console/logs?limit=20"),
                       ("kb", "/api/console/kb")]:
        s, d = req(path, token=tok)
        console[name] = {"status": s, "ok": s == 200}

    # 3) 三种模式 + 每答必图
    rows, imgs, ms, llm_ms, degraded = [], {}, [], [], 0
    for i in range(min(N, len(CASES))):
        q, mode = CASES[i % len(CASES)]
        t0 = time.time()
        s, d = req("/api/ask", {"question": q, "mode": mode}, token=tok, timeout=90)
        wall = int((time.time() - t0) * 1000)
        ms.append(wall)
        if d.get("llmMs"):
            llm_ms.append(d["llmMs"])
        if d.get("degraded"):
            degraded += 1
        imgs[d.get("image") or "NONE"] = imgs.get(d.get("image") or "NONE", 0) + 1
        rows.append({
            "q": q, "mode": mode, "status": s, "wallMs": wall,
            "llmMs": d.get("llmMs"), "model": d.get("model"),
            "image": d.get("image"), "imageSource": d.get("imageSource"),
            "usedWeb": d.get("usedWeb"), "usedKB": d.get("usedKB"),
            "degraded": d.get("degraded"), "len": len(d.get("text") or ""),
        })

    # 4) 图片真的能取到
    img_ok, img_bad = 0, []
    for name in list(imgs):
        if name == "NONE":
            continue
        try:
            r = urllib.request.urlopen(BASE + "/images/" + urllib.parse.quote(name) + ".webp", timeout=20)
            r.read()
            img_ok += 1
        except Exception:
            img_bad.append(name)

    ok_status = all(r["status"] == 200 for r in rows)
    ok_img = all(r["image"] for r in rows)
    ok_mode = all(r["mode"] in ("fact", "research", "moment") for r in rows)
    ok_len = all(r["len"] > 10 for r in rows)

    out.update({
        "permissions": perm,
        "console": console,
        "answers": rows,
        "imageUse": imgs,
        "imageFiles": {"ok": img_ok, "bad": img_bad},
        "latency": {
            "wallP50": int(statistics.median(ms)) if ms else 0,
            "wallMax": max(ms) if ms else 0,
            "llmP50": int(statistics.median(llm_ms)) if llm_ms else 0,
            "llmMax": max(llm_ms) if llm_ms else 0,
        },
        "degraded": degraded,
        "pass": bool(
            s_anon == 401 and s_bad == 401 and s_demo == 200 and s_judge == 200
            and all(v["ok"] for v in console.values())
            and ok_status and ok_img and ok_mode and ok_len and not img_bad
            and degraded == 0
        ),
    })
    print(json.dumps(out, ensure_ascii=False, indent=1))
    with open("docs/selftest_e2e.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    sys.exit(0 if out["pass"] else 1)


if __name__ == "__main__":
    main()
