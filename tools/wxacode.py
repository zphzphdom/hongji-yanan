# -*- coding: utf-8 -*-
"""生成微信小程序码（wxacode.getUnlimited）。

前置条件（缺一不可）：
  1. 小程序已注册并完成主体认证，拿到 AppID；
  2. 在「开发管理 → 开发设置」里生成 AppSecret；
  3. 代码已上传并在后台「提交审核 / 发布」（未发布也能生成码，但扫了打不开）。

用法：
  set WX_APPID=wx1234567890abcdef
  set WX_SECRET=你的appsecret
  python tools/wxacode.py --page pages/index/index --scene poster

产物：
  小程序码.png（430×430，带边框留白）
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def api(url, data=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    appid = os.environ.get("WX_APPID", "").strip()
    secret = os.environ.get("WX_SECRET", "").strip()
    if not appid or not secret:
        sys.exit("缺少 WX_APPID / WX_SECRET 环境变量（小程序后台 → 开发管理 → 开发设置）")

    page = "pages/index/index"
    scene = "poster"
    args = sys.argv[1:]
    if "--page" in args:
        page = args[args.index("--page") + 1]
    if "--scene" in args:
        scene = args[args.index("--scene") + 1]

    tok = json.loads(api(
        "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=%s&secret=%s"
        % (urllib.parse.quote(appid), urllib.parse.quote(secret))
    ))
    if "access_token" not in tok:
        sys.exit("拿不到 access_token：%s" % tok)

    body = {
        "scene": scene,
        "page": page,
        "width": 430,
        "auto_color": False,
        "line_color": {"r": 140, "g": 31, "b": 40},
        "is_hyaline": False,
    }
    req = urllib.request.Request(
        "https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token=" + tok["access_token"],
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        blob = r.read()

    if blob[:1] == b"{":
        sys.exit("微信返回错误：%s" % blob.decode("utf-8", "ignore"))

    for name in ("小程序码.png", os.path.join("miniprogram", "images", "wxacode.png")):
        path = os.path.join(ROOT, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(blob)
    print("小程序码已生成：小程序码.png（%d 字节）→ page=%s scene=%s" % (len(blob), page, scene))


if __name__ == "__main__":
    main()
