# -*- coding: utf-8 -*-
"""主题线路规划：先问身份与需求，再用「知识库点位 + 联网检索」生成线路、任务与配图。"""

import json
import os
import re
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")


def _sites():
    with open(os.path.join(DATA, "sites.json"), encoding="utf-8") as f:
        return json.load(f)["sites"]


# 兴趣 → 点位权重（按点位 id）
INTERESTS = {
    "history": "革命旧址与事件",
    "spirit": "延安精神与作风",
    "nature": "自然风光与黄河",
    "art": "文艺与新闻出版",
    "party": "党建与党性教育",
    "family": "亲子与研学",
}
WEIGHT = {
    "history": {"P2": 3, "P4": 3, "P3": 2, "P5": 2, "P1": 1, "P6": 1},
    "spirit": {"P3": 3, "P6": 3, "P1": 2, "P2": 1, "P4": 1, "P5": 1},
    "nature": {"P6": 3, "P1": 2, "P2": 0, "P3": 1, "P4": 0, "P5": 0},
    "art": {"P2": 3, "P4": 2, "P1": 1, "P3": 0, "P5": 0, "P6": 1},
    "party": {"P1": 3, "P2": 3, "P3": 2, "P4": 2, "P5": 1, "P6": 1},
    "family": {"P1": 3, "P6": 3, "P4": 2, "P2": 1, "P3": 1, "P5": 0},
}
# 半日/一日/两日
STAGE_TXT = {"primary": "小学", "middle": "初中", "high": "高中", "college": "大学"}
COUNT = {"half": 3, "full": 4, "two": 6}
# 每个点位的「为什么来」一句话（来自 KB 事实，不新增数字）
WHY = {
    "P1": "先在这里建立方向感：明代九层砖塔，延安最醒目的地标。",
    "P2": "看中央大礼堂，1942 年文艺座谈会与 1945 年七大都在这里。",
    "P3": "书记处驻地，园内纺车讲「自己动手、丰衣足食」。",
    "P4": "十三年完整叙事，11 个单元按历史顺序铺开。",
    "P5": "中央军委与八路军总部驻地，1947 年撤离延安的出发点。",
    "P6": "三五九旅开荒的地方，大生产运动的样板。",
}
# 每个点位的本地可用图（有就用，没有则取联网图）
LOCAL_IMG = {
    "P1": "宝塔山·仰拍",
    "P2": "延安大桥和宝塔山",
    "P3": "枣园",
    "P4": "延安小米",
    "P5": "宝塔山",
    "P6": "延安大桥和宝塔山",
}


def _score(interest, identity):
    base = dict(WEIGHT.get(interest, WEIGHT["history"]))
    # 党员偏重精神与党建；亲子偏重可看可玩
    if identity == "party":
        for k in ("P1", "P2", "P3"):
            base[k] = base.get(k, 0) + 1
    elif identity in ("student", "teacher") and interest == "party":
        base["P4"] = base.get("P4", 0) + 1
    return base


def plan_route(identity, stage, interest, duration, note=""):
    """纯规则选点：保证线路稳定、可解释。"""
    scores = _score(interest, identity)
    sites = {s["id"]: s for s in _sites()}
    order = sorted(scores, key=lambda k: (-scores[k], sites[k]["no"]))
    n = COUNT.get(duration, 3)
    picked = [sites[k] for k in order[:n]]

    route = []
    for i, s in enumerate(picked, 1):
        route.append({
            "order": i,
            "siteId": s["id"],
            "name": s["name"],
            "short": s["short"],
            "level": s["level"],
            "why": WHY.get(s["id"], ""),
            "minutes": 60 if s["id"] in ("P1", "P5") else 90,
        })
    return route


def greet(identity, stage, interest, duration, note, route=None):
    """开场白与线路标题：规则拼装，事实只用 knowledge 里的。"""
    who = {"student": "同学", "teacher": "老师", "party": "党员同志", "public": "朋友"}.get(identity, "朋友")
    stage_txt = {"primary": "小学", "middle": "初中", "high": "高中", "college": "大学"}.get(stage, "")
    topic = INTERESTS.get(interest, "革命旧址与事件")
    dur = {"half": "半日", "full": "一日", "two": "两日"}.get(duration, "半日")
    label = (stage_txt + "研学") if identity == "student" and stage_txt else (
        "党性教育" if identity == "party" else "主题参观")
    title = "%s · %s（%s）" % (label, topic, dur)
    n = len(route or []) or COUNT.get(duration, 3)
    intro = ("%s，按你选的「%s」和%s时间，我给你排了一条 %d 个点位的线路。"
             "顺序是按「先立方向、再看史实、最后落到精神」来的。") % (
        who, topic, dur, n)
    if note.strip():
        intro += "你提到的「%s」，我已经放进线路里了。" % note.strip()[:20]
    return {"title": title, "intro": intro, "label": label}


# 可信图源：延安本地媒体与央媒，避免抓到无关省份的站点图
GOOD_HOST = ("yanan.gov.cn", "yanews.cn", "cnr.cn", "cnwest.com", "hsw.cn",
             "people.com.cn", "xinhuanet.com", "gmw.cn", "china.cn", "gov.cn",
             "sxworker.com", "qinfeng.gov.cn", "snrtv.com", "cnwest.com")


def _credible(url):
    """只接受延安相关或央媒域名下的图，过滤掉无关省份与站点图标。"""
    if not url:
        return False
    low = url.lower()
    if any(x in low for x in ("logo", "weibo", "weixin", "qrcode", "banner", "icon")):
        return False
    return any(h in low for h in GOOD_HOST)


def collect_images(route, interest, note="", cfg=None):
    """线路配图：本地图优先，再联网补图（多组关键词依次尝试）。"""
    import server as S

    images = []
    for r in route:
        key = LOCAL_IMG.get(r["siteId"])
        if key:
            images.append({"siteId": r["siteId"], "name": r["name"], "local": key,
                           "url": None, "credit": "配图：" + key})

    # 候选关键词：用户输入优先，其次主题词，最后兜底
    cands = []
    if note.strip():
        cands.append([note.strip()[:8]])
    cands += [["延安"], ["宝塔山"], ["南泥湾"], ["延安", "宝塔山"]]
    kw_map = {"history": ["杨家岭"], "spirit": ["枣园"], "nature": ["南泥湾"],
              "art": ["鲁迅艺术文学院"], "party": ["宝塔山"], "family": ["南泥湾"]}
    cands = kw_map.get(interest, []) + cands

    web = []
    seen = set()
    for kw in cands:
        if not kw:
            continue
        try:
            box = {}
            th = threading.Thread(target=lambda: box.update(v=S.web_image(kw, timeout=7)))
            th.start()
            th.join(timeout=9)
            hit = box.get("v")
        except Exception:
            hit = None
        if hit and not _credible(hit.get("url") or ""):
            hit = None
        if hit and hit.get("url") not in seen:
            seen.add(hit.get("url"))
            web.append({"url": hit["url"], "credit": hit.get("credit") or "图源：网络",
                        "alt": " ".join(kw)})
            if len(web) >= 2:
                break
    return images, web


def web_brief(interest, note, cfg=None, timeout=8):
    """联网补充：围绕主题与用户输入检索一次，取最新 2 条标题与来源。"""
    import server as S
    q = {"history": "延安 革命旧址 开放", "spirit": "延安精神 弘扬", "nature": "南泥湾 黄河 壶口",
         "art": "延安 鲁艺 文艺", "party": "延安 党性教育", "family": "延安 亲子 研学"}.get(interest, "延安")
    if note.strip():
        q = note.strip() + " " + q
    out = []
    try:
        cfg = cfg or S.llm_config()
        for w in S.ds_search(cfg, q, timeout=timeout)[:2]:
            out.append({"title": w.get("title") or "", "site": S._site_name(w),
                        "url": w.get("url") or "", "date": w.get("date")})
    except Exception:
        pass
    return out
