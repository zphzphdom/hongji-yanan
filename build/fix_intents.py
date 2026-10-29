# -*- coding: utf-8 -*-
"""收尾修正：地名与主题词不该进意图表（否则「延安有多少地理标志产品」会被带去答人口）。

规则：itags 里只保留真正的"意图词"（票价/预约/开门/天气…），地名与实体词一律剔除。
"""
import io

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\build\build_kb.py"
s = io.open(P, encoding="utf-8").read()

block = '''INTENT_WORDS = set([
    "门票", "多少钱", "免费", "要钱吗", "预约", "实名", "怎么约", "约不上", "开门", "闭馆", "开放",
    "人多", "客流", "排队", "今天", "天气", "下雨", "气温", "冷不冷", "热不热", "订票", "代订",
    "买票", "预约代办", "馆长", "电话", "讲解员", "联系方式", "带货", "直播", "文案", "广告",
])
PLACE_WORDS = set(["延安", "子长", "宜川", "洛川", "志丹", "延川", "黄龙", "甘泉", "吴起", "黄陵",
                   "安塞", "宝塔", "杨家岭", "枣园", "王家坪", "凤凰山", "鲁艺", "清凉山", "南泥湾",
                   "壶口", "乾坤湾", "黄帝陵", "瓦窑堡", "刘志丹", "西北局", "纪念馆", "中央大礼堂",
                   "大生产纪念馆", "新闻纪念馆", "旧居", "旧址"])


def _itags(raw):
    out = []
    for t in raw:
        if t in PLACE_WORDS:
            continue
        if t in INTENT_WORDS:
            out.append(t)
    return out

'''

if "def _itags(raw):" not in s:
    s = s.replace("def main():", block + "\ndef main():")
    s = s.replace('"itags": sorted(set(t for t in itags if t)),',
                  '"itags": sorted(set(_itags(itags))),')
io.open(P, "w", encoding="utf-8").write(s)
print("patched:", "def _itags" in s, '"itags": sorted(set(_itags(itags)))' in s)
