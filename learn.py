# -*- coding: utf-8 -*-
"""点位学习：扫码 → 讲解 → 身份/学段 → 任务 → 判题反馈 → 进度 → 纪念卡。

账号维度存进度：data/progress.json
   {user: {siteId: {done, score, ts, mode}}}
"""
import hashlib
import json
import os
import re
import threading
import time

def _load_sites():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sites.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

_DATA = _load_sites()
SITES = _DATA["sites"]

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
PROGRESS = os.path.join(DATA, "progress.json")
LOCK = threading.Lock()

SITE_MAP = {s["id"]: s for s in SITES}
SITE_BY_NO = {s["no"]: s for s in SITES}

# 学段：小学 / 初中 / 高中 / 大学
STAGES = {
    "primary": "小学",
    "middle": "初中",
    "high": "高中",
    "college": "大学",
}
IDENTITIES = {
    "student": "学生",
    "teacher": "教师",
    "party": "党员",
    "public": "群众",
}


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


def site_list():
    return [{"id": s["id"], "no": s["no"], "name": s["name"], "short": s["short"],
             "level": s["level"]} for s in SITES]


def get_site(sid):
    if sid in SITE_MAP:
        return SITE_MAP[sid]
    try:
        return SITE_BY_NO.get(int(sid))
    except Exception:
        return None


def _key(user):
    """进度归属：没有账号体系，用浏览器访客 ID；测试账号单独隔离。"""
    u = (user or "").strip()
    if not u:
        return "anonymous"
    if u.startswith(("selftest", "test", "unknown")):
        return u
    return "v:" + u[:40]


def progress_of(user):
    data = _load()
    p = data.get(_key(user), {})
    done = [s for s in SITES if p.get(s["id"], {}).get("done")]
    return {
        "total": len(SITES),
        "done": len(done),
        "percent": round(len(done) / len(SITES) * 100),
        "sites": [{"id": s["id"], "no": s["no"], "name": s["name"],
                   "done": bool(p.get(s["id"], {}).get("done")),
                   "score": p.get(s["id"], {}).get("score"),
                   "mode": p.get(s["id"], {}).get("mode"),
                   "ts": p.get(s["id"], {}).get("ts")} for s in SITES],
        "allDone": len(done) == len(SITES),
    }


def mark_done(user, sid, score, mode, detail=None):
    with LOCK:
        data = _load()
        u = data.setdefault(_key(user), {})
        u[sid] = {"done": True, "score": score, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                  "mode": mode, "detail": detail or {}}
        _save(data)
    return progress_of(user)


# ---------------------------------------------------------------- 任务下发


def build_task(site, identity, stage, cfg, want=""):
    """按身份/学段下发任务。党员走电子讲解 + 判断题；学生/其他走学段任务。"""
    is_party = identity == "party"
    if is_party:
        return {
            "mode": "party",
            "kind": "电子讲解",
            "script": site["party"]["script"],
            "questions": site["party"]["questions"],
            "guide": "先听讲解，再完成下面的判断题；全部答对即标记该点位完成。",
        }

    st = stage if stage in site["questions"] else "middle"
    q = dict(site["questions"][st])
    # 学生可交三类之一：图片 / 文本 / 选择题；其他身份默认选择题
    allow = ["choice"]
    if identity in ("student", "teacher"):
        allow = ["choice", "text", "image"]
    prompt = {
        "primary": "看完展览，选一选下面哪句话最符合你在展板上看到的内容：",
        "middle": "根据展陈内容回答问题：",
        "high": "结合展陈内容完成下面这道题：",
        "college": "结合展陈内容与史料判断：",
    }.get(st, "根据展陈内容回答问题：")
    return {
        "mode": "learn",
        "kind": "学段任务/%s" % STAGES[st],
        "stage": st,
        "prompt": prompt,
        "question": q,
        "allow": allow,
        "guide": "可以选答案，也可以写下你的观察或上传现场照片（写上图片里的内容/展签文字）。",
    }


# ---------------------------------------------------------------- 判题与反馈


def _norm(s):
    return re.sub(r"[\s，。！？、；：\"'（）()《》·.,!?;:]", "", str(s or "")).lower()


def judge(site, task, choice=None, text=None, image=None, cfg=None):
    """返回 {ok, score, feedback, guide}。"""
    if task["mode"] == "party":
        qs = task["questions"]
        answers = choice or []
        right = 0
        wrong = []
        for i, q in enumerate(qs):
            got = answers[i] if i < len(answers) else -1
            if got == q["answer"]:
                right += 1
            else:
                wrong.append(q)
        ok = right == len(qs)
        score = round(right / max(1, len(qs)) * 100)
        if ok:
            fb = ("讲解听完了，%d 道判断题全部答对。%s"
                  % (len(qs), site["party"]["script"][:40] + "……"))
            guide = "这一段已经能讲给别人听了。"
        else:
            fb = ("答对 %d/%d。先别急，回到讲解里找依据：%s"
                  % (right, len(qs), wrong[0]["guide"]))
            guide = "可以再看一遍展陈，然后重做。"
        return {"ok": ok, "score": score, "feedback": fb, "guide": guide,
                "wrong": [q["q"] for q in wrong]}

    # 学段任务：选择题直接判；文本/图片交给模型做引导性评价
    if not choice and not text and not image:
        return {"ok": False, "score": 0, "feedback": "还没有提交内容。", "guide": "选一个答案，或写下你的观察。"}

    q = task["question"]
    if choice and not text and not image:
        got = choice[0] if isinstance(choice, list) else choice
        ok = got == q["answer"]
        if ok:
            return {"ok": True, "score": 100,
                    "feedback": "答对了。%s" % q["guide"],
                    "guide": "把这条事实记进你的研学笔记吧。"}
        right = q["options"][q["answer"]]
        return {"ok": False, "score": 0,
                "feedback": "这个选项还差一点。提示：%s" % q["guide"],
                "guide": "再读一遍展签，然后重新选择。"}

    # 文本 / 图片：先看是否覆盖了关键事实点，再请模型给引导性反馈
    sub = (text or "") + " " + (image or "")
    sub_n = _norm(sub)
    kn = dict(site["knowledge"])
    hits = [v for v in kn.values() if _norm(v) and _norm(v) in sub_n]
    # 关键数字：知识库里出现的年份/数值只要能对上就算命中（不要求整串一致）
    keys = list(kn.keys())
    key_num = set(n for n in re.findall(r"\d+(?:\.\d+)?", "".join(kn.values())) if n in sub)
    # 关键实体：知识点名称或其中 2 字以上片段出现在提交里也算命中
    key_ent = set()
    for k in keys:
        core = re.sub(r"[（(].*?[)）]", "", k)
        if core and core in sub_n:
            key_ent.add(k)
        else:
            for frag in re.findall(r"[\u4e00-\u9fa5]{2,5}", core):
                if frag in sub_n:
                    key_ent.add(k)
                    break
    covered = len(set(hits)) + len(key_num) + len(key_ent)
    # 只要写到 2 处以上关键事实（数字或实体），就视为完成任务

    score = min(100, 30 + covered * 25) if sub.strip() else 0
    ok = covered >= 2

    ai = ""
    if cfg and cfg.get("key"):
        try:
            prompt = ("你是延安红色研学导师。学生在「%s」提交了学习任务。\n"
                      "点位知识点：%s\n学生提交：%s\n"
                      "请用两句话给出引导性反馈：第一句指出他答对或观察到的具体内容，"
                      "第二句给一个下一步可以继续观察或思考的方向。不要打分，不要客套。"
                      % (site["name"], "；".join("%s：%s" % kv for kv in site["knowledge"]),
                         (text or "（图片）" + (image or ""))))
            import urllib.request
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
            ai = "你写到了%s，方向是对的。再看看讲解里另外几处细节，把它们串成一句话。" % "、".join(list(dict(site["knowledge"]).keys())[:2])
    return {"ok": ok, "score": score, "feedback": ai,
            "guide": q["guide"], "covered": covered}


# ---------------------------------------------------------------- 纪念卡


def memorial_card(user, progress, site=None, cfg=None):
    """单点位或全点位纪念卡：返回卡片文案与徽章。"""
    done = [s for s in progress["sites"] if s["done"]]
    if site:
        line = "我在延安的「%s」完成了展陈学习。" % site["name"]
        title = "点位完成纪念卡"
    elif progress["allDone"]:
        line = "我走完了延安的 %d 个展览点位，全部完成。" % progress["total"]
        title = "全线完成纪念卡"
    else:
        line = "我在延安已完成 %d/%d 个点位。" % (progress["done"], progress["total"])
        title = "进度纪念卡"
    names = "、".join(s["name"] for s in done) or "暂无"
    return {
        "title": title,
        "line": line,
        "detail": "已完成：%s" % names,
        "percent": progress["percent"],
        "done": progress["done"],
        "total": progress["total"],
        "allDone": progress["allDone"],
        "user": user,
        "badge": "全线完成" if progress["allDone"] else ("%d/%d" % (progress["done"], progress["total"])),
    }


def site_qr_payload(site_id, base=""):
    """点位二维码指向的地址（扫码后直接进入该点位）。"""
    return "%s/?site=%s" % (base.rstrip("/"), site_id) if base else "?site=" + site_id
