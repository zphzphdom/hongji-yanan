# -*- coding: utf-8 -*-
"""按内容哈希把用户提供的 20 张图片收进 web/images/，文件名即条目名。"""

import os
import shutil

ATT = r"C:\Users\zph\.dsh\attachments\v1\objects"
DST = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\web\images"

# 文件显示名 -> 内容哈希（同一张图在不同轮次可能重复出现，只保留一份）
IMAGES = {
    "子长粉条": "0be97afbf4d1a942b921316c9bb0e212e2178fa77c197bab561764ac4cac111f",
    "宜川花椒": "69e732e8e69a73ea9574ae026cd2614b82967da482b164aa95ffefa8ef9c51b2",
    "安塞小米": "70c803c35c124802e69e863e3f308f8bc46c00e2c810e5e95a6cc4f15f851549",
    "宝塔山": "a46c4827a0010232d88d78d60a0e4ecc24d1957d56fa8c6a2c8ff4aaa5f39142",
    "宝塔山·日出": "cfd7f9c3d2ab54b78eea5c3d542b39d87383c6048507f1a26ec87ab3f7c645ca",
    "宝塔山·仰拍": "b9e47310fa8c1be120869b45a44efaab32aebda64c530366878e746ce5cd434b",
    "宝塔山·林间": "4c5881cba7ffa208151a6f4da3457f008f3d98973aab497e4852b3e8fbe321a7",
    "宝塔山·雪后": "f9e1fcffcb8303f1b35cac7ef1670c70fa8cc15977ff470ec8ca172e2b0a6a7e",
    "宝塔山·延河": "f1769c4ba91de020c1aece9ee6446121eac8f571bf1bfefee75e7f597c60b984",
    "甘谷驿红薯": "634b331dfebf6f579ae0587f3c1bc7e6df1071b7b8894896388f43faf24e40ea",
    "甘泉黄酒": "9942b3a10ab377fdcc0d83e115c0975685cce66fe2b09f2d3cb858f5835497d0",
    "黄陵翡翠梨": "d6c905eba2e5b5ece9f241f3578024bb7d10cb2a1059faf67d5a02f8ff60aff2",
    "黄龙蜂蜜": "d61316cee902f927d280a5d22fc3f41dcb1ece17f79c8e549dd881e63554d1cd",
    "黄龙核桃": "c6ec1787b2c4ce95f0ff61b69b07262291d03d8c2b33afb5f158ed26d3f73012",
    "洛川苹果": "f65e3eb32272ddee982a6edc0c83f6ed145c606888f9be4da30e39ac2c7d36f1",
    "吴起荞麦": "566616c39106c08c25956cc6befda5cc5190a7b69d334cba844a853018add523",
    "延安苹果": "f9fc563e022a9f6d319efc36137daa9f0a429e42137caa6453462263da0b0e04",
    "延安小米": "e016fc439701bd89e2a93c7ba15fc92604bfc98efbeace829588d5c4e524cea1",
    "志丹杏仁": "5c9b5c56421cf1a03c531e15a19b3095408851336a87ab93702d1e372c554e0d",
}

EXTRA = {"甘谷驿红薯": "甘谷驿红薯"}


def main():
    os.makedirs(DST, exist_ok=True)
    index = {}
    for base, _dirs, files in os.walk(ATT):
        for f in files:
            index[f] = os.path.join(base, f)

    ok, miss = [], []
    for name, h in IMAGES.items():
        src = index.get(h)
        if not src:
            miss.append(name)
            continue
        dst = os.path.join(DST, name + ".webp")
        shutil.copy2(src, dst)
        ok.append((name, os.path.getsize(dst)))

    print("已收录 %d 张：" % len(ok))
    for n, sz in ok:
        print("  %-14s %7d bytes" % (n, sz))
    if miss:
        print("缺图：", miss)
    return ok


if __name__ == "__main__":
    main()
