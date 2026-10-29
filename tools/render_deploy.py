# -*- coding: utf-8 -*-
"""Render 部署脚本（幂等）：修正启动命令 → 确保 Key → 触发部署 → 等待 live。

用法：
  set RND=rnd_xxx
  set DSK=sk-xxx            （可选，缺省则保留已有环境变量）
  python tools/render_deploy.py --service srv-xxx
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.render.com/v1"
TOKEN = os.environ.get("RND", "").strip()
START = "python run.py --port $PORT"
BUILD = "python -V"


def call(method, path, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        API + path, data=body, method=method,
        headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/json",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as x:
            raw = x.read()
            return x.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:400].decode("utf-8", "ignore")


def main():
    if not TOKEN:
        sys.exit("缺少 RND 环境变量（Render API Key）")
    sid = "srv-dbhhf15g1s2s73a3jvp0"
    args = sys.argv[1:]
    if "--service" in args:
        sid = args[args.index("--service") + 1]

    s, svc = call("GET", "/services/" + sid)
    if s != 200:
        sys.exit("拿不到服务：%s %s" % (s, svc))
    print("服务：", svc["name"], svc["serviceDetails"]["url"])

    cur = svc["serviceDetails"].get("envSpecificDetails", {})
    if cur.get("startCommand") != START:
        s, r = call("PATCH", "/services/" + sid, {
            "serviceDetails": {"envSpecificDetails": {"buildCommand": BUILD, "startCommand": START}}})
        print("修正启动命令：", s, r if s >= 300 else "ok")

    key = os.environ.get("DSK", "").strip()
    if key:
        s, ev = call("PUT", "/services/%s/env-vars" % sid,
                     [{"key": "DEEPSEEK_API_KEY", "value": key}])
        print("写入 DEEPSEEK_API_KEY：", s)

    s, dp = call("POST", "/services/%s/deploys" % sid, {"clearCache": "clear"})
    dep_id = (dp or {}).get("id") if isinstance(dp, dict) else None
    print("触发部署：", s, dep_id or dp)

    url = svc["serviceDetails"]["url"]
    status = ""
    for i in range(60):
        time.sleep(10)
        s, d = call("GET", "/services/%s/deploys/%s" % (sid, dep_id)) if dep_id else (0, {})
        st = (d or {}).get("status", "")
        if st != status:
            print("  %02d %s" % (i, st))
            status = st
        if st == "live":
            break
        if st in ("build_failed", "update_failed", "canceled", "deactivated"):
            print("部署失败：", json.dumps(d, ensure_ascii=False)[:600])
            break

    print("结果：", status, url)
    if status != "live":
        s, d = call("GET", "/services/%s/deploys/%s/events" % (sid, dep_id))
        print("事件：", str(d)[:800])


if __name__ == "__main__":
    main()
