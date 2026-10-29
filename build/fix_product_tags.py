# -*- coding: utf-8 -*-
"""给地标农品条目补别名（tags2），让「花椒多少钱一斤」这类问法落到产品画像上。"""
import io

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\build\kb_products.py"
s = io.open(P, encoding="utf-8").read()

if 'tags2=["子长"' not in s:
    s = s.replace(
        'id="G01", q="子长粉条是用什么做的？有什么特点？", image="子长粉条",',
        'id="G01", q="子长粉条是用什么做的？有什么特点？", image="子长粉条",\n'
        '        tags2=["子长", "粉条", "洋芋", "淀粉"],')
if 'tags2=["宜川"' not in s:
    s = s.replace(
        'id="G02", q="宜川花椒有什么特点？种植面积多大？", image="宜川花椒",',
        'id="G02", q="宜川花椒有什么特点？种植面积多大？", image="宜川花椒",\n'
        '        tags2=["宜川", "花椒", "大红袍", "麻"],')

io.open(P, "w", encoding="utf-8").write(s)
print("tags2 blocks:", s.count("tags2="))
