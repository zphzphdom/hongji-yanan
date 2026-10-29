# -*- coding: utf-8 -*-
"""把 main 的 docs/ 同步到 gh-pages 分支（GitHub Pages 实际发布的是这个分支）。"""

import base64
import json
import os
import socket
import sys
import urllib.error
import urllib.request

ROOT = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan"
API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN", "").strip()
REPO = "zphzphdom/hongji-yanan"
DOCS = os.path.join(ROOT, "docs")
BINARY = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"}

_orig = socket.getaddrinfo


def _gai(host, port, *a, **k):
    if host == "api.github.com":
        return _orig("140.82.112.6", port, *a, **k)
    return _orig(host, port, *a, **k)


socket.getaddrinfo = _gai


def call(m, p, d=None):
    body = json.dumps(d).encode() if d is not None else None
    r = urllib.request.Request(API + p, data=body, method=m, headers={
        "Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json",
        "User-Agent": "hongji-sync", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as x:
            raw = x.read()
            return x.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    if not TOKEN:
        sys.exit("缺少 GH_TOKEN")
    s, ref = call("GET", "/repos/%s/git/ref/heads/main" % REPO)
    parent = ref["object"]["sha"]

    tree = []
    for name in os.listdir(DOCS):
        path = os.path.join(DOCS, name)
        if os.path.isdir(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in BINARY:
            with open(path, "rb") as f:
                s, b = call("POST", "/repos/%s/git/blobs" % REPO,
                            {"content": base64.b64encode(f.read()).decode(), "encoding": "base64"})
            if s != 201:
                sys.exit("blob 失败 %s: %s" % (name, s))
            tree.append({"path": name, "mode": "100644", "type": "blob", "sha": b["sha"]})
        else:
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except UnicodeDecodeError:
                with open(path, "rb") as f:
                    s, b = call("POST", "/repos/%s/git/blobs" % REPO,
                                {"content": base64.b64encode(f.read()).decode(), "encoding": "base64"})
                tree.append({"path": name, "mode": "100644", "type": "blob", "sha": b["sha"]})
                continue
            tree.append({"path": name, "mode": "100644", "type": "blob", "content": text})

    s, t = call("POST", "/repos/%s/git/trees" % REPO, {"tree": tree})
    if s != 201:
        sys.exit("tree 失败：%s" % s)
    s, c = call("POST", "/repos/%s/git/commits" % REPO,
                {"message": "gh-pages: 同步最新站点", "tree": t["sha"], "parents": [parent]})
    if s != 201:
        sys.exit("commit 失败：%s" % s)
    s, r = call("PATCH", "/repos/%s/git/refs/heads/gh-pages" % REPO, {"sha": c["sha"], "force": True})
    print("gh-pages 已更新：", s, c["sha"][:10], "| 文件", len(tree))


if __name__ == "__main__":
    main()
