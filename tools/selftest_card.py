# -*- coding: utf-8 -*-
"""问答卡 / 联网图 / 关键词 自测：python tools/selftest_card.py [base]"""

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788"


def req(path, body=None, token=None, timeout=90):
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
        return e.code, json.loads(e.read() or b"{}")


def main():
    s, j = req("/api/login", {"username": "demo", "password": "demo2026"})
    tok = j.get("token")

    print("— 关键词与联网图 —")
    kw_ok = img_ok = 0
    for q in ["宜川花椒有什么特点？", "宝塔山雪后是什么样", "子长粉条怎么吃", "黄龙核桃好在哪里"]:
        s, r = req("/api/ask", {"question": q, "mode": "fact"}, tok)
        kws = r.get("keywords") or []
        url = r.get("imageUrl") or ""
        good_kw = bool(kws) and not any(w in " ".join(kws) for w in ("什么", "怎么", "哪里"))
        if good_kw:
            kw_ok += 1
        if url:
            img_ok += 1
        print("  %-20s 关键词=%s" % (q[:18], kws))
        print("  %-20s 图片=%s" % ("", (url or "本地图")[:70]))

    print("\n— 卡片文案去重（同一问题连发 5 次）—")
    q, a = "子长粉条怎么吃", "子长粉条可炒烩炸烧，耐煮不耐焖，先用开水焖5到10分钟。"
    lines, uniq = [], 0
    for i in range(5):
        s, c = req("/api/card", {"question": q, "answer": a, "mode": "moment"}, tok)
        txt = "|".join(c.get("lines") or [])
        lines.append(txt)
        if txt not in lines[:-1]:
            uniq += 1
        print("  %d. %s" % (i + 1, (txt or "空")[:60]))

    ok = kw_ok >= 3 and img_ok >= 1 and uniq == 5
    print("\n关键词合格 %d/4 ｜ 拿到网络图 %d/4 ｜ 卡片唯一 %d/5" % (kw_ok, img_ok, uniq))
    print("结果：", "通过" if ok else "未通过")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
