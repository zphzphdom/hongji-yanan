# -*- coding: utf-8 -*-
"""共用数据层：读取已核验史料，注册来源编号，生成 50 条问答。"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.dirname(ROOT), "hongyuan-zhidao", "data")
OUT = ROOT

IP_NAME = "红迹·延安"
AGENT_NAME = "延小讲"
BOOK_URL = "https://yagmjng.com"
WECHAT = "微信公众号「延安革命纪念馆」"


def load():
    kb = {it["id"]: it for it in json.load(open(os.path.join(SRC, "kb.json"), encoding="utf-8"))}
    spots = {it["id"]: it for it in json.load(open(os.path.join(SRC, "spots.json"), encoding="utf-8"))}
    return kb, spots


KB, SPOTS = load()
SOURCE_INDEX = {}


def service_answer(spot_id):
    s = SPOTS[spot_id]
    parts = ["%s：%s。" % (s["name"], s.get("one_line", ""))]
    if s.get("ticket"):
        parts.append("门票：%s。" % s["ticket"])
    if s.get("open_time"):
        parts.append("开放时间：%s。" % s["open_time"])
    if s.get("booking"):
        parts.append("预约：%s。" % s["booking"])
    parts.append("以上为公开信息，出行前请以官方当日公告为准。")
    return "".join(parts)


def service_source(spot_id):
    """服务类事实（门票/时间/预约）按《延安市A级旅游景区基本信息表》统一出处。"""
    return KB["tourism_supply"]["source"]


def resolve(row):
    """返回 (标准回答, 来源对象列表)。"""
    ref = row["ref"]
    kind = row.get("kind", "fact")
    if kind == "service":
        sid = ref[1]
        src = service_source(sid)
        kb_id = SPOTS[sid].get("kb_id")
        if kb_id and kb_id in KB:
            src = KB[kb_id]["source"]
        return service_answer(sid), [src]
    if kind == "combo":
        texts = []
        srcs = []
        for k in ref:
            texts.append(KB[k]["text"])
            srcs.append(KB[k]["source"])
        return "".join(texts), srcs
    if kind == "multi":
        texts = [KB[k]["text"] for k in ref]
        srcs = [KB[k]["source"] for k in ref]
        return "".join(texts), srcs
    if isinstance(ref, dict):
        s = ref
        extra = row.get("ans") or ""
        body = ("来自%s《%s》（%s）的公开页面，链接可打开核对原文；具体细节以页面内容为准，我不做转述推测。"
                % (s["name"], s["doc"], s["date"]))
        return (extra + "\n" if extra else "") + body, [s]
    return KB[ref]["text"], [KB[ref]["source"]]


def all_spec():
    from kb_spec import SPEC
    from kb_extra import extra_spec
    from kb_products import extra_spec as products_spec
    from kb_phrasings import spec_list
    from kb_spirit import extra_spec as spirit_spec
    from kb_scenic import scenic_spec
    from kb_sites import site_kb_entries
    return (SPEC + extra_spec() + products_spec() + spec_list() + spirit_spec()
            + scenic_spec() + site_kb_entries())


def build_rows():
    rows = []
    registry = {}
    for r in all_spec():
        ans, srcs = resolve(r)
        if "ans" in r:
            ans = r["ans"]
        for ex in r.get("extra", []):
            if ex not in srcs:
                srcs = [ex] + srcs
        ids = []
        for s in srcs:
            key = (s["name"], s["doc"], s["date"], s["url"])
            if key not in registry:
                registry[key] = "S%02d" % (len(registry) + 1)
                SOURCE_INDEX[registry[key]] = {
                    "id": registry[key], "org": s["name"], "doc": s["doc"],
                    "date": s["date"], "url": s["url"],
                }
            if registry[key] not in ids:
                ids.append(registry[key])
        first = srcs[0]
        rows.append({
            "id": r["id"],
            "q": r["q"],
            "a": ans,
            "src_ids": ids,
            "org": first["name"],
            "doc": first["doc"],
            "date": first["date"],
            "url": first["url"],
            "conf": r.get("conf", "高"),
            "scene": r.get("scene", "参观中"),
            "kind": {"fact": "史实", "boundary": "拒答样板", "service": "服务信息", "combo": "史实",
                     "page": "待补细节"}.get(r.get("kind", "fact"), "史实"),
            "image": r.get("image"),
        })
    return rows, registry


if __name__ == "__main__":
    rows, reg = build_rows()
    print("rows", len(rows), "sources", len(reg))
    for x in rows[:3]:
        print(x["src_ids"], x["q"], "|", x["a"][:40])
