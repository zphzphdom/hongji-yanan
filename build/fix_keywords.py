# -*- coding: utf-8 -*-
"""改进关键词抽取：先切短语，再剔除疑问/虚词残片。"""

import io
import re

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\server.py"
s = io.open(P, encoding="utf-8").read()

start = s.find("def extract_keywords(query):")
end = s.find("# ---------------------------------------------------------------- 联网取图")
assert start > 0 and end > start

NEW = '''def extract_keywords(query):
    """从问题里抓关键词：先按已知实体表，再退回切词（过滤疑问词与虚词残片）。"""
    q = str(query or "")
    hits = [w for w in KW_ORDER if w in q]

    # 把疑问句式和虚词当分隔符切开，剩下的片段才可能是实体
    STOP_PHRASES = ("是什么", "有什么", "怎么样", "为什么", "在哪里", "是哪儿", "多少", "哪些", "怎么",
                    "如何", "请问", "介绍一下", "值得", "好在哪里", "能去", "可以", "有没有")
    for p in STOP_PHRASES:
        q = q.replace(p, "|")
    q = re.sub(r"[吗呢啊吧呀嘛了的和有与及或是在要去能会看听]|[？?，,。！!、：:；;（）()]", "|", q)

    for seg in re.findall(r"[A-Za-z]{3,}|[\\u4e00-\\u9fa5]{2,6}", q.replace("|", "|")):
        pass  # 占位，下面用 split 处理分隔符

    for seg in [x for x in re.split(r"\\|+", q) if x]:
        seg = seg.strip()
        if not (2 <= len(seg) <= 6):
            continue
        if seg in KW_NOISE:
            continue
        if any(seg in h or h in seg for h in hits):
            continue
        hits.append(seg)
        if len(hits) >= 4:
            break
    return hits[:4]


'''

s = s[:start] + NEW + s[end:]
io.open(P, "w", encoding="utf-8").write(s)
import ast
ast.parse(s)
print("extract_keywords rewritten; syntax ok")
