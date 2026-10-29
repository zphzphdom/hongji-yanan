# -*- coding: utf-8 -*-
"""整理 kb_phrasings.py 的语法（之前用正则删除条目留下了空 `,,`）。"""
import io
import re

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\build\kb_phrasings.py"
s = io.open(P, encoding="utf-8").read()
s = re.sub(r",\s*,", ",", s)
s = re.sub(r",\s*\)", ")", s)
io.open(P, "w", encoding="utf-8").write(s)

import sys
sys.path.insert(0, r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\build")
import kb_phrasings
print("phrasings:", len(kb_phrasings.spec_list()))
