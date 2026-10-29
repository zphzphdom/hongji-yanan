# -*- coding: utf-8 -*-
"""生成二维码：python tools/make_qr.py https://你的地址

输出 二维码.png（900×900，纠错 H）与 web/qr.png（问答卡上使用）。
"""
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make(url, size=900):
    q = ("https://api.qrserver.com/v1/create-qr-code/?size=%dx%d&ecc=H&margin=10&data=%s"
         % (size, size, urllib.parse.quote(url, safe="")))
    data = urllib.request.urlopen(q, timeout=30).read()
    for path in (os.path.join(ROOT, "二维码.png"), os.path.join(ROOT, "web", "qr.png")):
        with open(path, "wb") as f:
            f.write(data)
    with open(os.path.join(ROOT, "docs", "PUBLIC_URL.txt"), "w", encoding="utf-8") as f:
        f.write(url + "\n")
    print("二维码已生成：%s（%d 字节）" % (url, len(data)))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python tools/make_qr.py https://example.com")
        sys.exit(1)
    make(sys.argv[1])
