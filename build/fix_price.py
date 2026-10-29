# -*- coding: utf-8 -*-
"""追加"价格类问题"条目：农品没有政府公布单价，明确说明比拒答更有用。"""
import io

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\build\kb_products.py"
s = io.open(P, encoding="utf-8").read()

BLOCK = '''PRICE = dict(
    id="n13_price", q="子长粉条多少钱一斤？宜川花椒多少钱一斤？",
    tags2=["商品价格", "价格", "多少钱一斤"],
    ref={"name": "延安市人民政府（市市场监督管理局）",
         "doc": "延安市地理标志产品亮相第十五届中国知识产权年会", "date": "2026-09-11",
         "url": "https://www.yanan.gov.cn/zzms/bmdt/2098213380594307074.html"},
    ans="子长粉条、宜川花椒这类农品没有政府公布的统一零售价，价格随等级、季节、销售渠道浮动，我不报价，以免误导。"
        "能核实的产业信息是：延安市现有地理标志商标 34 件、居全省第一，地理标志保护产品 11 件。"
        "采购请以产地合作社、商超或官方展销渠道的当日挂牌价为准。",
)


def extra_spec():'''

if "n13_price" not in s:
    s = s.replace("def extra_spec():", BLOCK, 1)
    s = s.replace("    return PRODUCTS\n", "    return PRODUCTS + [PRICE]\n", 1)

io.open(P, "w", encoding="utf-8").write(s)
print("price entry:", "n13_price" in s, "| return:", "PRODUCTS + [PRICE]" in s)
