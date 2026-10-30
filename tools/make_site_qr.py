# -*- coding: utf-8 -*-
"""为每个点位生成专属二维码（扫码直达该点位学习页）。

用法：python tools/make_site_qr.py https://hongji-yanan.onrender.com
产物：qrcodes/site-P1.png …… site-P6.png，以及一张索引图
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import qr_local  # noqa: E402
import selftest_qr  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://hongji-yanan.onrender.com"
OUT = os.path.join(ROOT, "qrcodes")
DATA = os.path.join(ROOT, "data", "sites.json")


def main():
    sites = json.load(open(DATA, encoding="utf-8"))["sites"]
    os.makedirs(OUT, exist_ok=True)
    index = []
    bad = 0
    for s in sites:
        # 带 site 参数直达点位；版本 1—4 已核对，短链接保证落在可用区间
        url = "%s/learn.html?site=%s" % (BASE.rstrip("/"), s["id"])
        path = os.path.join(OUT, "site-%s.png" % s["id"])
        try:
            info = qr_local.save_png(path, url, scale=10, border=4)
        except Exception as e:
            print("  %s 生成失败：%s" % (s["name"], e))
            bad += 1
            continue
        ok, msg, det = selftest_qr.check(url)
        if not ok:
            bad += 1
        index.append({"site": s["id"], "name": s["name"], "url": url, "file": os.path.basename(path),
                      "version": det.get("version"), "verify": ok})
        print("  %-12s 版本%s %s  校验=%s" % (s["name"], det.get("version"), url, "通过" if ok else "失败"))

    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)

    # 索引页：一页看全所有点位码
    html = ["<!doctype html><meta charset=utf-8><title>点位二维码</title>",
            "<style>body{font-family:sans-serif;background:#FAF5EF;color:#211A17;margin:24px}",
            "h1{color:#8C1F28}.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:18px}",
            ".c{background:#fff;border:1px solid #E7DCD3;border-radius:12px;padding:14px;text-align:center}",
            ".c img{width:100%;max-width:200px}.n{font-weight:700;margin-bottom:6px}.u{font-size:10px;color:#6E625C;word-break:break-all}</style>",
            "<h1>红迹·延安 · 点位二维码</h1><div class=g>"]
    for x in index:
        html.append('<div class=c><div class=n>%s</div><img src="%s"><div class=u>%s</div></div>'
                    % (x["name"], x["file"], x["url"]))
    html.append("</div>")
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    print("\n生成 %d 个点位码（失败 %d），索引页：qrcodes/index.html" % (len(index), bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
