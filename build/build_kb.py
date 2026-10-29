# -*- coding: utf-8 -*-
"""把 50 条问答导出为运行时知识库 data/kb.json（应用与自测共用）。"""
import hashlib
import json
import os
import time

from common import OUT, SOURCE_INDEX, SPOTS, all_spec, build_rows

TAGS = {
    "baotashan": ["宝塔", "宝塔山", "地标", "象征"], "yangjialing": ["杨家岭", "七大", "文艺座谈会", "中央大礼堂"],
    "zaoyuan": ["枣园", "书记处", "为人民服务", "论联合政府"], "memorial": ["纪念馆", "延安革命纪念馆", "王家坪", "馆藏"],
    "wangjiaping": ["王家坪", "中央军委", "八路军总部", "撤离延安"], "fenghuangshan": ["凤凰山", "实践论", "矛盾论", "论持久战"],
    "luyi": ["鲁艺", "鲁迅艺术文学院", "六届六中全会", "桥儿沟"], "qingliangshan": ["清凉山", "新华社", "解放日报", "新闻"],
    "xibeiju": ["西北局", "南关"], "nanniwan": ["南泥湾", "三五九旅", "大生产", "垦荒"],
    "hukou": ["壶口", "壶口瀑布", "黄河", "宜川"], "qiankunwan": ["乾坤湾", "延川", "蛇曲", "黄河"],
    "huangdiling": ["黄帝陵", "黄陵", "桥山", "祭祖"], "wuyi": ["吴起", "长征", "落脚点", "纪念园"],
    "wayaobao": ["瓦窑堡", "子长", "瓦窑堡会议", "统一战线"], "luochuan": ["洛川", "洛川会议", "抗日"],
    "zhidan": ["刘志丹", "志丹", "烈士陵园"], "ansai": ["安塞", "腰鼓", "剪纸", "农民画", "非遗"],
}

SYNONYMS = {
    "A10": ["预约", "实名", "怎么约", "约不上"],
    "A11": ["门票", "多少钱", "免费", "要钱吗"],
    "E01": ["开门", "闭馆", "开放", "人多", "客流", "排队", "今天"],
    "E02": ["天气", "下雨", "气温", "冷不冷", "热不热"],
    "E03": ["订票", "代订", "买票", "预约代办"],
    "E04": ["梁家河", "知青"],
    "E05": ["馆长", "电话", "讲解员", "联系方式"],
    "E06": ["带货", "直播", "文案", "广告"],
}

SPOT_TAGS = {
    "spot_baotashan": "baotashan", "spot_yangjialing": "yangjialing", "spot_zaoyuan": "zaoyuan",
    "spot_memorial": "memorial", "spot_wangjiaping": "wangjiaping", "spot_fenghuangshan": "fenghuangshan",
    "spot_luyi": "luyi", "spot_qingliangshan": "qingliangshan", "spot_xibeiju": "xibeiju",
    "spot_nanniwan": "nanniwan", "spot_hukou": "hukou", "spot_qiankunwan": "qiankunwan",
    "spot_huangdiling": "huangdiling", "spot_wuyi_memorial": "wuyi", "spot_wayaobao": "wayaobao",
    "spot_luochuan_meeting": "luochuan", "spot_zhidan_memorial": "zhidan", "spot_ansai_culture": "ansai",
}


def main():
    specs = all_spec()
    rows, _ = build_rows()
    entries = []
    for row, spec in zip(rows, specs):
        tags = []
        itags = list(spec.get("tags2") or []) + SYNONYMS.get(row["id"], [])
        ref = spec.get("ref")
        keys = [ref] if isinstance(ref, str) else (list(ref) if isinstance(ref, list) else [])
        if isinstance(ref, tuple) and ref[0] == "service":
            keys = [SPOTS[ref[1]].get("kb_id")]
        for k in keys:
            if k in SPOT_TAGS:
                tags += TAGS[SPOT_TAGS[k]]
        entries.append({
            "id": row["id"],
            "q": row["q"],
            "a": row["a"],
            "sources": [SOURCE_INDEX[s] for s in row["src_ids"]],
            "kind": row["kind"],
            "scene": row["scene"],
            "conf": row["conf"],
            "tags": sorted(set(tags)),
            "itags": sorted(set(t for t in itags if t)),
        })
    payload = {
        "ip": "红迹·延安",
        "agent": "延小讲",
        "count": len(entries),
        "sources": len(SOURCE_INDEX),
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "entries": entries,
        "sourceIndex": SOURCE_INDEX,
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    payload["version"] = hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]

    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    with open(os.path.join(OUT, "data", "kb.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    # 离线内嵌副本（file:// 或无服务时使用）
    with open(os.path.join(OUT, "web", "kb.js"), "w", encoding="utf-8") as f:
        f.write("/* 自动生成，勿手改：build/build_kb.py */\nwindow.RED_KB = ")
        json.dump(payload, f, ensure_ascii=False)
        f.write(";\n")
    print("ok kb v%s / %d 条 / %d 个来源" % (payload["version"], payload["count"], payload["sources"]))


if __name__ == "__main__":
    main()
