# -*- coding: utf-8 -*-
"""点位学习：扫码/选点 → 讲解 → 身份学段 → 匹配题目 → 判题 → 进度 → 纪念卡。

题库 data/quiz.json：按「点位 × 身份 / 学段」分池，并按访客轮换，避免所有人做同一套。
点位池：data/sites.json（深度点位 P1—P6）+ data/scenic_list.json（66 个 A 级景区）。
"""
import hashlib
import json
import os
import re
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
PROGRESS = os.path.join(DATA, "progress.json")
LOCK = threading.Lock()

STAGES = {"primary": "小学", "middle": "初中", "high": "高中", "college": "大学"}
IDENTITIES = {"student": "学生", "teacher": "教师", "party": "党员", "public": "群众"}


def _read(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


_DEEP = _read("sites.json", {"sites": []}).get("sites", [])
_SCENIC = _read("scenic_list.json", {"items": []}).get("items", [])
_QUIZ = _read("quiz.json", {"deep": {}, "scenic": {}, "meta": {}})

SCENIC_REF = {"name": "延安市文化和旅游局", "doc": "延安市A级旅游景区基本信息表",
              "date": "2026-10-26",
              "url": "https://www.yanan.gov.cn/gk/fdzdgknr/shgy/wtly/wlyw/gsgg/2114647785526538241.html"}


def _build_pool():
    pool = []
    for s in _DEEP:
        pool.append({"id": s["id"], "no": s["no"], "name": s["name"], "short": s["short"],
                     "level": s["level"], "kind": "deep", "intro": s["intro"],
                     "knowledge": s["knowledge"], "ref": s.get("ref"),
                     "tour": s.get("party", {}).get("tour") or [],
                     "script": s.get("party", {}).get("script") or "",
                     "address": "", "hours": "", "phone": "", "priceHigh": ""})
    for i, item in enumerate(_SCENIC, 1):
        sid = "S%02d" % i
        free = str(item["priceHigh"]) == "0"
        intro = "%s，%s 级旅游景区。%s开放时间：%s。地址：%s。" % (
            item["name"], item["level"],
            "免费开放。" if free else "门票旺季 %s 元、淡季 %s 元。" % (item["priceHigh"], item["priceLow"]),
            item.get("hours", ""), item.get("address", ""))
        pool.append({"id": sid, "no": int(item["no"]) if str(item["no"]).isdigit() else 0,
                     "name": item["name"], "short": item["name"].replace("景区", ""),
                     "level": item["level"], "kind": "scenic", "intro": intro,
                     "knowledge": [("等级", item["level"]),
                                   ("旺季门票", "免费" if free else item["priceHigh"] + " 元"),
                                   ("开放时间", item.get("hours", "")),
                                   ("地址", item.get("address", ""))],
                     "ref": SCENIC_REF, "tour": [], "script": "",
                     "address": item.get("address", ""), "hours": item.get("hours", ""),
                     "phone": item.get("phone", ""), "priceHigh": item.get("priceHigh", "")})
    return pool


POOL = _build_pool()
SITE_MAP = {s["id"]: s for s in POOL}
SITE_BY_NO = {s["no"]: s for s in POOL if s["no"]}


def site_list():
    return [{"id": s["id"], "no": s["no"], "name": s["name"], "short": s["short"],
             "level": s["level"], "kind": s["kind"]} for s in POOL]


def get_site(sid):
    if sid in SITE_MAP:
        return SITE_MAP[sid]
    try:
        return SITE_BY_NO.get(int(sid))
    except Exception:
        return None


def site_qr_payload(site_id, base=""):
    return "%s/?s=%s" % (base.rstrip("/"), site_id) if base else "?s=" + site_id


# ---------------------------------------------------------------- 进度
def _key(user):
    u = (user or "").strip()
    if not u:
        return "anonymous"
    if u.startswith(("selftest", "test", "unknown")):
        return u
    return "v:" + u[:40]


def _load():
    try:
        with open(PROGRESS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(obj):
    tmp = PROGRESS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PROGRESS)


def progress_of(user, scope=None):
    """scope 给定时按线路统计（进度条只算本次线路）。"""
    data = _load()
    p = data.get(_key(user), {})
    ids = scope if scope else [s["id"] for s in POOL]
    done = [i for i in ids if p.get(i, {}).get("done")]
    sites = []
    for sid in ids:
        s = SITE_MAP.get(sid)
        if not s:
            continue
        v = p.get(sid, {})
        sites.append({"id": sid, "no": s["no"], "name": s["name"], "level": s["level"],
                      "done": bool(v.get("done")), "score": v.get("score"),
                      "mode": v.get("mode"), "ts": v.get("ts")})
    total = len(sites) if scope else len(POOL)
    return {"total": total, "done": len(done),
            "percent": round(len(done) / total * 100) if total else 0,
            "sites": sites, "allDone": bool(total) and len(done) == total}


def mark_done(user, sid, score, mode, detail=None):
    with LOCK:
        data = _load()
        u = data.setdefault(_key(user), {})
        u[sid] = {"done": True, "score": score, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                  "mode": mode, "detail": detail or {}}
        _save(data)
    return progress_of(user)


# ---------------------------------------------------------------- 题目匹配
_VISITS = {}
_VISIT_LOCK = threading.Lock()


def _rotate(pool, visitor, identity, stage, sid, n):
    """不同访客分散到不同题；同一访客重复进入也往后换一题。"""
    if not pool:
        return []
    seed = int(hashlib.sha1((visitor + sid + identity + stage).encode()).hexdigest()[:8], 16)
    k = (visitor, sid, identity, stage)
    with _VISIT_LOCK:
        _VISITS[k] = _VISITS.get(k, 0) + 1
        step = _VISITS[k] - 1
    start = (seed + step) % len(pool)
    out = []
    for i in range(min(n, len(pool))):
        q = pool[(start + i) % len(pool)]
        out.append({"q": q["q"], "options": list(q["options"]), "answer": q["answer"],
                    "guide": q.get("guide", "")})
    return out


def pick_questions(site, identity, stage, visitor="", n=1):
    """按身份与学段取不同池；同一访客多次进入也会换题。"""
    sid = site["id"]
    deep = _QUIZ.get("deep", {}).get(sid) or {}
    if deep:
        if identity == "party":
            key = "party"
        elif identity == "teacher":
            key = "teacher"
        elif identity == "student":
            key = stage if stage in deep else "middle"
        else:
            key = "public"
        pool = deep.get(key) or deep.get("middle") or []
        return _rotate(pool, visitor, identity, stage, sid, n)
    pool = _QUIZ.get("scenic", {}).get(sid) or []
    return _rotate(pool, visitor, identity, stage, sid, n)


# ---------------------------------------------------------------- 任务下发
def _tour_of(site):
    if site.get("tour"):
        return site["tour"]
    kn = dict(site.get("knowledge") or [])
    free = str(site.get("priceHigh")) in ("0", "")
    return [
        ("你在哪儿", "%s，%s 级旅游景区。%s" % (site["name"], site["level"], site.get("address") or "")),
        ("看清楚这些", "开放时间 %s；%s。" % (kn.get("开放时间", "见公告"),
                                     "免费开放" if free else "旺季门票 %s 元" % site.get("priceHigh"))),
        ("带走一句", "把展签上的时间、数字、地点记下来，再谈感受——这是这一站的作业。"),
    ]


def _script_of(site):
    if site.get("script"):
        return site["script"]
    kn = dict(site.get("knowledge") or [])
    return "%s，%s 级旅游景区。%s 开放时间 %s。" % (
        site["name"], site["level"], site.get("address") or "", kn.get("开放时间", "见公告"))


# 记住给每个访客下发过的题，提交时按同一套判，避免判错题
_SERVED = {}
_SERVED_LOCK = threading.Lock()


def served_task(visitor, sid, identity, stage):
    with _SERVED_LOCK:
        return _SERVED.get((visitor, sid, identity, stage))


def build_task(site, identity, stage, cfg=None, want="", visitor=""):
    task = _build_task(site, identity, stage, cfg, want, visitor)
    if visitor:
        with _SERVED_LOCK:
            _SERVED[(visitor, site["id"], identity, stage)] = task
            if len(_SERVED) > 5000:
                for k in list(_SERVED)[:1000]:
                    _SERVED.pop(k, None)
    return task


def _build_task(site, identity, stage, cfg=None, want="", visitor=""):
    if identity == "party":
        qs = pick_questions(site, identity, stage, visitor, n=3)
        return {"mode": "party", "kind": "电子导览", "tour": _tour_of(site),
                "script": _script_of(site), "questions": qs,
                "guide": "先听导览，再完成下面的判断题；全部答对即标记该点位完成。"}

    n = 2 if identity in ("student", "teacher") else 1
    qs = pick_questions(site, identity, stage, visitor, n=n)
    allow = ["choice", "text", "image"] if identity in ("student", "teacher") else ["choice"]
    if identity == "student":
        kind = "学段任务/%s" % STAGES.get(stage, "初中")
    elif identity == "teacher":
        kind = "教师任务"
    else:
        kind = "参观任务"
    prompt = {"primary": "看完展览，选一选最符合展签内容的一项：",
              "middle": "根据展陈内容回答问题：",
              "high": "结合展陈内容完成下面这道题：",
              "college": "结合展陈与史料判断："}.get(stage, "根据展陈内容回答问题：")
    fallback = {"q": "这个点位最值得记住的一个事实是什么？",
                "options": ["展签上的时间", "展签上的数字", "展签上的地点", "以上都是"],
                "answer": 3, "guide": "先看展签的三类信息。"}
    return {"mode": "learn", "kind": kind, "stage": stage, "prompt": prompt,
            "question": qs[0] if qs else fallback, "extra": qs[1:], "allow": allow,
            "guide": "可以选答案，也可以写下观察或上传现场照片。"}


# ---------------------------------------------------------------- 判题
def _norm(s):
    return re.sub(r"[\s，。！？、；：\"'（）()《》·.,!?;:]", "", str(s or "")).lower()


def judge(site, task, choice=None, text=None, image=None, cfg=None):
    if task["mode"] == "party":
        qs = task.get("questions") or []
        answers = choice or []
        right, wrong = 0, []
        for i, q in enumerate(qs):
            got = answers[i] if i < len(answers) else -1
            if got == q["answer"]:
                right += 1
            else:
                wrong.append(q)
        ok = bool(qs) and right == len(qs)
        score = round(right / max(1, len(qs)) * 100)
        if ok:
            fb = "导览听完了，%d 道判断题全部答对。" % len(qs)
            guide = "这一段已经能讲给别人听了。"
        else:
            fb = "答对 %d/%d。回到导览里找依据：%s" % (right, len(qs),
                                                wrong[0].get("guide", "") if wrong else "")
            guide = "可以再看一遍展陈，然后重做。"
        return {"ok": ok, "score": score, "feedback": fb, "guide": guide,
                "wrong": [q["q"] for q in wrong]}

    if not choice and not text and not image:
        return {"ok": False, "score": 0, "feedback": "还没有提交内容。",
                "guide": "选一个答案，或写下你的观察。"}

    q = task["question"]
    if choice and not text and not image:
        got = choice[0] if isinstance(choice, list) else choice
        if got == q["answer"]:
            return {"ok": True, "score": 100, "feedback": "答对了。%s" % q.get("guide", ""),
                    "guide": "把这条事实记进你的研学笔记吧。"}
        return {"ok": False, "score": 0,
                "feedback": "这个选项还差一点。提示：%s" % q.get("guide", ""),
                "guide": "再读一遍展签，然后重新选择。"}

    sub = (text or "") + " " + (image or "")
    sub_n = _norm(sub)
    kn = dict(site.get("knowledge") or [])
    hits = [v for v in kn.values() if _norm(v) and _norm(v) in sub_n]
    key_num = set(n for n in re.findall(r"\d+(?:\.\d+)?", "".join(kn.values())) if n in sub)
    key_ent = set()
    for k in kn:
        core = re.sub(r"[（(].*?[)）]", "", k)
        if core and core in sub_n:
            key_ent.add(k)
        else:
            for frag in re.findall(r"[\u4e00-\u9fa5]{2,5}", core):
                if frag in sub_n:
                    key_ent.add(k)
                    break
    covered = len(set(hits)) + len(key_num) + len(key_ent)
    score = min(100, 30 + covered * 25) if sub.strip() else 0
    ok = covered >= 2

    ai = ""
    if cfg and cfg.get("key"):
        try:
            import urllib.request
            prompt = ("你是延安红色研学导师。学生在「%s」提交了学习任务。\n点位知识点：%s\n学生提交：%s\n"
                      "用两句话给引导性反馈：第一句指出他答对或观察到的具体内容，第二句给下一步方向。"
                      "不要打分，不要客套。"
                      % (site["name"], "；".join("%s：%s" % kv for kv in kn.items()),
                         (text or ("（图片）" + (image or "")))[:400]))
            payload = {"model": cfg["model"], "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.5, "max_tokens": 1200, "stream": False}
            req = urllib.request.Request(cfg["chat"], data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer " + cfg["key"]}, method="POST")
            with urllib.request.urlopen(req, timeout=18) as r:
                d = json.loads(r.read().decode("utf-8"))
            ai = (d.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        except Exception:
            ai = ""
    if not ai:
        if covered == 0:
            ai = "你提交的内容里还没有出现这个点位的具体史实。回到展板，找一处数字或年份写进答案。"
        else:
            ai = "你写到了%s，方向是对的。再看讲解里另外几处细节，把它们串成一句话。" % "、".join(list(kn.keys())[:2])
    return {"ok": ok, "score": score, "feedback": ai, "guide": q.get("guide", ""), "covered": covered}


# ---------------------------------------------------------------- 纪念卡
def memorial_card(user, progress, site=None, cfg=None, signer=""):
    done = [s for s in progress["sites"] if s["done"]]
    if site:
        line = "我在延安的「%s」完成了展陈学习。" % site["name"]
        title = "点位完成纪念卡"
    elif progress["allDone"]:
        line = "我走完了这条线路的 %d 个点位，全部完成。" % progress["total"]
        title = "全线完成纪念卡"
    else:
        line = "我在延安已完成 %d/%d 个点位。" % (progress["done"], progress["total"])
        title = "进度纪念卡"
    names = "、".join(s["name"] for s in done) or "暂无"
    return {"title": title, "line": line, "detail": "已完成：%s" % names,
            "percent": progress["percent"], "done": progress["done"],
            "total": progress["total"], "allDone": progress["allDone"],
            "user": (signer or "").strip()[:20],
            "badge": "全线完成" if progress["allDone"] else ("%d/%d" % (progress["done"], progress["total"]))}
