# -*- coding: utf-8 -*-
"""红迹·延安 —— 服务端（标准库，零依赖）。

三种模式（史实问答 / 研学讲解词 / 朋友圈一句话）**全部**由 DeepSeek 生成：
  ① 本地知识库检索命中条目（150+，带来源与配图）
  ② DeepSeek 联网检索补充（/v1/tools/search）
  ③ DeepSeek 对话模型整合成指定模式，带事实护栏
  ④ 附来源 + 附图片；任何一环失败都有降级路径，绝不返回空回答

账号：
  demo  / demo2026   → 问答 + 后台（只读：知识库、日志、看板）
  judge / judge2026  → 问答 + 后台（同只读）
  admin / <随机生成> → 全部权限（见 data/users.json）
"""
import base64
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")
USERS = os.path.join(DATA, "users.json")
LOCK = threading.Lock()

# ---------------------------------------------------------------- 配置


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


CFG_PATH = os.path.join(DATA, "config.json")
CHAT_URL = "https://api.deepseek.com/chat/completions"
SEARCH_URL = "https://api.deepseek.com/v1/tools/search"
MODEL = "deepseek-flash"


def llm_config():
    cfg = read_json(CFG_PATH, {}) or {}
    key = os.environ.get("DEEPSEEK_API_KEY") or cfg.get("api_key") or ""
    return {
        "key": key.strip(),
        "model": os.environ.get("DEEPSEEK_MODEL") or cfg.get("model") or MODEL,
        "chat": os.environ.get("DEEPSEEK_URL") or cfg.get("url") or CHAT_URL,
        "search": cfg.get("search_url") or SEARCH_URL,
        "search_on": os.environ.get("DEEPSEEK_SEARCH", "1") != "0",
    }


# ---------------------------------------------------------------- 账号

ROLES = {
    "demo": {"password": "demo2026", "role": "demo", "admin": False,
             "label": "演示账号", "allow": ["chat", "console"]},
    "judge": {"password": "judge2026", "role": "judge", "admin": False,
              "label": "评审账号", "allow": ["chat", "console"]},
}


def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("utf-8"), 120000).hex()


def ensure_users():
    users = read_json(USERS, None)
    if isinstance(users, dict) and users.get("users"):
        return users
    admin_pw = os.environ.get("HONGJI_ADMIN_PW") or ("admin" + secrets.token_hex(3))
    users = {"users": {}, "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    for name, cfg in ROLES.items():
        salt = secrets.token_hex(8)
        users["users"][name] = {
            "salt": salt, "hash": _hash(cfg["password"], salt),
            "role": cfg["role"], "admin": cfg["admin"], "label": cfg["label"],
            "allow": cfg["allow"],
        }
    salt = secrets.token_hex(8)
    users["users"]["admin"] = {
        "salt": salt, "hash": _hash(admin_pw, salt),
        "role": "admin", "admin": True, "label": "管理员",
        "allow": ["chat", "console", "write"],
    }
    os.makedirs(DATA, exist_ok=True)
    write_json(USERS, users)
    with open(os.path.join(DATA, "ADMIN_CREDENTIAL.txt"), "w", encoding="utf-8") as f:
        f.write("账号：admin\n密码：%s\n（首次启动生成，请勿提交到仓库；改密码删掉 data/users.json 重启即可）\n" % admin_pw)
    return users


SESSIONS = {}  # token -> {user, exp}
SESSION_TTL = 8 * 3600


def verify(name, pw):
    users = ensure_users()["users"]
    u = users.get((name or "").strip().lower())
    if not u:
        return None
    if hmac.compare_digest(_hash(pw or "", u["salt"]), u["hash"]):
        return u
    return None


def issue_token(name):
    tok = secrets.token_urlsafe(24)
    SESSIONS[tok] = {"user": name, "exp": time.time() + SESSION_TTL}
    return tok


def whoami(handler):
    tok = handler.headers.get("Authorization", "").replace("Bearer ", "").strip()
    meta = SESSIONS.get(tok)
    if not meta or meta["exp"] < time.time():
        return None
    users = ensure_users()["users"]
    u = users.get(meta["user"])
    if not u:
        return None
    return {"user": meta["user"], "role": u["role"], "admin": u["admin"],
           "label": u["label"], "allow": u["allow"]}


# ---------------------------------------------------------------- 知识库检索

_CACHE = {"kb": None, "mtime": 0, "idx": None}
PUNCT = re.compile(r"[\s\u3000，。！？、；：\"'“”‘’（）()《》〈〉·…—\-_,.!?;:\[\]{}<>/\\|@#$%^&*+=~`]+")


def _norm(s):
    return PUNCT.sub("", str(s or "").lower())


def _grams(s):
    t = _norm(s)
    out, parts = set(), re.findall(r"[a-z0-9]+|[\u4e00-\u9fa5]+", t)
    for seg in parts:
        if re.match(r"[\u4e00-\u9fa5]", seg):
            if len(seg) == 1:
                out.add(seg)
            for i in range(len(seg) - 1):
                out.add(seg[i:i + 2])
        else:
            out.add(seg)
    return out


def load_index():
    path = os.path.join(DATA, "kb.json")
    mtime = os.path.getmtime(path) if os.path.exists(path) else 0
    if _CACHE["mtime"] == mtime and _CACHE["idx"]:
        return _CACHE["idx"], _CACHE["kb"]
    kb = read_json(path, {"entries": []}) or {"entries": []}
    n = max(1, len(kb["entries"]))
    df = {}
    for e in kb["entries"]:
        doc = (e.get("q") or "") + "。" + (e.get("a") or "") + "。" + " ".join(e.get("tags") or [])
        e["_g"] = _grams(doc)
        e["_qg"] = _grams(e.get("q") or "")
        for k in e["_g"]:
            df[k] = df.get(k, 0) + 1
    idx = {"entries": kb["entries"]}
    idf = {k: math.log((n + 1) / (df[k] + 1)) + 1 for k in df}
    maxidf = math.log(n + 1) + 1
    tagmap, intentmap = {}, {}
    for i, e in enumerate(kb["entries"]):
        for t in e.get("tags") or []:
            tagmap.setdefault(_norm(t), []).append(i)
        for t in e.get("itags") or []:
            intentmap.setdefault(_norm(t), []).append(i)
    idx = {
        "entries": kb["entries"], "idf": idf, "maxidf": maxidf,
        "tagmap": tagmap, "intentmap": intentmap,
        "tags": sorted(tagmap, key=len, reverse=True),
        "intents": sorted(intentmap, key=len, reverse=True),
    }
    _CACHE.update({"kb": kb, "mtime": mtime, "idx": idx})
    return idx, kb


def _rank(idx, cands, qg, qn):
    out = []
    for i in cands:
        e = idx["entries"][i]
        total = hit = qhit = 0.0
        for k in qg:
            w = idx["idf"].get(k, idx["maxidf"])
            total += w
            if k in e["_g"]:
                hit += w
                if k in e["_qg"]:
                    qhit += w
        if total <= 0:
            continue
        score = (hit / total) * 0.55 + (qhit / total) * 0.45
        if e["_qg"] and (_norm(e["q"]) in qn or qn in _norm(e["q"])):
            score = max(score, 0.96)
        if score > 0.02:
            out.append((score, i))
    out.sort(reverse=True)
    return out


def search_kb(q, topk=4):
    idx, kb = load_index()
    qg, qn = _grams(q), _norm(q)
    if not qg:
        return [], kb
    # 实体优先（覆盖比例最高者）
    ents = [t for t in idx["tags"] if t and t in qn]
    if ents:
        best, ratio = None, 0.0
        for t in ents:
            r = len(t) / max(1, len(qn))
            if r > ratio + 1e-9:
                ratio, best = r, t
        if ratio >= 0.5 and best:
            res = _rank(idx, idx["tagmap"][best], qg, qn)
            if res and res[0][0] >= 0.20:
                return [idx["entries"][i] for _, i in res[:topk]], kb
        return [idx["entries"][i] for _, i in _rank(idx, range(len(idx["entries"])), qg, qn)[:topk]], kb
    # 意图词
    for t in idx["intents"]:
        if t and t in qn:
            res = _rank(idx, idx["intentmap"][t], qg, qn)
            if res and res[0][0] >= 0.22:
                return [idx["entries"][i] for _, i in res[:topk]], kb
    return [idx["entries"][i] for _, i in _rank(idx, range(len(idx["entries"])), qg, qn)[:topk]], kb


# ---------------------------------------------------------------- DeepSeek


def ds_search(cfg, query, timeout=8):
    """DeepSeek 联网检索；失败返回空，不阻塞主链路。"""
    if not cfg["key"] or not cfg["search_on"]:
        return []
    body = json.dumps({"query": query, "max_results": 4}).encode("utf-8")
    req = urllib.request.Request(cfg["search"], data=body, headers={
        "Authorization": "Bearer " + cfg["key"], "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return []
    out = []
    for it in (data.get("results") or [])[:4]:
        title = (it.get("title") or "").strip()
        content = (it.get("snippet") or it.get("content") or it.get("summary") or "").strip()
        if not content:
            continue
        out.append({"title": title[:80], "site": (it.get("site_name") or "")[:24],
                    "url": (it.get("url") or "")[:300], "content": content[:400]})
    return out


MODE_RULES = {
    "fact": "史实问答：先给结论（一句），再补一句解释或一个细节。3—5 句、不超过 120 字。",
    "research": "研学讲解词：严格三段，每段以「看什么：」「为什么重要：」「想一想：」开头，"
                "每段一到两句；「想一想」必须是学生现场能观察或讨论的问题。不超过 220 字。",
    "moment": "朋友圈一句话：一行，不超过 60 字，句末带 #延安红色之旅；不用「震惊／必看／天花板／绝美」这类词。",
}

SYSTEM = (
    "你是延安红色文旅的 AI 讲解员「延小讲」。你会拿到三样东西：用户的提问、"
    "本地知识库的命中条目（权威，带来源）、可选的联网检索结果。\n"
    "你的任务：把知识库与联网结果整合成指定模式的回答。\n\n"
    "硬规则：\n"
    "1. 事实以「知识库」为准；知识库没有时，才可以采用「联网结果」，并且必须与提问直接相关。\n"
    "2. 所有数字、日期、人名、地名必须与所给材料逐字一致，不换算、不四舍五入、不补充推算。\n"
    "3. 材料里没有的信息一律不编；拿不准就说明「这一点需要查证」。\n"
    "4. 一句话里最多出现 2 个数字；不要罗列数据清单。\n"
    "5. 简体中文，不用 Markdown 符号，不写「作为AI」「以上回答」这类话，不加感叹号连用。\n"
    "6. 只输出正文，不要输出「来源：」行（来源由系统自动附加）。"
)

MODE_HINTS = {
    "fact": "史实问答：先给结论（一句），再补一句解释或一个细节。3—5 句、不超过 120 字。",
    "research": "研学讲解词：严格三段，每段以「看什么：」「为什么重要：」「想一想：」开头，"
                "每段一到两句；「想一想」必须是学生现场能观察或讨论的问题。不超过 260 字。",
    "moment": "朋友圈一句话：一行，不超过 60 字，句末带 #延安红色之旅；不用「震惊／必看／天花板／绝美」这类词。",
}

TRAD = set("個這說時為國會後學實現點東車馬長門問間樣麼幾還開關頭區單獨風飛書筆義傳體聲廣場廠條"
           "務員親愛歡迎歲歷應當與軍農業產黨團鐵銀錢買賣讀寫聽讓認識記憶約級給華萬億兩隻雙對錯難"
           "簡據處證灣醫療藝術範圍導遊覽資訊網絡聯繫電話號碼")


def _nums(s):
    return set(re.findall(r"\d+(?:\.\d+)?", s or ""))


def ds_chat(cfg, query, mode, kb_hits, web_hits, timeout=20, budget=1200):
    """返回 (text, meta) 或 (None, err)。"""
    if not cfg["key"]:
        return None, "no_key"

    parts = ["用户提问：%s" % query, "输出模式：%s" % MODE_RULES.get(mode, MODE_RULES["fact"])]
    if kb_hits:
        parts.append("【知识库】")
        for h in kb_hits[:3]:
            src = (h.get("sources") or [{}])[0]
            parts.append("- 问：%s\n  答：%s\n  来源：%s《%s》%s" % (
                h.get("q"), h.get("a"), src.get("org", ""), src.get("doc", ""), src.get("date", "")))
    if web_hits:
        parts.append("【联网检索（未人工复核，仅作补充）】")
        for w in web_hits[:3]:
            parts.append("- %s（%s）：%s" % (w["title"], w["site"], w["content"]))
    if not kb_hits and not web_hits:
        parts.append("【材料】无。请直接说明这个问题需要查证，并给出官方渠道建议。")

    payload = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": "\n".join(parts)}],
        "temperature": 0.35,
        "max_tokens": budget,
        "stream": False,
    }
    req = urllib.request.Request(cfg["chat"], data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + cfg["key"]}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return None, type(e).__name__ + ":" + str(e)[:80]
    out = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
    usage = data.get("usage") or {}

    out = re.sub(r"(?m)^\s*#{1,6}\s*", "", out).replace("**", "")
    out = re.sub(r"^(来源|参考)[:：].*$", "", out, flags=re.M).strip()
    lines = [ln for ln in out.splitlines() if ln.strip()]
    out = "\n".join(ln.rstrip() for ln in lines)
    finish = (data.get("choices") or [{}])[0].get("finish_reason")
    if not out:
        # 常见原因：预算被推理 token 吃光（finish_reason=length）
        return None, "empty" + ("_length" if finish == "length" else "")
    if len(set(out) & TRAD) >= 2:
        return None, "traditional"
    # 事实护栏：知识库命中时，模型不得出现知识库以外的数字
    if kb_hits:
        allowed = set()
        for h in kb_hits[:3]:
            allowed |= _nums(h.get("q", "")) | _nums(h.get("a", ""))
        for w in web_hits[:3]:
            allowed |= _nums(w.get("content", ""))
        extra = _nums(out) - allowed
        if extra:
            return None, "ungrounded:" + ",".join(sorted(extra)[:4])
    return {"text": out, "ms": int((time.time() - t0) * 1000),
            "tokens": usage.get("total_tokens"), "model": cfg["model"]}, None


# ---------------------------------------------------------------- 配图：每答必图
# 场景图按"问到什么"给：先看命中条目有没有图，再按关键词挑场景图，最后兜底城市图
SCENE_RULES = [
    (("雪",), "宝塔山·雪后"),
    (("日出", "日落", "夕阳", "清晨", "日落"), "宝塔山·日出"),
    (("仰", "近看", "塔身", "九层"), "宝塔山·仰拍"),
    (("延河", "位置", "在哪", "市区"), "宝塔山·延河"),
    (("宝塔",), "宝塔山"),
    (("城门", "延安城", "城市", "建筑"), "延安大桥和宝塔山"),
]
FALLBACKS = {
    "fact": "宝塔山",
    "research": "延安大桥和宝塔山",
    "moment": "宝塔山·日出",
}


def pick_image(query, mode, kb_hits):
    for h in kb_hits:
        if h.get("image"):
            return h["image"], "条目图片"
    for keys, name in SCENE_RULES:
        if any(k in query for k in keys):
            return name, "场景图"
    for h in kb_hits:
        for t in h.get("tags") or []:
            for keys, name in SCENE_RULES:
                if any(k in t for k in keys):
                    return name, "场景图"
    return FALLBACKS.get(mode, "宝塔山"), "默认图"


# ---------------------------------------------------------------- 回答编排


def answer(query, mode, trace=False):
    t0 = time.time()
    cfg = llm_config()
    # 知识库检索与联网检索并行，省掉一整个网络往返
    box = {}
    th = threading.Thread(target=lambda: box.update(web=ds_search(cfg, query)))
    th.start()
    kb_hits, kb = search_kb(query, 4)
    th.join(timeout=8)
    web_hits = box.get('web', [])

    budget = {"fact": 900, "research": 1500, "moment": 700}.get(mode, 900)
    text, err = ds_chat(cfg, query, mode, kb_hits, web_hits, timeout=22, budget=budget)
    if not text:
        # 空输出常见于模型把预算花在推理上（finish_reason=length）：加预算重来一次
        retry_budget = 2600 if (err and "length" in err) else 1500
        text, err2 = ds_chat(cfg, query, mode, kb_hits, web_hits, timeout=16, budget=retry_budget)
        err = err2 if not text else None
    llm_ms = 0
    if text:
        llm_ms = text["ms"]
    else:
        # 降级：模式化拼装知识库内容（保证有答，不空手）
        text = {"text": fallback_text(query, mode, kb_hits), "model": None,
                "ms": 0, "tokens": 0}

    img, img_src = pick_image(query, mode, kb_hits)
    srcs = []
    for h in kb_hits[:2]:
        for s in h.get("sources") or []:
            if s not in srcs:
                srcs.append(s)
    web = [{"title": w["title"], "site": w["site"], "url": w["url"]} for w in web_hits[:3]]

    out = {
        "ok": True,
        "mode": mode,
        "text": text["text"],
        "kb": [{"id": h.get("id"), "q": h.get("q"), "kind": h.get("kind")} for h in kb_hits[:3]],
        "sources": srcs,
        "web": web,
        "image": img,
        "imageSource": img_src,
        "model": text.get("model"),
        "llmMs": llm_ms,
        "usedWeb": bool(web_hits),
        "usedKB": bool(kb_hits),
        "degraded": err is not None and text.get("model") is None,
        "error": err,
        "ms": int((time.time() - t0) * 1000),
        "kbVersion": kb.get("version"),
    }
    if not trace:
        out.pop("error", None)
    return out


def fallback_text(query, mode, kb_hits):
    if not kb_hits:
        return ("这个问题我需要查证，建议咨询延安市文旅局或对应场馆的官方渠道。"
                "为避免提供不准确的信息，我不做推测。")
    a = kb_hits[0].get("a") or ""
    sents = re.split(r"(?<=[。！？；])", a)
    sents = [s for s in sents if s.strip()]
    if mode == "moment":
        one = sents[0] if sents else a
        return (one[:56] + ("…" if len(one) > 56 else "")) + " #延安红色之旅"
    if mode == "research":
        what = sents[0] if sents else a
        why = sents[1] if len(sents) > 1 else "这一段是延安十三年的一部分。"
        return ("看什么：%s\n为什么重要：%s\n想一想：如果请你向同伴介绍这一段，你会先讲哪一件事？"
                % (what.strip(), why.strip()))
    return "".join(sents[:3])[:160]


# ---------------------------------------------------------------- 日志与看板


def append_log(rec):
    rec = dict(rec)
    rec.setdefault("t", time.strftime("%Y-%m-%d %H:%M:%S"))
    os.makedirs(DATA, exist_ok=True)
    with LOCK:
        with open(os.path.join(DATA, "usage.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_logs(limit=200):
    path = os.path.join(DATA, "usage.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return list(reversed(out))


def dashboard():
    logs = read_logs(1000)
    total = len(logs)
    by_mode = {}
    refused = 0
    used_web = 0
    img = 0
    ms = []
    by_user = {}
    for r in logs:
        by_mode[r.get("mode", "?")] = by_mode.get(r.get("mode", "?"), 0) + 1
        refused += 1 if r.get("refused") else 0
        used_web += 1 if r.get("web") else 0
        img += 1 if r.get("image") else 0
        if isinstance(r.get("ms"), (int, float)):
            ms.append(r["ms"])
        u = r.get("user", "anonymous")
        by_user[u] = by_user.get(u, 0) + 1
    ms.sort()
    kb = read_json(os.path.join(DATA, "kb.json"), {}) or {}
    health = read_json(os.path.join(DATA, "kb_health.json"), {}) or {}
    return {
        "total": total,
        "byMode": by_mode,
        "refused": refused,
        "refusedRate": round(refused / total * 100, 1) if total else 0,
        "usedWeb": used_web,
        "webRate": round(used_web / total * 100, 1) if total else 0,
        "withImage": img,
        "imageRate": round(img / total * 100, 1) if total else 0,
        "p50": ms[len(ms) // 2] if ms else 0,
        "p90": ms[int(len(ms) * 0.9)] if ms else 0,
        "byUser": by_user,
        "kb": {"count": kb.get("count"), "sources": kb.get("sources"), "version": kb.get("version")},
        "sourceHealth": {"ok": health.get("ok"), "total": health.get("total"),
                         "checked": health.get("checked_at")},
        "recent": read_logs(20),
    }


# ---------------------------------------------------------------- HTTP


def _safe(o):
    """JSON 兜底：把 set / 其他非序列化对象转成可序列化形态，避免整条请求 500。"""
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, bytes):
        return o.decode("utf-8", "ignore")
    return str(o)


class Handler(SimpleHTTPRequestHandler):
    server_version = "HongjiYanan/2.0"

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB, **kw)

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, default=_safe).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _need(self, allow="console"):
        u = whoami(self)
        if not u:
            self._json({"ok": False, "error": "unauthorized"}, 401)
            return None
        if allow not in u["allow"] and not u["admin"]:
            self._json({"ok": False, "error": "forbidden"}, 403)
            return None
        return u

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return None

    # ------------------------------------------------ GET
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/health":
            return self._json({"ok": True, "t": int(time.time())})
        if path == "/api/kb":
            _, kb = load_index()
            return self._json(kb)
        if path == "/api/capabilities":
            cfg = llm_config()
            _, kb = load_index()
            return self._json({
                "llm": bool(cfg["key"]), "search": bool(cfg["key"] and cfg["search_on"]),
                "model": cfg["model"] if cfg["key"] else None,
                "modes": ["fact", "research", "moment"], "imageEveryReply": True,
                "kb": {"count": kb.get("count"), "sources": kb.get("sources"), "version": kb.get("version")},
            })
        if path == "/api/selftest":
            return self._json(read_json(os.path.join(DOCS, "selftest.json"), {}))
        if path == "/api/console/dashboard":
            if not self._need():
                return
            return self._json(dashboard())
        if path == "/api/console/logs":
            if not self._need():
                return
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            limit = min(500, int((q.get("limit") or ["100"])[0]))
            return self._json({"logs": read_logs(limit)})
        if path == "/api/console/kb":
            if not self._need():
                return
            _, kb = load_index()
            return self._json(kb)
        return super().do_GET()

    # ------------------------------------------------ POST
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self._body()
        if body is None:
            return self._json({"ok": False, "error": "bad_json"}, 400)

        if path == "/api/login":
            name = str(body.get("username") or "").strip()
            u = verify(name, str(body.get("password") or ""))
            if not u:
                return self._json({"ok": False, "error": "账号或密码错误"}, 401)
            tok = issue_token(name.lower())
            append_log({"event": "login", "user": name.lower(),
                        "ip": self.client_address[0]})
            return self._json({"ok": True, "token": tok, "user": name.lower(),
                               "role": u["role"], "label": u["label"], "allow": u["allow"]})

        if path == "/api/logout":
            tok = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
            SESSIONS.pop(tok, None)
            return self._json({"ok": True})

        if path == "/api/ask":
            q = str(body.get("question") or "").strip()[:300]
            mode = str(body.get("mode") or "fact")
            if mode not in MODE_RULES:
                mode = "fact"
            if not q:
                return self._json({"ok": False, "error": "empty"}, 400)
            u = whoami(self)
            try:
                res = answer(q, mode)
            except Exception as e:
                res = {"ok": False, "error": type(e).__name__, "text": "服务端出错了，请重试。", "image": "宝塔山"}
            append_log({
                "q": q, "mode": mode, "user": (u or {}).get("user", "anonymous"),
                "kb": [h["id"] for h in res.get("kb", [])][:2],
                "refused": not res.get("usedKB") and not res.get("usedWeb"),
                "web": res.get("usedWeb"), "image": res.get("image"),
                "model": res.get("model"), "llmMs": res.get("llmMs"),
                "ms": res.get("ms"), "degraded": res.get("degraded"),
                "ip": self.client_address[0],
            })
            return self._json(res)

        if path == "/api/log":
            append_log({
                "q": str(body.get("q", ""))[:120], "mode": body.get("mode"),
                "id": body.get("id"), "refused": bool(body.get("refused")),
                "image": body.get("image"), "ip": self.client_address[0],
            })
            return self._json({"ok": True})

        return self._json({"ok": False, "error": "not_found"}, 404)


def main():
    port, host = 8788, "0.0.0.0"
    args = sys.argv[1:]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    if "--host" in args:
        host = args[args.index("--host") + 1]
    ensure_users()
    srv = ThreadingHTTPServer((host, port), Handler)
    cfg = llm_config()
    print("红迹·延安 已启动：")
    print("  本机   http://127.0.0.1:%d" % port)
    for ip in _lan_ips():
        print("  局域网 http://%s:%d" % (ip, port))
    print("  DeepSeek：%s ｜ 联网检索：%s" % ("已接入" if cfg["key"] else "未配置",
                                          "开" if (cfg["key"] and cfg["search_on"]) else "关"))
    print("  账号：demo/demo2026（演示）  judge/judge2026（评审）  admin（见 data/ADMIN_CREDENTIAL.txt）")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


def _lan_ips():
    import socket
    out = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("223.5.5.5", 80))
        out.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return out


if __name__ == "__main__":
    main()
