# -*- coding: utf-8 -*-
"""重写 web_image：从相关网页抓正文主图（og:image 优先）。"""

import io

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\server.py"
s = io.open(P, encoding="utf-8").read()
start = s.find("def web_image(keywords, timeout=6):")
end = s.find("# ---------------------------------------------------------------- 问答卡文案")
assert start > 0 and end > start

NEW = r'''def _page_first_image(page_url, timeout=6):
    """从网页里取一张正文主图：优先 og:image，其次正文里第一张合格大图。"""
    try:
        req = urllib.request.Request(page_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.baidu.com/"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type") or ""
            if "html" not in ctype and "xml" not in ctype:
                return None
            html = r.read(400000).decode("utf-8", "ignore")
    except Exception:
        return None

    cands = []
    m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*content=["\']([^"\']+)', html, re.I)
    if m:
        cands.append(m.group(1))
    m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\']', html, re.I)
    if m:
        cands.append(m.group(1))
    cands += re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)[:40]

    for c in cands:
        if not c or c.startswith("data:"):
            continue
        if re.search(r"(logo|icon|avatar|qrcode|share|blank|spacer|ad_)", c, re.I):
            continue
        u = urllib.parse.urljoin(page_url, c)
        if not IMG_OK.search(u.split("?")[0]):
            continue
        if any(h in u for h in IMG_BAD_HOST):
            continue
        if _url_alive(u):
            return u
    return None


def web_image(keywords, timeout=8):
    """从网络取一张与关键词相关的图：先看检索结果有没有图片直链，再从相关网页抓主图。"""
    if not keywords:
        return None
    key = "|".join(keywords[:2])
    cache = _img_cache()
    if key in cache:
        return cache[key] or None

    cfg = llm_config()
    found = None
    if cfg["key"] and cfg["search_on"]:
        results = []
        for q in (" ".join(keywords), " ".join(keywords) + " 图片"):
            try:
                results += ds_search(cfg, q, timeout=timeout)
            except Exception:
                pass

        for w in results:
            u = w.get("url") or ""
            if IMG_OK.search(u) and not any(h in u for h in IMG_BAD_HOST) and _url_alive(u):
                found = {"url": u, "credit": "图源：" + (w.get("site") or "网络"),
                         "alt": " ".join(keywords)}
                break

        if not found:
            GOOD = ("gov.cn", "xinhuanet", "people.com.cn", "cnwest.com", "hsw.cn", "gmw.cn", "cnr.cn")
            ranked = sorted(results, key=lambda w: 0 if any(d in (w.get("url") or "") for d in GOOD) else 1)
            for w in ranked[:4]:
                u = _page_first_image(w.get("url") or "")
                if u:
                    found = {"url": u, "credit": "图源：" + (w.get("site") or "相关报道"),
                             "alt": " ".join(keywords)}
                    break
    _img_cache_put(key, found)
    return found


'''

s = s[:start] + NEW + s[end:]
io.open(P, "w", encoding="utf-8").write(s)
import ast
ast.parse(s)
print("web_image rewritten; syntax ok")
