# -*- coding: utf-8 -*-
"""主题线路规划：按用户填写的天数，从全部点位池正常排线，并按县区就近成组。

点位池 = 6 个深度点位 + 66 个 A 级景区（共 72 个），不再固定只给那 6 个。
配图全部联网获取，不使用本地图库。
"""
import os
import random
import re
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

STAGE_TXT = {"primary": "小学", "middle": "初中", "high": "高中", "college": "大学"}
IDENT_TXT = {"student": "同学", "teacher": "老师", "party": "党员同志", "public": "朋友"}
INTERESTS = {"history": "革命旧址与事件", "spirit": "延安精神与作风",
             "nature": "自然风光与黄河", "art": "文艺与新闻出版", "family": "亲子与研学"}

TAGS = {
    "history": ("革命", "旧址", "纪念馆", "会议", "陵园", "故居", "长征", "战役", "纪念园", "西北局", "鲁艺"),
    "spirit": ("革命", "旧址", "纪念馆", "故居", "陵园"),
    "nature": ("森林公园", "峡谷", "瀑布", "山", "湖", "湾", "泉", "生态", "园"),
    "art": ("石窟", "文化", "博物馆", "艺术", "鲁艺", "苹果", "民俗"),
    "family": ("游乐", "生态", "田园", "古镇", "南沟", "峡谷", "森林公园", "渔业"),
    "party": ("革命", "旧址", "纪念馆", "会议", "陵园", "故居"),
}

WHY = {
    "P1": "延安最醒目的地标，先在这里建立方向感。",
    "P2": "中央大礼堂所在地，1942 年文艺座谈会与 1945 年七大都在这。",
    "P3": "书记处驻地，园内纺车讲「自己动手、丰衣足食」。",
    "P4": "十三年完整叙事，11 个单元按历史顺序铺开。",
    "P5": "中央军委与八路军总部驻地，1947 年撤离延安的出发点。",
    "P6": "三五九旅开荒处，大生产运动的样板。",
}


def _pool():
    import learn
    return learn.POOL


def _tags(site):
    name = site["name"]
    out = set()
    for k, words in TAGS.items():
        if any(w in name for w in words):
            out.add(k)
    if site["kind"] == "deep":
        out.update(("history", "spirit"))
        if site["id"] in ("P1", "P4", "P6"):
            out.add("family")
    return out


def _county(site):
    addr = site.get("address") or ""
    m = re.search(r"([\u4e00-\u9fa5]{2,3}(?:县|区|市))", addr)
    if m:
        return m.group(1)
    if site["kind"] == "deep":
        return "宝塔区"
    return "其他"


def _score(site, interest, identity):
    tags = _tags(site)
    s = 0
    if interest in tags:
        s += 5
    if identity == "party" and ("party" in tags or "spirit" in tags):
        s += 3
    if identity in ("student", "teacher") and interest == "history" and "history" in tags:
        s += 2
    if site["kind"] == "deep":
        s += 2
    if site["level"] == "5A":
        s += 1
    return s


def _why(site, interest, identity):
    kn = dict(site.get("knowledge") or {})
    if site["kind"] == "deep":
        return WHY.get(site["id"], "核心点位，展陈完整。")
    bits = []
    if site["level"] in ("5A", "4A"):
        bits.append("%s 级景区" % site["level"])
    free = str(site.get("priceHigh")) in ("0", "")
    bits.append("免费" if free else "门票 %s 元" % site.get("priceHigh"))
    hours = (kn.get("开放时间") or "").split("；")[0]
    if hours:
        bits.append(hours)
    tail = {"history": "适合看旧址与展陈。", "spirit": "适合做精神主题的现场教学。",
            "nature": "自然景观，适合调节节奏。", "art": "偏文化展陈，适合慢看。",
            "family": "适合带孩子轻松参观。"}.get(interest, "顺路可看。")
    return "，".join(bits) + "。" + tail


def plan_route(identity, stage, interest, days=1, note=""):
    """按天数排线：一天一个片区（县区），片区内按得分取点位，避免跨县折返。"""
    try:
        days = max(1, min(7, int(days)))
    except Exception:
        days = 1
    need = days * 3
    pool = _pool()

    # 去掉与深度点位重复的组合景区子项，并按名称去重
    seen_name, uniq = set(), []
    for st in pool:
        nm = st["name"]
        if nm.startswith("延安革命纪念地景区"):
            continue
        keyn = nm.replace("景区", "").replace("革命旧址", "")
        if keyn in seen_name:
            continue
        seen_name.add(keyn)
        uniq.append(st)
    pool = uniq

    # 同分点位随机打散：同样条件每次生成不同线路
    rnd = random.Random()          # 每次调用都是新种子
    scored = []
    for st in pool:
        base = _score(st, interest, identity)
        jitter = rnd.uniform(0, 2.5)      # 同档内随机，不改变主题方向
        scored.append((-(base + jitter), rnd.random(), st))
    scored.sort(key=lambda x: (x[0], x[1]))
    scored = [x[2] for x in scored]

    # 按县区分组，组内按得分排序
    groups = {}
    for st in scored:
        groups.setdefault(_county(st), []).append(st)

    def county_strength(c):
        lst = groups[c]
        return (max(_score(x, interest, identity) for x in lst), len(lst))

    counties = sorted(groups, key=lambda c: (-county_strength(c)[0], -county_strength(c)[1]))
    # 同强度的县区之间随机换序，避免每次都是同一个开始
    bands, cur_band, cur_key = [], [], None
    for c in counties:
        k = county_strength(c)[0]
        if cur_key is None or k == cur_key:
            cur_band.append(c)
        else:
            bands.append(cur_band)
            cur_band = [c]
        cur_key = k
    if cur_band:
        bands.append(cur_band)
    counties = []
    for band in bands:
        rnd.shuffle(band)
        counties.extend(band)
    # 城区优先：宝塔区点位最集中，短行程先排它
    if "宝塔区" in counties:
        counties.remove("宝塔区")
        counties.insert(0, "宝塔区")

    deep_cap = max(1, need // 2)
    picked, used, deep_used = [], set(), 0

    def take(c, want):
        nonlocal deep_used
        got = []
        bucket = [x for x in groups.get(c, []) if x["id"] not in used]
        # 同档多点位时随机挑，保证每次组合不同
        head = bucket[:max(want * 2, want)]
        rnd.shuffle(head)
        rest = [x for x in bucket if x not in head]
        for x in head + rest:
            if len(got) >= want:
                break
            if x["id"] in used:
                continue
            if x["kind"] == "deep" and deep_used >= deep_cap:
                continue
            got.append(x)
            used.add(x["id"])
            if x["kind"] == "deep":
                deep_used += 1
        return got

    # 一天一个片区，按县区强度依次填
    day_groups = []
    ci = 0
    while len(day_groups) < days and ci < len(counties) * 2:
        c = counties[ci % len(counties)]
        got = take(c, 3)
        if got:
            day_groups.append((c, got))
        ci += 1
        if all(len([x for x in groups[c2] if x["id"] not in used]) == 0
               for c2 in counties):
            break

    # 不足的天数用剩余点位补齐
    while len(day_groups) < days:
        rest = [x for x in scored if x["id"] not in used]
        if not rest:
            break
        day_groups.append((_county(rest[0]), take(_county(rest[0]), 3) or rest[:1]))

    route = []
    order = 0
    for di, (c, items) in enumerate(day_groups[:days], 1):
        for st in items:
            order += 1
            route.append({"order": order, "day": di, "siteId": st["id"], "name": st["name"],
                          "short": st["short"], "level": st["level"], "kind": st["kind"],
                          "county": _county(st), "why": _why(st, interest, identity),
                          "minutes": 60 if st["kind"] == "deep" else 75})
            if order >= need:
                break
        if order >= need:
            break
    return route


def greet(identity, stage, interest, days, note, route):
    who = IDENT_TXT.get(identity, "朋友")
    topic = INTERESTS.get(interest, "革命旧址与事件")
    if identity == "student":
        label = (STAGE_TXT.get(stage, "") + "研学") if STAGE_TXT.get(stage) else "研学"
    elif identity == "party":
        label = "党性教育"
    elif identity == "teacher":
        label = "教师考察"
    else:
        label = "主题参观"
    title = "%s · %s（%s 天 · %d 个点位）" % (label, topic, days, len(route))
    intro = ("%s，按你说的 %s 天和「%s」，我排了 %d 个点位，分 %d 天走；"
             "同一天尽量放在同一个县区，少折返。") % (who, days, topic, len(route), days)
    if (note or "").strip():
        intro += "你提到的「%s」，我也考虑进去了。" % note.strip()[:18]
    return {"title": title, "intro": intro, "label": label}


# ---------------------------------------------------------------- 配图（全部联网）
# 可信图源：延安本地媒体与央媒（不含泛 gov.cn，避免抓到外省站点）
GOOD_HOST = ("yanan.gov.cn", "yanews.cn", "cnr.cn", "cnwest.com", "hsw.cn",
             "people.com.cn", "xinhuanet.com", "news.cn", "gmw.cn", "china.cn",
             "qinfeng.gov.cn", "snrtv.com", "sxworker.com", "chinadaily.com.cn",
             "cri.cn", "sxdaily.com.cn", "sanqin.com", "sohu.com", "163.com",
             "qq.com", "sina.com.cn", "ifeng.com", "thepaper.cn")

BAD_WORDS = ("logo", "weibo", "weixin", "wechatimg", "qrcode", "banner", "icon",
             "share", "avatar", "default", "placeholder")
# 报纸整版扫描图：内容相关但观感差，仅作最后兜底
NEWSPAPER = re.compile(r"(/page_?\d+\.(?:jpe?g|png)$)|(/mhtml/)", re.I)


def _credible(url, strict=True):
    """strict=True 时排除报纸整版扫描；False 时允许。"""
    if not url:
        return False
    low = url.lower()
    if any(x in low for x in BAD_WORDS):
        return False
    if strict and NEWSPAPER.search(low.split("?")[0]):
        return False
    return any(h in low for h in GOOD_HOST)


def collect_images(route, interest, note="", cfg=None, limit=4):
    """线路配图全部从网上取，不用本地图库。"""
    import server as S

    cands = []
    if (note or "").strip():
        cands.append([note.strip()[:8]])
    for r in route[:limit]:
        cands.append([r["short"]])
    cands.append(["延安"])
    cands.append(["延安", "宝塔山"])

    rnd = random.Random()
    cands = list(cands)
    rnd.shuffle(cands)                 # 关键词顺序随机 → 图片不同
    web, seen = [], set()
    for kw in cands:
        if not kw or len(web) >= limit:
            continue
        try:
            box = {}
            salted = list(kw) + [rnd.choice(("实景", "现场", "照片", "风光"))]
            th = threading.Thread(target=lambda: box.update(v=S.web_image(salted, timeout=7)))
            th.start()
            th.join(timeout=9)
            hit = box.get("v")
        except Exception:
            hit = None
        if not hit:
            continue
        url = hit.get("url")
        if not url or url in seen or not _credible(url):
            continue
        seen.add(url)
        web.append({"url": url, "credit": hit.get("credit") or "图源：网络",
                    "alt": " ".join(kw)})
    return [], web


def web_brief(interest, note, cfg=None, timeout=8):
    import server as S
    q = {"history": "延安 革命旧址 开放", "spirit": "延安精神 弘扬", "nature": "南泥湾 黄河 壶口",
         "art": "延安 鲁艺 文艺", "family": "延安 亲子 研学"}.get(interest, "延安")
    if (note or "").strip():
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
