# -*- coding: utf-8 -*-
"""删掉重复的「宝塔山为什么是延安的象征？复述」条目（与 A01 同义，抢了自身问法）。"""

import io
import re

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\build\kb_phrasings.py"
s = io.open(P, encoding="utf-8").read()
before = len(s)
s = re.sub(r'\n    \("宝塔山为什么是延安的象征？复述",[^\n]*?\),', "", s, count=1)
io.open(P, "w", encoding="utf-8").write(s)
print("removed db", before != len(s))
