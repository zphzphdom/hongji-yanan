# -*- coding: utf-8 -*-
"""修两处：kb_products.py 里重复的 image 参数；图片压缩时清只读属性。"""

import io
import os
import re
from PIL import Image

ROOT = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan"
P = os.path.join(ROOT, "build", "kb_products.py")
IMG = os.path.join(ROOT, "web", "images")

# 1) 去掉重复的 image= 参数（保留一个）
s = io.open(P, encoding="utf-8").read()
before = s.count('image=')
s = re.sub(r'(id="G\d+", image="[^"]+",)((?:(?!id=").){0,80}?)image="[^"]+",', r'\1\2', s)
io.open(P, "w", encoding="utf-8").write(s)
print("image= 参数：%d → %d" % (before, s.count('image=')))

# 2) 压缩图片
saved = 0
for f in sorted(os.listdir(IMG)):
    if not f.endswith(".webp"):
        continue
    p = os.path.join(IMG, f)
    os.chmod(p, 0o666)
    try:
        Image.open(p).close()
    except Exception:
        pass
    im = Image.open(p)
    before_bytes = os.path.getsize(p)
    w, h = im.size
    if max(w, h) > 1000:
        r = 1000 / max(w, h)
        im = im.resize((max(1, int(w * r)), max(1, int(h * r))), Image.LANCZOS)
    im.convert("RGB").save(p, "WEBP", quality=82, method=6)
    saved += before_bytes - os.path.getsize(p)
print("压缩节省 %.0f KB" % (saved / 1024))
