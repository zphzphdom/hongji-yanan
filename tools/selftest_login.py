# -*- coding: utf-8 -*-
"""登录流程自测：错误提示是否真的返回给前端（校验后端状态码与文案）。"""
import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788"


def login(u, p):
    r = urllib.request.Request(BASE + "/api/login",
                               data=json.dumps({"username": u, "password": p}).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


cases = [
    ("错误密码", "demo", "wrongpass", 401),
    ("不存在的账号", "nobody", "x", 401),
    ("空账号", "", "x", 401),
    ("demo 正确", "demo", "demo2026", 200),
    ("judge 正确", "judge", "judge2026", 200),
]

ok = True
for name, u, p, want in cases:
    s, body = login(u, p)
    good = s == want
    ok = ok and good
    msg = body.get("error") or body.get("role") or ""
    print("%-12s HTTP %d（期望 %d）%s  提示：%s" % (name, s, want, "✓" if good else "✗", msg))

print("\n结果：", "通过" if ok else "未通过")
sys.exit(0 if ok else 1)
