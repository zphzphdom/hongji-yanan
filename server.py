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

import learn
import plan

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
              "label": "评审账号", "allow": ["chat"]},
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
    if not os.path.exists(path):
        # 知识库已下线：只用联网 + 临时缓存（返回完整空索引，避免下游 KeyError）
        return ({"entries": [], "idf": {}, "avg": 1.0, "tags": [], "tagmap": {},
                 "intents": [], "intentmap": {}, "places": [], "title_df": {}},
                {"entries": [], "version": "web-only", "sources": 0})
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
    """DeepSeek 联网检索（实时）。失败返回空，不阻塞主链路。"""
    if not cfg["key"] or not cfg["search_on"]:
        return []
    body = json.dumps({"query": query, "max_results": 6}).encode("utf-8")
    req = urllib.request.Request(cfg["search"], data=body, headers={
        "Authorization": "Bearer " + cfg["key"], "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return []
    out = []
    for it in (data.get("results") or [])[:6]:
        title = (it.get("title") or "").strip()
        content = (it.get("snippet") or it.get("content") or it.get("summary") or "").strip()
        if not content:
            continue
        out.append({"title": title[:80], "site": (it.get("site_name") or "")[:24],
                    "url": (it.get("url") or "")[:300],
                    "date": (it.get("published_at") or it.get("date") or "")[:20],
                    "content": content[:400]})
    return out


MODE_RULES = {
    "fact": "史实问答：先给结论（一句），再补一句解释或一个细节。3—5 句、不超过 120 字。",
    "research": "研学讲解词：严格三段，每段以「看什么：」「为什么重要：」「想一想：」开头，"
                "每段一到两句；「想一想」必须是学生现场能观察或讨论的问题。不超过 220 字。",
    "moment": "朋友圈一句话：一行，不超过 60 字，句末带 #延安红色之旅；不用「震惊／必看／天花板／绝美」这类词。",
}

SYSTEM = (
    "你是延安红色文旅的 AI 讲解员「延小讲」。你拿到的是**刚刚联网检索到的实时网页内容**，"
    "请据此回答用户提问，并在字里行间自然体现这是新近信息。\n\n"
    "硬规则：\n"
    "1. 事实只能来自这次给出的联网检索结果；检索结果里没有的数字、日期、人名、地名一律不写。\n"
    "2. 数字、日期、专有名词必须与检索原文逐字一致，不换算、不约整、不补充推算。\n"
    "3. 检索结果相互矛盾时，选官方来源（政府网站、官媒）；仍无法判断就说明「这一点需要查证」。\n"
    "4. 一句话里最多出现 2 个数字；不要罗列数据清单。\n"
    "5. 简体中文，不用 Markdown 符号，不写「作为AI」「以上回答」这类话。\n"
    "6. 只输出正文，不要输出来源行（来源由系统附加）。\n"
    "7. 只要内容与延安时期的人、事、旧址、精神相关，就用一句话把这段内容与「延安精神」四条中的一条自然联系起来"
    "（坚定正确的政治方向／解放思想、实事求是／全心全意为人民服务／自力更生、艰苦奋斗）。"
    "不要生硬贴标签，不要每次罗列四条；与延安无关的问题（如天气、交通）不必强行关联。"
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


def ds_chat(cfg, query, mode, web_hits, timeout=20, budget=1200, strict=True):
    """先用联网检索结果生成回答；strict=False 时允许在联网为空时用知识库兜底。"""
    if not cfg["key"]:
        return None, "no_key"

    parts = ["用户提问：%s" % query, "输出模式：%s" % MODE_RULES.get(mode, MODE_RULES["fact"])]
    if web_hits:
        parts.append("【联网检索（本次唯一事实来源，按时间由新到旧给出）】")
        for i, w in enumerate(web_hits[:4], 1):
            parts.append("[%d] %s（%s，%s）\n%s" % (
                i, w.get("title") or w.get("q") or "知识库条目",
                w.get("site") or ((w.get("sources") or [{}])[0].get("org") or "知识库"),
                w.get("date") or "日期未标注",
                w.get("content") or w.get("a") or ""))
    elif strict:
        parts.append("【联网检索】无结果。")
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "\n".join(parts)},
        ],
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
        return None, "empty" + ("_length" if finish == "length" else "")
    if len(set(out) & TRAD) >= 2:
        return None, "traditional"
    # 事实护栏：回答里的数字必须来自本次给出的材料（防止模型凭记忆补数）
    if web_hits and strict:
        allowed = set()
        for w in web_hits[:4]:
            allowed |= _nums(w.get("content", "")) | _nums(w.get("title", ""))
        extra = _nums(out) - allowed
        if extra:
            return None, "ungrounded:" + ",".join(sorted(extra)[:4])
    return {"text": out, "ms": int((time.time() - t0) * 1000),
            "tokens": usage.get("total_tokens"), "model": cfg["model"]}, None


# ---------------------------------------------------------------- 知识库：只辨真伪

STOP = set("的了是在和与及或这那都有为什么怎么什么哪里如何多少几哪请问一下一一一个".replace("一", ""))


def _entities(text):
    """抽出数值与实体词（2—5 字专名），用于判断"讲的是不是同一件事"。"""
    t = str(text or "")
    nums = set(re.findall(r"\d+(?:\.\d+)?%?", t))
    cand = re.findall(r"[\u4e00-\u9fa5]{2,5}", t)
    ents = {w for w in cand if not (set(w) & STOP) or len(w) >= 4}
    return nums, ents


def verify_against_kb(answer_text, kb_hits):
    """知识库不做回答者，只做校对员：看联网生成的回答与库里记载是一致、冲突还是查无。

    判据按可靠度排序：
      1) 回答里的数值与库内某条记载同量级但不同值 → 冲突
      2) 共享 ≥2 个实体且覆盖库内关键实体 ≥40% → 支持
      3) 共享 1 个 ≥4 字专名（同一事实主体）→ 支持
      4) 其余 → 查无（明确标注为联网实时生成）
    """
    if not kb_hits:
        return {"level": "unknown", "matched": [], "conflicts": [],
                "note": "知识库没有对应的权威条目，本回答依据联网检索实时生成。"}

    a_nums, a_ents = _entities(answer_text)
    best = None
    for h in kb_hits:
        k_nums, k_ents = _entities(h.get("a", ""))
        _, q_ents = _entities(h.get("q", ""))
        pool = k_ents | q_ents
        shared = a_ents & pool
        cov_kb = len(shared) / max(1, len(pool))
        cov_ans = len(shared) / max(1, len(a_ents))
        conflict = set()
        for n in a_nums - k_nums:
            for k in k_nums:
                if len(n) == len(k) >= 3 and n[:2] == k[:2] and n != k:
                    conflict.add(n)
                    break
        score = cov_kb * 0.7 + cov_ans * 0.3
        if best is None or score > best["score"]:
            best = {"entry": h, "score": score, "cov_kb": cov_kb, "cov_ans": cov_ans,
                    "shared": shared, "conflict": conflict, "pool": len(pool),
                    "nums_ok": bool(a_nums & k_nums)}

    e = best["entry"]
    matched = [{"id": e.get("id"), "q": e.get("q"), "a": e.get("a"),
                "sources": e.get("sources"), "image": e.get("image")}]
    src = (e.get("sources") or [{}])[0]
    org = src.get("org") or "知识库"

    if best["conflict"] and len(best["shared"]) >= 2:
        return {"level": "conflict", "matched": matched,
                "conflicts": [{"entry": e.get("q")}],
                "note": "联网内容与库内记载的数值不一致，请以 %s 原始页面为准。" % org}

    long_shared = {s for s in best["shared"] if len(s) >= 4}
    if (len(best["shared"]) >= 2 and best["cov_kb"] >= 0.40) or long_shared or best["nums_ok"]:
        return {"level": "support", "matched": matched, "conflicts": [],
                "note": "库内《%s》的记载与此一致，可点开核对原文。" % (src.get("doc") or org)}
    if best["pool"] <= 12 and best["cov_ans"] >= 0.5:
        return {"level": "support", "matched": matched, "conflicts": [],
                "note": "回答主体与库内记载吻合，库内条目可作佐证。"}
    return {"level": "unknown", "matched": [], "conflicts": [],
            "note": "库内相关条目未能佐证本回答，已标注为联网实时生成。"}


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


# ---------------------------------------------------------------- 临时库（联网结果缓存）

WEBCACHE = os.path.join(DATA, "webcache.json")
WEB_TTL = 30 * 60          # 30 分钟内同问直接复用检索结果，避免重复请求


def _wc_load():
    return read_json(WEBCACHE, {}) or {}


def web_cache_get(q):
    key = hashlib.sha1(str(q).encode("utf-8")).hexdigest()[:16]
    c = _wc_load()
    item = c.get(key)
    if not item:
        return None
    if time.time() - item.get("ts", 0) > WEB_TTL:
        return None
    return item.get("hits") or []


def web_cache_put(q, hits):
    key = hashlib.sha1(str(q).encode("utf-8")).hexdigest()[:16]
    with LOCK:
        c = _wc_load()
        c[key] = {"q": str(q)[:120], "ts": time.time(), "hits": hits[:8]}
        # 只保留最近 500 条
        if len(c) > 500:
            for k in sorted(c, key=lambda x: c[x].get("ts", 0))[:len(c) - 500]:
                c.pop(k, None)
        try:
            write_json(WEBCACHE, c)
        except Exception:
            pass


# ---------------------------------------------------------------- 关键词抽取（联网取图用）

KW_NOISE = set("什么 怎么 为什么 哪里 多少 哪些 请问 一下 介绍 讲讲 告诉 帮我 可以 是否 有没有 吗 呢 啊 吧".split())
KW_ORDER = ["延安", "宝塔山", "杨家岭", "枣园", "王家岭", "王家坪", "凤凰山", "鲁艺", "清凉山", "南泥湾",
            "壶口", "乾坤湾", "黄帝陵", "瓦窑堡", "洛川", "吴起", "安塞", "子长", "宜川", "延川", "黄龙",
            "甘泉", "志丹", "黄陵", "富县", "延长", "延河", "纪念馆", "旧址", "大礼堂",
            "花椒", "粉条", "苹果", "红枣", "核桃", "蜂蜜", "小米", "荞麦", "黄酒", "豆腐", "红薯", "杏仁", "梨"]


def extract_keywords(query):
    """从问题里抓关键词：先按已知实体表，再退回切词（过滤疑问词与虚词残片）。"""
    q = str(query or "")
    hits = [w for w in KW_ORDER if w in q]

    # 把疑问句式和虚词当分隔符切开，剩下的片段才可能是实体
    STOP_PHRASES = ("是什么", "有什么", "怎么样", "为什么", "在哪里", "是哪儿", "多少", "哪些", "怎么",
                    "如何", "请问", "介绍一下", "值得", "好在哪里", "能去", "可以", "有没有")
    for p in STOP_PHRASES:
        q = q.replace(p, "|")
    q = re.sub(r"[吗呢啊吧呀嘛了的和有与及或是在要去能会看听]|[？?，,。！!、：:；;（）()]", "|", q)

    for seg in re.findall(r"[A-Za-z]{3,}|[\u4e00-\u9fa5]{2,6}", q.replace("|", "|")):
        pass  # 占位，下面用 split 处理分隔符

    for seg in [x for x in re.split(r"\|+", q) if x]:
        seg = seg.strip()
        if not (2 <= len(seg) <= 6):
            continue
        if seg in KW_NOISE:
            continue
        if any(seg in h or h in seg for h in hits):
            continue
        hits.append(seg)
        if len(hits) >= 4:
            break
    return hits[:4]


# ---------------------------------------------------------------- 联网取图
IMG_CACHE_PATH = os.path.join(DATA, "image_cache.json")
IMG_OK = re.compile(r"\.(jpe?g|png|webp)(\?|$)", re.I)
IMG_BAD_HOST = ("google.", "gstatic.", "facebook.", "twitter.", "instagram.", "tiktok.",
                "zhimg.com", "pstatic.", "doubleclick.")


IMG_NEG_TTL = 6 * 3600  # 失败结果只保留 6 小时，之后重试


def _img_cache():
    return read_json(IMG_CACHE_PATH, {}) or {}




def _img_cache_put(key, val):
    with LOCK:
        c = _img_cache()
        c[key] = val
        ts = c.get("__ts__")
        if not isinstance(ts, dict):
            ts = {}
        ts[key] = time.time()
        c["__ts__"] = ts
        try:
            write_json(IMG_CACHE_PATH, c)
        except Exception:
            pass


def _url_alive(url, timeout=4):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://yanan.gov.cn/"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ct = (r.headers.get("Content-Type") or "").lower()
            return r.status == 200 and ct.startswith("image/")
    except Exception:
        return False


def _site_name(w):
    """检索结果里的站点名偶尔是转义的十六进制串，回落成域名。"""
    name = (w.get("site") or "").strip()
    if name and re.search(r"[\u4e00-\u9fa5A-Za-z]", name) and not re.fullmatch(r"[0-9a-f]{12,}", name):
        return name
    try:
        return urllib.parse.urlparse(w.get("url") or "").netloc or "网络"
    except Exception:
        return "网络"


def _fetch_page_images(page_url, timeout=5, limit=8):
    """抓一个页面里的候选图片地址：og:image 优先，兼容懒加载属性。"""
    try:
        req = urllib.request.Request(page_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.baidu.com/"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "html" not in ctype and "xml" not in ctype:
                return []
            html = r.read(400000).decode("utf-8", "ignore")
    except Exception:
        return []

    cands = []
    Q = "[" + chr(34) + chr(39) + "]"          # ["']
    NOTQ = "([^" + chr(34) + chr(39) + "]+)"   # 捕获组

    # og:image / twitter:image（两种属性顺序）
    for pat in (
        "<meta[^>]+(?:property|name)=" + Q + "(?:og:image|twitter:image)" + Q + "[^>]*content=" + Q + NOTQ,
        "<meta[^>]+content=" + Q + NOTQ + Q + "[^>]*(?:property|name)=" + Q + "(?:og:image|twitter:image)" + Q,
    ):
        m = re.search(pat, html, re.I)
        if m:
            cands.append(m.group(1))

    # 正文图：src / data-src / data-original / data-lazy-src
    for attr in ("src", "data-src", "data-original", "data-lazy-src", "data-echo"):
        pat = "<img[^>]+" + attr + "=" + Q + NOTQ + Q
        cands += re.findall(pat, html, re.I)[:20]
    # srcset 取第一个地址
    for ss in re.findall("<img[^>]+srcset=" + Q + NOTQ + Q, html, re.I)[:10]:
        cands.append(ss.split(",")[0].strip().split(" ")[0])

    out, seen = [], set()
    DATEISH = re.compile(r"(20\d{2}[-/]?\d{2}[-/]?\d{2})|(/upload/)|(/photo/)", re.I)
    for c in cands:
        if not c or c.startswith("data:"):
            continue
        u = urllib.parse.urljoin(page_url, c)
        low = u.lower()
        if not IMG_OK.search(low.split("?")[0]):
            continue
        if any(h in low for h in IMG_BAD_HOST):
            continue
        # 站点模板图：既像图标又没有日期/上传目录，直接丢弃
        if re.search(r"(logo|icon|avatar|qrcode|share|blank|spacer|banner|wechatimg|default)", low):
            if not DATEISH.search(low):
                continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= limit:
            break
    return out


def _img_head_ok(url, timeout=4, min_bytes=25000):
    """轻量校验：只发 HEAD，看类型与大小，不下载图片本体。"""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://yanan.gov.cn/"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            size = int(r.headers.get("Content-Length") or 0)
            if not ctype.startswith("image/"):
                return False
            return size == 0 or size >= min_bytes
    except Exception:
        return False


def _img_https_ok(url, timeout=4):
    """http 图在 https 页面会被拦截：能升级就升级，不能就丢弃。"""
    if not url:
        return None
    if url.startswith("https://"):
        return url
    if url.startswith("http://"):
        cand = "https://" + url[len("http://"):]
        return cand if _img_head_ok(cand, timeout=timeout) else None
    return None


def _img_pixels_ok(url, timeout=6):
    """像素级自动识别：确认是一张真实照片（够大、比例正常、颜色不单一）。"""
    try:
        import io as _io
        from PIL import Image, ImageStat
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                   "Referer": "https://yanan.gov.cn/"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            blob = r.read(1200000)
        im = Image.open(_io.BytesIO(blob)).convert("RGB")
        w, h = im.size
        if w < 420 or h < 280:
            return False
        ratio = w / max(1, h)
        if ratio > 3.2 or ratio < 0.33:
            return False
        # 颜色标准差过小 → 纯色块/占位图
        stat = ImageStat.Stat(im.resize((80, 80)))
        if max(stat.stddev) < 12:
            return False
        return True
    except Exception:
        return None          # 无法判定：不因此拦截（网络/格式问题）


def _img_relevant(url, page_title, context, keys):
    """文本相关性：图片所在页面标题/关键词要与回答内容对得上。"""
    hay = (url or "") + " " + (page_title or "") + " " + " ".join(keys or [])
    hay_n = re.sub(r"\s+", "", hay).lower()
    terms = [k for k in (keys or []) if k] + [t for t in extract_keywords(context or "") if t]
    hits = 0
    for t in set(terms):
        tn = str(t).lower()
        if len(tn) >= 2 and tn in hay_n:
            hits += 1
    return hits >= 1


def web_image(keywords, timeout=5, fresh=False):
    """按关键词联网找图。首次收集多张候选存池，之后每次随机取一张（每条不同）。"""
    import random as _rnd
    if not keywords:
        return None
    key = "pool|" + "|".join(keywords[:2])
    cache = _img_cache()
    pool = cache.get(key)
    if isinstance(pool, list) and pool and not fresh:
        return _rnd.choice(pool)

    cfg = llm_config()
    found = []
    if cfg["key"] and cfg["search_on"]:
        try:
            results = ds_search(cfg, " ".join(keywords) + " 图片", timeout=timeout)
        except Exception:
            results = []

        BADNAME = ("logo", "icon", "avatar", "qrcode", "share", "banner", "wechat",
                   "admin", "default", "placeholder", "empty")

        # ① 结果本身就是图片
        for w in results:
            u = w.get("url") or ""
            low = u.lower()
            if any(b in low for b in BADNAME):
                continue
            if not IMG_OK.search(u.split("?")[0]) or any(h in u for h in IMG_BAD_HOST):
                continue
            if _img_head_ok(u):
                found.append({"url": u, "credit": "图源：" + _site_name(w),
                              "alt": " ".join(keywords), "page": "",
                              "pageTitle": w.get("title") or ""})

        # ② 从相关页面里抓候选图（并行），收集多张
        if len(found) < 4 and results:
            GOOD = ("gov.cn", "xinhuanet", "people.com.cn", "cnwest.com", "hsw.cn",
                    "gmw.cn", "cnr.cn", "yanews.cn", "cn")
            ranked = sorted(results, key=lambda w: 0 if any(
                d in (w.get("url") or "") for d in GOOD) else 1)
            pages = [w for w in ranked[:5] if (w.get("url") or "").startswith("http")]

            bag, lock = [], threading.Lock()

            def grab(w):
                imgs = _fetch_page_images(w.get("url") or "", timeout=4)
                with lock:
                    for u in imgs:
                        bag.append((u, w))

            ths = [threading.Thread(target=grab, args=(w,)) for w in pages]
            for th in ths:
                th.start()
            for th in ths:
                th.join(timeout=5)

            seen = {f["url"] for f in found}
            checked = []
            for u, w in bag:
                if u in seen or len(found) >= 5:
                    continue
                seen.add(u)
                checked.append((u, w))
            verdict = {}

            def check(u):
                verdict[u] = _img_head_ok(u, timeout=3)

            cths = [threading.Thread(target=check, args=(u,)) for u, _ in checked[:10]]
            for th in cths:
                th.start()
            for th in cths:
                th.join(timeout=4)
            for u, w in checked[:10]:
                if len(found) >= 5:
                    break
                if verdict.get(u):
                    found.append({"url": u, "credit": "图源：" + _site_name(w),
                                  "alt": " ".join(keywords), "page": w.get("url") or "",
                                  "pageTitle": w.get("title") or ""})

    if not found:
        _img_cache_put(key, None)
        return None
    _img_cache_put(key, found)
    return _rnd.choice(found)


# ---------------------------------------------------------------- 问答卡文案：联网生成 + 去重
CARD_STORE = os.path.join(DATA, "cards.json")
CARD_STYLE = [
    "用第一人称写两行，像在朋友圈记录当天的一个发现",
    "以一句现场感的话开头（刚走出展馆/刚爬上坡），再补一句可核对的结论",
    "用一个反常识的发现开头，让人想继续问下去",
    "以时间或地点切入，把答案落到一个具体场景",
    "以一个可以照着做的动作开头（抬头看、伸手摸），再接结论",
    "用一句疑问句开头，紧接答案，形成自问自答",
    "把答案压成一句短句 + 一句克制的感受",
    "用对比句开头：来之前以为……，其实……",
]


def _cards():
    return read_json(CARD_STORE, {"seen": [], "items": []}) or {"seen": [], "items": []}


def _gen_lines(cfg, prompt, timeout=20):
    payload = {"model": cfg["model"], "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.95, "max_tokens": 1400, "stream": False}
    req = urllib.request.Request(cfg["chat"], data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + cfg["key"]}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    raw = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    raw = re.sub(r"[*#`]", "", raw).strip()
    return [ln.strip(" -·。")[:24] for ln in raw.splitlines() if ln.strip()][:2]


def card_copy(question, answer, mode, image_key):
    """生成问答卡文案：每次联网现写，并避开已经用过的开头（保证每张不同）。"""
    cfg = llm_config()
    store = _cards()
    items = store.get("items", [])
    used_openers = [x.get("opener", "") for x in items][-20:]
    style = CARD_STYLE[len(items) % len(CARD_STYLE)]

    base = ("写两行分享文案（每行≤22字），不要解释、不要思考过程，直接输出两行正文。\n"
            "问：%s\n答：%s\n风格：%s\n避免与这些开头重复：%s\n只用答案里已有的事实。") % (
        question, answer[:160], style, "；".join(x for x in used_openers if x) or "无")

    lines = []
    if cfg["key"]:
        try:
            lines = _gen_lines(cfg, base)
        except Exception:
            lines = []
    if not lines:
        lines = [question[:20], (answer or "")[:20]]
    opener = lines[0][:8]

    seen = set(store.get("seen", []))
    sig = "|".join(lines)
    if sig in seen or opener in used_openers:
        try:
            lines = _gen_lines(cfg, base + "\n5. 上一版被判重复，请换一个完全不同的开头和句式。", timeout=18) or lines
            opener = lines[0][:8]
        except Exception:
            pass

    cid = hashlib.sha1((sig + str(time.time())).encode()).hexdigest()[:10]
    with LOCK:
        st = _cards()
        st.setdefault("seen", []).append("|".join(lines))
        st.setdefault("items", []).append({
            "id": cid, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "q": question[:80],
            "lines": lines, "opener": opener, "image": image_key, "mode": mode,
        })
        st["seen"] = st["seen"][-500:]
        st["items"] = st["items"][-200:]
        try:
            write_json(CARD_STORE, st)
        except Exception:
            pass
    return {"id": cid, "lines": lines, "unique": sig not in seen and opener not in used_openers}


# ---------------------------------------------------------------- 回答编排


def answer(query, mode, trace=False):
    """联网实时生成 → 知识库核查真伪 → 附来源与唯一配图。"""
    t0 = time.time()
    cfg = llm_config()
    kb_hits, kb = search_kb(query, 3)
    # 先查临时库（30 分钟内的联网结果），没有再联网
    web_hits = web_cache_get(query)
    if web_hits is None:
        web_hits = ds_search(cfg, query)
        if web_hits:
            web_cache_put(query, web_hits)

    budget = {"fact": 900, "research": 1500, "moment": 700}.get(mode, 900)
    text, err = ds_chat(cfg, query, mode, web_hits, timeout=22, budget=budget)
    if not text and err:
        # 空输出常见于模型把预算花在推理上（finish_reason=length）：加预算重来一次
        retry_budget = 2600 if "length" in err else 1500
        text, err2 = ds_chat(cfg, query, mode, web_hits, timeout=16, budget=retry_budget)
        err = err2 if not text else None
    if not text:
        # 联网全空 / 调用失败时才退回知识库兜底，并明确标注
        text, err3 = ds_chat(cfg, query, mode, kb_hits, timeout=16, budget=1500, strict=False)
        if not text:
            err = err3 or err
    llm_ms = text["ms"] if text else 0
    if not text:
        text = {"text": fallback_text(query, mode, kb_hits), "model": None, "ms": 0, "tokens": 0}

    # 核查：知识库下线后改为「联网多源」判断
    if kb_hits:
        verdict = verify_against_kb(text["text"], kb_hits)
    else:
        n_src = len({(w.get("site") or "") for w in web_hits})
        if not web_hits:
            verdict = {"level": "unknown", "matched": [], "reason": "本次未取到联网结果"}
        elif n_src >= 2:
            verdict = {"level": "support", "matched": [],
                       "reason": "联网 %d 个来源可相互印证" % n_src}
        else:
            verdict = {"level": "unknown", "matched": [],
                       "reason": "仅 1 个联网来源，未做交叉印证"}

    # 配图：按问题关键词从网上搜相关图片；搜不到就不配图，不再回落到本地图库
    keywords = extract_keywords(query)
    # 命中条目里的地名通常比用户原句更适合搜图（如「杨家岭革命旧址」）
    place_kw = []
    for h in kb_hits[:2]:
        for w in extract_keywords(h.get("q") or ""):
            if w not in place_kw:
                place_kw.append(w)
    # 图片改为前端异步请求（/api/img），这里只给出检索用的关键词
    img_keys = []
    for grp in (place_kw, keywords):
        for w in grp:
            if w and w not in img_keys:
                img_keys.append(w)
    web_img = None

    srcs = []
    if verdict["level"] == "support":
        for h in verdict["matched"][:1]:
            for s in h.get("sources") or []:
                if s not in srcs:
                    srcs.append(s)
    web = [{"title": w["title"], "site": w["site"], "url": w["url"], "date": w.get("date")}
           for w in web_hits[:3]]

    return {
        "ok": True,
        "mode": mode,
        "text": text["text"],
        "current": bool(web_hits),                 # 是否基于本次联网实时结果
        "verdict": verdict,
        "kb": [{"id": h.get("id"), "q": h.get("q"), "kind": h.get("kind")} for h in kb_hits],
        "sources": srcs,
        "web": web,
        "image": "",
        "imageUrl": "",
        "imagePending": True,
        "imageKeys": img_keys[:4],
        "keywords": keywords,
        "model": text.get("model"),
        "llmMs": llm_ms,
        "usedWeb": bool(web_hits),
        "degraded": text.get("model") is None,
        "error": err,
        "ms": int((time.time() - t0) * 1000),
        "kbVersion": kb.get("version"),
    } if trace else {
        "ok": True, "mode": mode, "text": text["text"], "current": bool(web_hits),
        "verdict": verdict, "kb": [{"id": h.get("id"), "q": h.get("q")} for h in kb_hits],
        "sources": srcs, "web": web, "image": "",
        "imageUrl": "",
        "imagePending": True,
        "imageKeys": img_keys[:4],
        "keywords": keywords,
        "model": text.get("model"), "llmMs": llm_ms, "usedWeb": bool(web_hits),
        "degraded": text.get("model") is None, "ms": int((time.time() - t0) * 1000),
        "kbVersion": kb.get("version"),
    }


def _public(obj):
    return obj


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
        img += 1 if (r.get("imageUrl") or r.get("image")) else 0
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



def visitor_of(req, body_user=None):
    """没有账号体系：用浏览器生成的访客 ID 区分进度，避免所有人共用一份。"""
    v = (req.headers.get("X-Visitor") or "").strip()
    if not v and isinstance(body_user, str):
        v = body_user.strip()
    return v[:40] if v else ""


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
        # 后台改为隐藏入口：不校验账号，任何人拿到入口都能看（只读）
        return {"user": "designer", "role": "admin", "admin": True, "allow": ["chat", "console"]}

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return None

    # ------------------------------------------------ GET
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        # 扫码短链：/?s=P2 → 直接跳到该点位学习页
        if path in ("/", "") and "s=" in (parsed.query or ""):
            sid = urllib.parse.parse_qs(parsed.query).get("s", [""])[0]
            if sid:
                self.send_response(302)
                self.send_header("Location", "/learn.html?site=" + urllib.parse.quote(sid))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
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
                "refused": not res.get("current"),
                "web": res.get("usedWeb"), "image": res.get("image"),
                "imageUrl": res.get("imageUrl"),
                "kw": res.get("keywords"),
                "model": res.get("model"), "llmMs": res.get("llmMs"),
                "ms": res.get("ms"), "degraded": res.get("degraded"),
                "ip": self.client_address[0],
            })
            return self._json(res)

        if path == "/api/card":
            q = str(body.get("question") or "").strip()[:300]
            a = str(body.get("answer") or "").strip()[:1200]
            if not q:
                return self._json({"ok": False, "error": "empty"}, 400)
            u = whoami(self)
            try:
                card = card_copy(q, a, str(body.get("mode") or "fact"), str(body.get("image") or ""))
            except Exception as e:
                card = {"id": "", "lines": [q[:20], a[:20]], "unique": False,
                        "error": type(e).__name__}
            append_log({"event": "card", "q": q[:80], "user": (u or {}).get("user", "anonymous"),
                        "lines": card.get("lines"), "unique": card.get("unique"),
                        "ip": self.client_address[0]})
            return self._json({"ok": True, **card})

        if path == "/api/plan":
            # 对话式开场：身份 + 学段 + 兴趣 + 时长 + 自由输入 → 任务与主题线路
            identity = str(body.get("identity") or "public")
            stage = str(body.get("stage") or "middle")
            interest = str(body.get("interest") or "history")
            # 天数由用户自己填写
            try:
                days = int(str(body.get("days") or "1").strip() or 1)
            except Exception:
                days = 1
            days = max(1, min(7, days))
            note = str(body.get("note") or "")[:120]
            route = plan.plan_route(identity, stage, interest, days, note)
            head = plan.greet(identity, stage, interest, days, note, route, llm_config())
            scope = [r["siteId"] for r in route]
            imgs, web = plan.collect_images(route, interest, note, llm_config())
            brief = plan.web_brief(interest, note, llm_config())
            # 任务：按身份给总量说明，具体每题在进入点位时下发
            task = {
                "mode": "party" if identity == "party" else "learn",
                "summary": (
                    "本次为党性教育线路：每个点位先听电子导览，再答 2 道判断题，全对即完成。"
                    if identity == "party" else
                    ("本次为%s研学线路：每个点位完成 1 个学习任务，可交选择题、文字或现场照片。"
                     % plan.STAGE_TXT.get(stage, "")) if identity == "student" else
                    ("本次为%s参观线路：每个点位看展陈、答 1 道题，完成即打勾。" % (
                        "教师" if identity == "teacher" else "主题"))),
                "count": len(route), "days": days,
            }
            u = visitor_of(self, body.get("visitor"))
            append_log({"event": "plan", "q": head["title"], "user": u,
                        "identity": identity, "interest": interest, "days": days})
            return self._json({"ok": True, "title": head["title"], "intro": head["intro"],
                               "label": head["label"], "route": route, "task": task, "days": days,
                               "scope": scope,
                               "images": imgs, "webImages": web, "webBrief": brief,
                               "progress": learn.progress_of(u, scope)})

        if path == "/api/site":
            sid = str(body.get("site") or "")
            site = learn.get_site(sid)
            if not site:
                return self._json({"ok": False, "error": "unknown_site"}, 404)
            vis = visitor_of(self, body.get("visitor"))
            return self._json({
                "ok": True,
                "site": {"id": site["id"], "no": site["no"], "name": site["name"],
                          "short": site["short"], "level": site["level"], "intro": site["intro"]},
                "progress": learn.progress_of(vis, body.get("scope") or None),
                "sites": learn.site_list(),
                "stages": learn.STAGES, "identities": learn.IDENTITIES,
            })

        if path == "/api/task":
            sid = str(body.get("site") or "")
            site = learn.get_site(sid)
            if not site:
                return self._json({"ok": False, "error": "unknown_site"}, 404)
            ident = str(body.get("identity") or "student")
            stage = str(body.get("stage") or "middle")
            task = learn.build_task(site, ident, stage, llm_config(), visitor=visitor_of(self, body.get("visitor")))
            return self._json({"ok": True, "task": task})

        if path == "/api/submit":
            sid = str(body.get("site") or "")
            site = learn.get_site(sid)
            if not site:
                return self._json({"ok": False, "error": "unknown_site"}, 404)
            user = visitor_of(self, body.get("visitor"))
            ident = str(body.get("identity") or "student")
            stage = str(body.get("stage") or "middle")
            vis = visitor_of(self, body.get("visitor"))
            # 用下发时那一套题判分，保证与用户看到的题一致
            task = learn.served_task(vis, site["id"], ident, stage) or \
                learn.build_task(site, ident, stage, llm_config(), visitor=vis)
            res = learn.judge(site, task, choice=body.get("choice"),
                              text=body.get("text"), image=body.get("image"), cfg=llm_config())
            scope = body.get("scope") or None
            if res["ok"]:
                learn.mark_done(user, site["id"], res["score"], task["mode"], {"kind": task["kind"]})
            prog = learn.progress_of(user, scope)
            append_log({"event": "task", "q": site["name"], "user": user,
                        "mode": task["mode"], "ok": res["ok"], "score": res["score"]})
            return self._json({"ok": True, "result": res, "progress": prog})

        if path == "/api/progress":
            user = visitor_of(self, body.get("visitor"))
            scope = body.get("scope") or None
            return self._json({"ok": True, "progress": learn.progress_of(user, scope),
                               "sites": learn.site_list()})

        if path == "/api/memorial":
            user = visitor_of(self, body.get("visitor"))
            prog = learn.progress_of(user, body.get("scope") or None)
            sid = str(body.get("site") or "")
            site = learn.get_site(sid) if sid else None
            signer = str(body.get("name") or "").strip()[:20]
            card = learn.memorial_card(user, prog, site=site, cfg=llm_config(), signer=signer)
            append_log({"event": "memorial", "user": user, "q": sid or "ALL"})
            return self._json({"ok": True, "card": card})

        if path == "/api/img":
            # 实时从网上取图：候选池随机抽，抽到合格的即返回（每条不同）
            import random as _random
            kws = body.get("keys") or []
            if isinstance(kws, str):
                kws = [k for k in kws.split() if k]
            kws = [str(k)[:16] for k in kws][:4]
            ctx = str(body.get("context") or "")[:400]

            combos = []
            for i in range(len(kws)):
                combos.append(kws[i:i + 2])
                combos.append(kws[i:i + 1])
            combos.append(["延安"])
            _random.shuffle(combos)

            deadline = time.time() + 14
            got = None
            tried = set()
            for combo in combos:
                if got or time.time() > deadline:
                    break
                combo = [k for k in combo if k]
                if not combo:
                    continue
                # 同一关键词多抽两次，提高"每次不一样"的概率
                for _ in range(2):
                    try:
                        box = {}
                        th = threading.Thread(target=lambda: box.update(v=web_image(combo, timeout=6)))
                        th.start()
                        th.join(timeout=7)
                        cand = box.get("v")
                    except Exception:
                        cand = None
                    if not cand or not cand.get("url"):
                        break
                    url = cand["url"]
                    if url in tried:
                        continue
                    tried.add(url)
                    if not plan._credible(url, strict=False):
                        continue
                    url2 = _img_https_ok(url)
                    if not url2:
                        continue
                    if ctx and not _img_relevant(url2, cand.get("pageTitle"), ctx, kws):
                        continue
                    if _img_pixels_ok(url2) is False:
                        continue
                    got = {"url": url2, "credit": cand.get("credit") or "图源：网络",
                           "alt": cand.get("alt") or " ".join(combo)}
                    break
            if not got:
                return self._json({"ok": True, "url": "", "reason": "未找到通过校验的相关图片"})
            return self._json({"ok": True, "url": got["url"], "credit": got["credit"],
                               "alt": got["alt"]})

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
