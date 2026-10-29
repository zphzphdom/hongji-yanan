# -*- coding: utf-8 -*-
"""收到正好 150 条：删除与已有条目高度重复、信息量最低的 10 个问法。"""

import io
import re

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\build\kb_phrasings.py"
s = io.open(P, encoding="utf-8").read()

DROP = [
    "延安人均旅游花费多少？",
    "革命老区 2035 年的目标是什么？",
    "延安在黄河保护里有什么定位？",
    "红色旅游的经典景区有多少处？",
    "宝塔山能登塔吗？",
    "鲁艺培养过哪些人？",
    "安塞剪纸能体验吗？",
    "吴起长征胜利纪念园是几 A？",  # 已被前面的等级条目覆盖
    "西北局是谁的驻地？",
    "长征在吴起结束的吗？",
]

removed = 0
for q in DROP:
    pat = r'\n    \("' + re.escape(q) + r'",[^\n]*?\),'
    new = re.sub(pat, "", s, count=1)
    if new != s:
        removed += 1
        s = new
    else:
        print("未找到：", q)

s = re.sub(r",\s*,", ",", s)
io.open(P, "w", encoding="utf-8").write(s)
print("删除 %d 条" % removed)
