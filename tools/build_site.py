# -*- coding: utf-8 -*-
"""把 web/ 打成 GitHub Pages 站点（输出到 docs/），并为固定网址生成二维码。

GitHub Pages 只能从仓库根目录或 /docs 发布，所以站点副本放 docs/。
Pages 是纯静态：没有 /api，页面自动退回内嵌知识库 kb.js（离线精确模式）。
"""
import os
import shutil

from make_qr import make

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
DOCS = os.path.join(ROOT, "docs")
FILES = ["index.html", "style.css", "app.js", "engine.js", "kb.js", "qr.png"]


def main(pages_url):
    os.makedirs(DOCS, exist_ok=True)
    for name in FILES:
        src = os.path.join(WEB, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DOCS, name))
    make(pages_url)  # 固定网址的二维码：docs/qr.png + 仓库根 二维码.png
    print("站点已输出到 docs/，二维码指向 %s" % pages_url)


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.github.io/hongji-yanan/"
    main(url)
