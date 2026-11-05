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
    # 「山西省长治市武乡县」→ 去掉省名再匹配，避免解析成「省长治市」
    if "省" in addr:
        addr = addr.split("省", 1)[1]
    # 先找「县/区」（更具体），再退到「市」
    m = re.search(r"([\u4e00-\u9fa5]{2,4}(?:县|区))", addr)
    if not m:
        m = re.search(r"([\u4e00-\u9fa5]{2,4}市)", addr)
    if m:
        return m.group(1)
    # 延安的深度点位默认在宝塔区；其他地区按地址判断，避免混成同一片区
    if (site.get("region") or "yanan") == "yanan" and site["kind"] == "deep":
        return "宝塔区"
    return (site.get("region") or "其他")


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


def _geo_of_county(county):
    try:
        import json as _j, os as _o
        p = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "data", "geo.json")
        d = _j.load(open(p, encoding="utf-8"))
        for k, v in (d.get("counties") or {}).items():
            if k and (k in (county or "") or (county or "") in k):
                return (v[0], v[1])
    except Exception:
        pass
    return None


def _dist_km(a, b):
    import math
    dlat = math.radians(b[0] - a[0]); dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(min(1, math.sqrt(h)))


def plan_route(identity, stage, interest, days=1, note="", region="yanan", origin=None):
    """按天数排线：一天一个片区（县区），片区内按得分取点位，避免跨县折返。"""
    try:
        days = max(1, min(7, int(days)))
    except Exception:
        days = 1
    need = days * 3
    pool = [x for x in _pool() if (x.get("region") or "yanan") == region] or _pool()

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

    def county_distance(c):
        if not origin or not origin.get("lat"):
            return 0
        geo = _geo_of_county(c)
        if not geo:
            return 0
        return _dist_km((origin["lat"], origin["lng"]), geo)

    counties = sorted(groups, key=lambda c: (-county_strength(c)[0], county_distance(c),
                                             -county_strength(c)[1]))
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

    # 深度点位上限：延安点位多，限一半以避免全是核心点；小地区点位本就少，不设限
    deep_cap = need if len(pool) <= need * 2 else max(1, need // 2)
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
    while len(day_groups) < days and ci < len(counties) * 3:
        c = counties[ci % len(counties)]
        got = take(c, 3)
        # 片区点位不足一天时，从后续片区继续补满（不空转）
        while len(got) < 3 and ci + 1 < len(counties) * 3:
            ci += 1
            c2 = counties[ci % len(counties)]
            more = take(c2, 3 - len(got))
            if not more:
                break
            got.extend(more)
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


OPENERS = [
    "{who}，按你说的 {days} 天和「{topic}」，我排了 {n} 个点位，分 {days} 天走。",
    "{who}，{days} 天、主题「{topic}」，{n} 个点位给你串成了 {days} 天。",
    "{who}，我按「{topic}」这个方向，把 {days} 天的行程拆成 {n} 个点位，一天一段。",
    "{who}，先定主题「{topic}」，再看时间 {days} 天，最后落到 {n} 个点位上。",
    "{who}，给你一条 {days} 天的「{topic}」线：{n} 个点位，分 {days} 天。",
]
MIDDLES = [
    "同一天尽量放在同一个县区，少折返。",
    "每天的点位都在同一片区，路上不折腾。",
    "按片区串的，一天一个方向，走起来顺。",
    "先近后远，同一天不跨县。",
    "点位之间留了缓冲，不用赶场。",
]
TITLES = [
    "{label} · {topic}（{days} 天 · {n} 个点位）",
    "{label}｜{topic}｜{days} 天 {n} 站",
    "{label} · {topic} · {days} 日线（{n} 站）",
    "{label}：{topic} · {days} 天 · {n} 个点位",
]


def greet(identity, stage, interest, days, note, route, cfg=None, region="yanan"):
    import server as _sv
    region_name = ""
    try:
        region_name = _sv.region_name(region)
    except Exception:
        region_name = ""
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

    # 线路标题与开场都用随机模板，避免每次都一样
    import random as _r
    fields = {"label": label, "topic": topic, "days": days, "n": len(route),
              "who": who}
    if region_name:
        fields["label"] = "%s·%s" % (region_name, label)
    title = _r.choice(TITLES).format(**fields)

    names = [x["name"] for x in route[:3]]
    spot_line = "、".join(names) + ("等" if len(route) > 3 else "")

    intro = ""
    if cfg and cfg.get("key"):
        try:
            import json as _json
            import urllib.request as _u
            prompt = ("你是一名延安研学线路讲解员。刚给一位%s排了一条 %s 天的「%s」线路，"
                      "点位是：%s。请写 2 句话作为开场介绍：第一句说明你怎么取舍的，"
                      "第二句给他一个参观时的观察建议。不要罗列点位名字，不要客套，"
                      "不超过 70 字，简体中文。"
                      % (who, days, topic, "、".join(x["name"] for x in route[:6])))
            payload = {"model": cfg["model"], "messages": [{"role": "user", "content": prompt}],
                       "temperature": 1.0, "max_tokens": 900, "stream": False}
            req = _u.Request(cfg["chat"], data=_json.dumps(payload).encode("utf-8"),
                             headers={"Content-Type": "application/json",
                                      "Authorization": "Bearer " + cfg["key"]}, method="POST")
            with _u.urlopen(req, timeout=15) as r:
                d = _json.loads(r.read().decode("utf-8"))
            intro = (d.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
            intro = intro.replace("\n", " ")[:140]
        except Exception:
            intro = ""

    if not intro:
        import random as _r2
        intro = _r2.choice(OPENERS).format(**fields) + _r2.choice(MIDDLES)

    if (note or "").strip():
        intro += "你提到的「%s」也算进去了。" % note.strip()[:16]

    return {"title": title, "intro": intro, "label": label, "spots": spot_line}


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


# ---------------------------------------------------------------- 社交平台参考
# 小红书 / 抖音 未开放免费搜索 API：用站点定向检索取公开网页标题做参考信号
SOCIAL_SITES = [
    ("小红书", "xiaohongshu.com"),
    ("抖音", "douyin.com"),
    ("哔哩哔哩", "bilibili.com"),
]


def social_brief(route, region_name="延安", cfg=None, timeout=8):
    """按点位关键词检索社交平台上的公开讨论标题，作为线路参考（不伪造数据）。"""
    import server as S
    out = []
    cfg = cfg or S.llm_config()
    if not cfg.get("key"):
        return out
    names = [r["short"] for r in route[:3]] or ["延安"]
    for label, domain in SOCIAL_SITES:
        q = "%s %s site:%s" % (region_name, " ".join(names[:2]), domain)
        try:
            hits = S.ds_search(cfg, q, timeout=timeout)[:2]
        except Exception:
            hits = []
        for h in hits:
            url = h.get("url") or ""
            title = (h.get("title") or "").strip()
            if domain.split(".")[0] not in url:
                continue
            # 过滤空标题、导航页、与主题无关的杂项
            if len(title) < 8:
                continue
            if any(bad in title for bad in ("热门分类", "加载中", "登录", "首页", "搜索结果")):
                continue
            out.append({"platform": label, "title": title,
                        "url": url, "site": h.get("site") or ""})
    return out[:6]
