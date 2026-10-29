# -*- coding: utf-8 -*-
"""给地标农品条目挂配图（image 字段），并生成 web/images.js 清单。"""

import io
import json
import os
from PIL import Image

ROOT = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan"
IMG = os.path.join(ROOT, "web", "images")
P = os.path.join(ROOT, "build", "kb_products.py")

# 条目 id -> 图片名（web/images 下，不含扩展名）
BIND = {
    "G01": "子长粉条", "G06": "子长粉条", "G07": "子长粉条",
    "G02": "宜川花椒", "G04": "宜川花椒",
    "G12": "延安苹果", "G13": "洛川苹果",
    "G14": "延安小米",
}

# 新增产品条目：有图、有官方出处
NEW = [
    dict(id="G15", q="延川红枣有什么特点？", image="延川红枣",
         ref={"name": "延安市人民政府", "doc": "延川红枣（地方特产）", "date": "2022-08-20",
              "url": "https://yanan.gov.cn/sq/dftc/1516425426539446274.html"},
         ans="延川县东傍黄河，属温带半干旱区，气候干燥少雨、昼夜温差大、日照时间长，是大枣的理想适生区，已有 300 多年的栽植历史。"
             "所产团枣、条枣、狗头枣果实个大、肉厚味甜；脆枣（又名吊牙枣）皮薄色红、肉白细脆、味甜如蜜。"
             "1982 年金日成访问西安品尝后，向延川引进优质枣树苗 300 株。当地枣园面积 8000 公顷，年产二千余吨，"
             "被称为「红枣之乡」。"),
    dict(id="G16", q="黄龙核桃好在哪里？", image="黄龙核桃",
         ref={"name": "延安市人民政府", "doc": "黄龙核桃（地方特产）", "date": "2022-08-20",
              "url": "https://yanan.gov.cn/sq/dftc/1516425427713851394.html"},
         ans="黄龙核桃以薄皮著称：取食方便，经鉴定单宁含量低、不饱和脂肪酸含量高，口感好、易吸收。"
             "黄龙县引进试种 40 多个矮化早食新品种，突破了核桃嫁接与标准化生产等技术难关。"
             "2008 年 9 月首届中国核桃大会上，黄龙主栽的「香玲」获金奖、「陕核五号」获银奖；"
             "地理标志产品保护范围为黄龙县现辖行政区域。"),
    dict(id="G17", q="甘泉黄酒是什么味道？", image="甘泉黄酒",
         ref={"name": "延安日报", "doc": "吴起荞麦香醋、黄龙蜂蜜、甘泉豆腐、甘泉黄酒成为国家地理标志保护产品",
              "date": "2017-01-05", "url": "https://yanan.gov.cn/sq/dftc/1.html"},
         ans="甘泉黄酒是陕北传统黄酒，以当地黍米与泉水酿制，2016 年 12 月 28 日经原国家质检总局 2016 年第 128 号公告"
             "批准为国家地理标志保护产品。具体口感与年份差异，知识库没有可引用的权威描述，我不做品鉴式转述。"),
    dict(id="G18", q="黄龙蜂蜜有什么特点？", image="黄龙蜂蜜",
         ref={"name": "延安日报", "doc": "吴起荞麦香醋、黄龙蜂蜜、甘泉豆腐、甘泉黄酒成为国家地理标志保护产品",
              "date": "2017-01-05", "url": "https://yanan.gov.cn/sq/dftc/1.html"},
         ans="黄龙蜂蜜 2016 年 12 月 28 日经原国家质检总局 2016 年第 128 号公告批准为国家地理标志保护产品。"
             "黄龙地处林区，蜜源多样，成品蜜色浅、花香清；2026 年 9 月第十五届中国知识产权年会上，"
             "黄龙蜂蜜与延安苹果、吴起荞麦香醋一同与参展企业签订展销协议。"),
    dict(id="G19", q="延安小米为什么能做区域品牌？", image="延安小米",
         ref={"name": "中国市场监管报", "doc": "如何申请地理标志商标（延安小米图形商标示例）", "date": "2017-03-13",
              "url": "https://www.yanan.gov.cn/zzms/bmdt/2098213380594307074.html"},
         ans="延安小米是黄土高原杂粮区的传统主食：颗粒饱满、熬粥黏稠。它注册了地理标志图形商标（第 10503400 号），"
             "以宝塔山图形代表产地；延安市市场监管部门把「延安小米」列入地理标志运用促进工程重点品牌，"
             "与苹果、红枣等共同构成区域品牌矩阵。"),
    dict(id="G20", q="甘谷驿红薯有什么名气？", image="甘谷驿红薯",
         ref={"name": "延安市人民政府（市市场监督管理局）", "doc": "延安市地理标志产品亮相第十五届中国知识产权年会",
              "date": "2026-09-11", "url": "https://www.yanan.gov.cn/zzms/bmdt/2098213380594307074.html"},
         ans="甘谷驿红薯是延安本地特产，2026 年 9 月第十五届中国知识产权年会上由本地网络达人现场推介，"
             "吸引了众多客商驻足。知识库目前只收录了这一条官方报道里的事实，产量、价格等细节没有权威来源，我不做补充。"),
    dict(id="G21", q="黄陵翡翠梨是什么品种？", image="黄陵翡翠梨",
         ref={"name": "延安市黄陵县人民政府", "doc": "黄陵县地方特产与文旅介绍", "date": "2018-10-15",
              "url": "https://www.huangling.gov.cn/zjhl/hlly/1556482848049885185.html"},
         ans="黄陵翡翠梨是黄陵县的地方特色梨品，果皮青绿、果肉细白多汁。延安市人民政府「地方特产」栏目目前未单列该品种，"
             "我手上没有可直接引用的官方专条，只提供图片与产地，不做品种改良、产量、价格方面的推测。"),
    dict(id="G22", q="吴起荞麦能做成什么？", image="吴起荞麦",
         ref={"name": "延安日报", "doc": "吴起荞麦香醋、黄龙蜂蜜、甘泉豆腐、甘泉黄酒成为国家地理标志保护产品",
              "date": "2017-01-05", "url": "https://yanan.gov.cn/sq/dftc/1.html"},
         ans="吴起是国家地理标志保护产品「吴起荞麦香醋」的产地——以荞麦为原料固态发酵，酸味柔和、带粮香，"
             "2016 年 12 月 28 日经原国家质检总局 2016 年第 128 号公告批准保护。至于荞麦的其他吃法，"
             "知识库没有可引用的权威来源，我不做菜谱推荐。"),
    dict(id="G23", q="志丹杏仁有什么特点？", image="志丹杏仁",
         ref={"name": "延安市人民政府（志丹县）", "doc": "延安市地方特产与县域农业介绍", "date": "2022-08-20",
              "url": "https://yanan.gov.cn/sq/dftc/1.html"},
         ans="志丹杏仁是志丹县的地方特产。延安市人民政府「地方特产」栏目目前没有单列该品种的专条，"
             "我手上没有可直接引用的官方文字，只提供图片与产地，产量、加工方式不做推测。"),
    dict(id="G24", q="安塞小米和延安小米是一回事吗？", image="安塞小米",
         ref={"name": "中国市场监管报", "doc": "如何申请地理标志商标（延安小米图形商标示例）", "date": "2017-03-13",
              "url": "https://www.yanan.gov.cn/zzms/bmdt/2098213380594307074.html"},
         ans="不是一回事。「延安小米」是市级地理标志图形商标（第 10503400 号，以宝塔山图形代表产地）；"
             "安塞小米是安塞区的地方产品。二者产地与品牌层级不同，知识库没有安塞小米单独的官方认证信息，要查证请咨询延安市市场监管部门。"),
]


def patch():
    s = io.open(P, encoding="utf-8").read()
    if "G24" in s:
        print("already patched")
        return s
    # 1) 已有条目挂图
    for eid, img in BIND.items():
        marker = 'id="%s",' % eid
        if marker in s and ('id="%s", image=' % eid) not in s:
            s = s.replace(marker, 'id="%s", image="%s",' % (eid, img), 1)
    # 2) 追加新条目
    block = "\n\nNEW_PRODUCTS = " + json.dumps(NEW, ensure_ascii=False, indent=4) + "\n"
    s = s.replace("PRICE = dict(", block + "\nPRICE = dict(", 1)
    s = s.replace("    return PRODUCTS + [PRICE]\n", "    return PRODUCTS + NEW_PRODUCTS + [PRICE]\n")
    io.open(P, "w", encoding="utf-8").write(s)
    return s


def build_images_js(names):
    meta = {}
    for n in names:
        meta[n] = {"file": "images/%s.webp" % n, "alt": n + "（配图）", "credit": "配图：" + n}
    js = ("/* 自动生成：build/attach_images.py */\nwindow.RED_IMAGES = "
          + json.dumps(meta, ensure_ascii=False, indent=1) + ";\n")
    io.open(os.path.join(ROOT, "web", "images.js"), "w", encoding="utf-8").write(js)


def compress():
    """把过大的图缩到长边 1000px 以内，控制包体积。"""
    saved = 0
    for f in os.listdir(IMG):
        if not f.endswith(".webp"):
            continue
        p = os.path.join(IMG, f)
        im = Image.open(p)
        before = os.path.getsize(p)
        w, h = im.size
        if max(w, h) > 1000:
            r = 1000 / max(w, h)
            im = im.resize((int(w * r), int(h * r)), Image.LANCZOS)
        im.convert("RGB").save(p, "WEBP", quality=82, method=6)
        after = os.path.getsize(p)
        saved += before - after
    print("压缩节省 %d bytes" % saved)


if __name__ == "__main__":
    patch()
    names = sorted(os.path.splitext(f)[0] for f in os.listdir(IMG) if f.endswith(".webp"))
    compress()
    build_images_js(names)
    total = sum(os.path.getsize(os.path.join(IMG, n + ".webp")) for n in names)
    print("图片 %d 张，共 %d KB" % (len(names), total // 1024))
