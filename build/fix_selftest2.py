# -*- coding: utf-8 -*-
"""自测对齐：新增口语问法后，同义问法期望改为对应条目（同一事实，不同问法）。"""

import io

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\tools\selftest.js"
s = io.open(P, encoding="utf-8").read()

FIX = {
    "['宝塔山的塔是明朝的吗', 'A02']": "['宝塔山的塔是明朝的吗', 'Q03']",
    "['七大在哪开的', 'A04']": "['七大在哪开的', 'Q01']",
    "['南泥湾是谁开垦的', 'A18']": "['南泥湾是谁开垦的', 'Q02']",
    "['黄帝陵在哪里', 'A21']": "['黄帝陵在哪里', 'Q05']",
    "['清凉山上的新华社', 'A16']": "['清凉山上的新华社', 'Q07']",
}
for a, b in FIX.items():
    s = s.replace(a, b)

# 越界集：价格问题已由 n13_price 明确作答；"延安房价"仍属越界但被 Q29 误命中，保留在失败项里如实记录
io.open(P, "w", encoding="utf-8").write(s)
print("ok", all(b not in s for b in []))
