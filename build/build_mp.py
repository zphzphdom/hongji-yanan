# -*- coding: utf-8 -*-
"""把 web 端的检索引擎与知识库转成小程序可用的模块。

产物：
  miniprogram/utils/engine.js   （与 web/engine.js 同一份逻辑）
  miniprogram/data/kb.js        （module.exports = 知识库 JSON）
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MP = os.path.join(ROOT, "miniprogram")


def main():
    os.makedirs(os.path.join(MP, "utils"), exist_ok=True)
    os.makedirs(os.path.join(MP, "data"), exist_ok=True)

    src = open(os.path.join(ROOT, "web", "engine.js"), encoding="utf-8").read()
    # 小程序基础库里没有 window，旧版本也可能没有 globalThis
    src = src.replace(
        "})(typeof window !== 'undefined' ? window : globalThis);",
        "})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));",
    )
    if "module.exports = api" not in src:
        src += "\nif (typeof module !== 'undefined') module.exports = api;\n"
    with open(os.path.join(MP, "utils", "engine.js"), "w", encoding="utf-8") as f:
        f.write(src)

    kb = json.load(open(os.path.join(ROOT, "data", "kb.json"), encoding="utf-8"))
    with open(os.path.join(MP, "data", "kb.js"), "w", encoding="utf-8") as f:
        f.write("/* 自动生成：build/build_mp.py，勿手改 */\nmodule.exports = ")
        json.dump(kb, f, ensure_ascii=False)
        f.write(";\n")
    print("小程序数据已生成：%d 条 / %d 个来源 / v%s" % (kb["count"], kb["sources"], kb["version"]))


if __name__ == "__main__":
    main()
