# -*- coding: utf-8 -*-
"""自测脚本里的期望值随知识库扩容需要更新：
   - 给这些问法补上正式条目后，"同义问法"的期望 ID 变成了新条目；这里按当前库自动对齐。
   - 越界集里"洛川苹果多少钱一斤"现在由价格条目明确作答（不再算越界失败）。
"""
import io
import re

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\tools\selftest.js"
s = io.open(P, encoding="utf-8").read()

# 1) 越界集去掉已明确作答的价格问题
s = s.replace("'洛川苹果多少钱一斤', ", "")

# 2) 同义问法期望值：新增了专门条目后，期望改成实际命中（仍是同一条事实）
FIX = {
    "['黄帝陵在哪里', 'A21']": "['黄帝陵在哪里', 'Q20']",
    "['清凉山上的新华社', 'A16']": "['清凉山上的新华社', 'Q13']",
}
for a, b in FIX.items():
    s = s.replace(a, b)

io.open(P, "w", encoding="utf-8").write(s)
print("patched:", "洛川苹果多少钱一斤" not in s, s.count("'Q20'"), s.count("'Q13'"))
