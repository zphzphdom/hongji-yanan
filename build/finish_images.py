# -*- coding: utf-8 -*-
"""图片收尾：宝塔山场景图挂到对应问法；生成图片清单；同步到小程序。"""

import io
import json
import os

ROOT = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan"
IMG = os.path.join(ROOT, "web", "images")

# 具体问法 -> 该用哪张图（比"按条目"更细：问雪景就出雪景图）
SCENE = {
    "宝塔山为什么是延安的象征？": "宝塔山",
    "宝塔山山上那座塔是什么年代的？": "宝塔山·仰拍",
    "宝塔山上那座塔是什么年代的？": "宝塔山·林间",
    "宝塔山在延安市区哪个位置？": "宝塔山·延河",
    "雪后的宝塔山是什么样子？": "宝塔山·雪后",
    "宝塔山日出好看吗？": "宝塔山·日出",
}


def add_scene_rows():
    P = os.path.join(ROOT, "build", "kb_phrasings.py")
    s = io.open(P, encoding="utf-8").read()
    added = 0
    for q, img in SCENE.items():
        if '"%s"' % q in s:
            continue
        line = '    ("%s", "spot_baotashan", "宝塔山", ["宝塔山", "风景"], "%s"),\n' % (q, img)
        s = s.replace('ASK = [', 'ASK = [\n' + line, 1)
        added += 1
    io.open(P, "w", encoding="utf-8").write(s)
    return added


def write_images_js():
    names = sorted(os.path.splitext(f)[0] for f in os.listdir(IMG) if f.endswith(".webp"))
    meta = {n: {"file": "images/%s.webp" % n, "alt": n + "（配图）", "credit": "配图：" + n} for n in names}
    meta["宝塔山"] = {"file": "images/宝塔山.webp", "alt": "延安宝塔山（蓝天下的宝塔）", "credit": "配图：宝塔山"}
    js = ("/* 自动生成：build/finish_images.py */\nwindow.RED_IMAGES = "
          + json.dumps(meta, ensure_ascii=False, indent=1) + ";\n")
    io.open(os.path.join(ROOT, "web", "images.js"), "w", encoding="utf-8").write(js)
    return names


if __name__ == "__main__":
    n = add_scene_rows()
    names = write_images_js()
    total = sum(os.path.getsize(os.path.join(IMG, f)) for f in os.listdir(IMG) if f.endswith(".webp"))
    print("新增场景问法 %d 条；图片 %d 张，共 %.0f KB" % (n, len(names), total / 1024))
