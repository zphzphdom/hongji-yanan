# -*- coding: utf-8 -*-
"""无 git 客户端发布：GitHub REST API 建仓 + 一次提交 + 开 Pages。

用法（token 只从环境变量读，不落盘）：
  set GH_TOKEN=github_pat_xxx
  python tools/publish_github.py --repo hongji-yanan --pages-path /docs
"""
import base64
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN", "").strip()

# 本机 DNS 解析 github.com 不稳定时，固定 IP + 正常 SNI 兜底
PIN = {
    "api.github.com": ["140.82.112.6", "140.82.113.6", "140.82.114.6", "140.82.121.6"],
    "github.com": ["140.82.112.4", "140.82.113.4"],
}
_pin_state = {}
_orig_gai = socket.getaddrinfo


def _gai(host, port, *a, **k):
    ip = _pin_state.get(host) or (PIN.get(host) or [None])[0]
    if ip:
        return _orig_gai(ip, port, *a, **k)
    return _orig_gai(host, port, *a, **k)


socket.getaddrinfo = _gai


def _probe():
    """挑一个能连通的 api.github.com IP。"""
    for ip in PIN["api.github.com"]:
        _pin_state["api.github.com"] = ip
        try:
            r = urllib.request.Request("https://api.github.com/zen", headers={"User-Agent": "x"})
            with urllib.request.urlopen(r, timeout=12) as x:
                if x.status == 200:
                    print("GitHub API 走固定 IP：", ip)
                    return
        except Exception:
            continue
    print("警告：固定 IP 都不通，按系统 DNS 继续")

SKIP_DIRS = {"__pycache__", ".git", "node_modules"}
SKIP_FILES = {"data/config.json", "data/usage.jsonl", "docs/cf.log", "docs/_st.txt"}
SKIP_PREFIX = (".dsh-office-",)
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".docx", ".xlsx", ".pptx", ".pdf", ".zip", ".ico"}


def call(method, path, data=None, ok=(200, 201, 204)):
    url = path if path.startswith("http") else API + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "hongji-publish",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(r, timeout=60) as x:
            raw = x.read()
            return x.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def collect():
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(SKIP_PREFIX)]
        for f in files:
            full = os.path.join(base, f)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            if rel in SKIP_FILES or f.endswith(".pyc") or rel.startswith(SKIP_PREFIX):
                continue
            out.append((rel, full))
    return sorted(out)


def main():
    if not TOKEN:
        sys.exit("缺少 GH_TOKEN 环境变量")
    repo = "hongji-yanan"
    pages_path = "/docs"
    args = sys.argv[1:]
    if "--repo" in args:
        repo = args[args.index("--repo") + 1]
    if "--pages-path" in args:
        pages_path = args[args.index("--pages-path") + 1]

    _probe()
    s, me = call("GET", "/user")
    if s != 200:
        sys.exit("token 无效：%s %s" % (s, me))
    owner = me["login"]
    print("账号：", owner)

    s, info = call("GET", "/repos/%s/%s" % (owner, repo))
    if s == 404:
        s, info = call("POST", "/user/repos", {
            "name": repo, "description": "红迹·延安：带来源的红色文旅 AI 问答讲解员与分享卡",
            "private": False, "auto_init": False, "has_issues": True, "has_wiki": False,
        })
        print("建仓：", s, info.get("full_name"))
    else:
        print("仓库已存在：", info.get("full_name"))
    if s not in (200, 201):
        sys.exit("建仓失败：%s %s" % (s, info))

    files = collect()
    print("待上传 %d 个文件" % len(files))

    # Git Data API 在空仓库上会返回 409，先用 Contents API 落一个初始提交
    s, ref = call("GET", "/repos/%s/%s/git/ref/heads/main" % (owner, repo))
    if s != 200 or "object" not in (ref or {}):
        s2, init = call("PUT", "/repos/%s/%s/contents/.gitkeep" % (owner, repo), {
            "message": "init", "content": base64.b64encode(b" ").decode()})
        if s2 not in (200, 201, 422):
            sys.exit("初始化提交失败：%s %s" % (s2, init))
        s, ref = call("GET", "/repos/%s/%s/git/ref/heads/main" % (owner, repo))
    if "object" not in (ref or {}):
        sys.exit("拿不到 main 分支：%s %s" % (s, ref))
    parent = ref["object"]["sha"]
    print("父提交：", parent[:10])

    tree, blobs = [], 0
    for rel, full in files:
        ext = os.path.splitext(rel)[1].lower()
        if ext in BINARY_EXT:
            with open(full, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            s, b = call("POST", "/repos/%s/%s/git/blobs" % (owner, repo),
                        {"content": b64, "encoding": "base64"})
            if s != 201:
                sys.exit("blob 失败 %s：%s %s" % (rel, s, b))
            tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": b["sha"]})
            blobs += 1
        else:
            with open(full, encoding="utf-8") as f:
                tree.append({"path": rel, "mode": "100644", "type": "blob", "content": f.read()})

    s, t = call("POST", "/repos/%s/%s/git/trees" % (owner, repo), {"tree": tree})
    if s != 201:
        sys.exit("tree 失败：%s %s" % (s, t))
    s, c = call("POST", "/repos/%s/%s/git/commits" % (owner, repo), {
        "message": "红迹·延安 v2：延安全域 91 条带来源问答 + 在线模型改写 + 问答卡",
        "tree": t["sha"], "parents": [parent],
    })
    if s != 201:
        sys.exit("commit 失败：%s %s" % (s, c))
    s, ref2 = call("PATCH", "/repos/%s/%s/git/refs/heads/main" % (owner, repo),
                   {"sha": c["sha"], "force": True})
    if s not in (200, 201):
        sys.exit("更新分支失败：%s %s" % (s, ref2))
    print("已推送 commit：", c["sha"][:10])

    s, pg = call("GET", "/repos/%s/%s/pages" % (owner, repo))
    if s == 404:
        s, pg = call("POST", "/repos/%s/%s/pages" % (owner, repo),
                     {"source": {"branch": "main", "path": pages_path}})
        print("开启 Pages：", s, pg.get("html_url") or pg)
    else:
        s2, pg2 = call("PUT", "/repos/%s/%s/pages" % (owner, repo),
                       {"source": {"branch": "main", "path": pages_path}})
        print("Pages 已存在，更新源：", s2)

    for _ in range(12):
        s, pg = call("GET", "/repos/%s/%s/pages" % (owner, repo))
        if s == 200 and pg.get("status") in ("built", "building"):
            break
        time.sleep(5)

    result = {
        "repo": "https://github.com/%s/%s" % (owner, repo),
        "pages": "https://%s.github.io/%s/" % (owner.lower(), repo),
        "files": len(files), "blobs": blobs,
        "pages_status": pg.get("status") if isinstance(pg, dict) else None,
    }
    with open(os.path.join(ROOT, "docs", "publish.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
