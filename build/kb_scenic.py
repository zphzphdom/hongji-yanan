# -*- coding: utf-8 -*-
"""把 62 个 A 级景区接入知识库：生成可检索的条目 + 提供完整名录查询。"""

import io
import json
import os

ROOT = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan"
SCENIC = json.load(open(os.path.join(ROOT, "data", "scenic_list.json"), encoding="utf-8"))
SRC = SCENIC["source"]
ITEMS = SCENIC["items"]

LEVELS = {"5A": [x for x in ITEMS if x["level"] == "5A"],
          "4A": [x for x in ITEMS if x["level"] == "4A"],
          "3A": [x for x in ITEMS if x["level"] == "3A"]}


def _names(lst):
    return "、".join(x["name"] for x in lst)


def _fmt(x):
    price = "免费" if x["priceHigh"] in ("0", 0) else "%s 元（旺季）/ %s 元（淡季）" % (x["priceHigh"], x["priceLow"])
    return "%s（%s，%s，开放 %s，电话 %s，地址 %s）" % (
        x["name"], x["level"], price, x["hours"], x["phone"], x["address"])


# 5A 只有 4 个景区主体（延安革命纪念地景区含 5 个子点）
FIVE_A_MAIN = ["黄帝陵景区", "延安革命纪念地景区", "黄河壶口瀑布旅游区", "延川黄河乾坤湾景区"]

SPEC = [
    dict(id="A5A", q="延安的 5A 级景区都有哪些？", tags2=["5A", "5A级景区", "A级景区", "景区"],
         ref=SRC, kind="fact", scene="参观前",
         ans="延安共有 4 个国家 5A 级旅游景区：① 黄帝陵景区；② 延安革命纪念地景区（含宝塔山、杨家岭革命旧址、"
             "枣园革命旧址、延安革命纪念馆、中共中央西北局旧址五个点）；③ 黄河壶口瀑布旅游区；④ 延川黄河乾坤湾景区。"
             "（延安市文旅局《延安市A级旅游景区基本信息表》，2026-10-26）"),
    dict(id="A4A", q="延安有哪些 4A 级景区？", tags2=["4A", "4A级景区", "A级景区"],
         ref=SRC, kind="fact", scene="参观前",
         ans="延安共有 9 个 4A 级景区：%s。（延安市文旅局，2026-10-26）" % _names(LEVELS["4A"])),
    dict(id="A3A1", q="延安 3A 级景区有哪些？（一）", tags2=["3A", "3A级景区", "A级景区"],
         ref=SRC, kind="fact", scene="参观前",
         ans="延安共有 49 个 3A 级景区，前 25 个是：%s。（延安市文旅局，2026-10-26）" % _names(LEVELS["3A"][:25])),
    dict(id="A3A2", q="延安 3A 级景区有哪些？（二）", tags2=["3A", "3A级景区", "A级景区"],
         ref=SRC, kind="fact", scene="参观前",
         ans="延安 3A 级景区后 24 个：%s。（延安市文旅局，2026-10-26）" % _names(LEVELS["3A"][25:])),
    dict(id="ALIST", q="延安一共有多少个 A 级景区？分别是哪些？", tags2=["A级景区", "数量", "几个", "名录"],
         ref=SRC, kind="fact", scene="参观前",
         ans="截至 2026 年 10 月 26 日，延安市 A 级旅游景区共 62 个：5A 级 4 个、4A 级 9 个、3A 级 49 个。"
             "完整名录见《延安市A级旅游景区基本信息表》，每条含门票、开放时间、电话与地址；"
             "在本站问答里直接问景区名称，我会给出该景区的等级、票价与开放时间。"),
]


def scenic_spec():
    """按等级生成名录条目，另外给每个景区一条独立问答（可查票价/时间/电话）。"""
    out = list(SPEC)
    # 每个景区一条，便于"××景区门票多少"这类问题命中
    for i, x in enumerate(ITEMS, 1):
        out.append(dict(
            id="S%02d_%s" % (i, x["no"]),
            q="%s门票多少钱？开放时间？" % x["name"],
            tags2=["A级景区", x["name"]],
            ref=SRC, kind="fact", scene="参观前",
            ans=_fmt(x) + "。以上为延安市文旅局 2026-10-26 公示信息，出行前请以景区当日公告为准。",
        ))
    return out


if __name__ == "__main__":
    print("景区条目数：", len(scenic_spec()) + 5)
