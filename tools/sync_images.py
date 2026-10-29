# -*- coding: utf-8 -*-
"""把 web/images 同步进 docs/images（Pages 站点）与 miniprogram/images（小程序）。"""

import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "web", "images")
TARGETS = [os.path.join(ROOT, "docs", "images"), os.path.join(ROOT, "miniprogram", "images")]


def main():
    for dst in TARGETS:
        os.makedirs(dst, exist_ok=True)
        n = total = 0
        for f in os.listdir(SRC):
            if not f.endswith(".webp"):
                continue
            s, d = os.path.join(SRC, f), os.path.join(dst, f)
            os.chmod(s, 0o666)
            if os.path.exists(d):
                os.chmod(d, 0o666)
            shutil.copy2(s, d)
            n += 1
            total += os.path.getsize(d)
        print("%-40s %2d 张 %6.0f KB" % (os.path.relpath(dst, ROOT), n, total / 1024))


if __name__ == "__main__":
    main()
