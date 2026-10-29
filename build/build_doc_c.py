# -*- coding: utf-8 -*-
"""生成 09_微信小程序上架与小程序码.docx"""
import json
import os

from common import OUT
from docx_kit import GREY, bullet, h1, h2, new_doc, num_item, p, quote, table, title

FOOT = "红迹·延安 ｜ AI 问答讲解员与分享卡 ｜ 参赛材料"


def main():
    mp = json.load(open(os.path.join(OUT, "docs", "selftest_mp.json"), encoding="utf-8"))
    doc = new_doc(footer_text=FOOT)
    title(doc, "微信小程序上架与小程序码", "工程已就绪，缺的只有你的 AppID")

    h1(doc, "先说清楚：哪一步我做不了", "1")
    p(doc, "小程序码不是画出来的，是微信后台用 AppID + AppSecret 换出来的。注册、实名、审核、发布这四步必须由账号主体完成，"
           "任何第三方都替代不了。本作品已经把**除这四步之外的全部工作**做完：可直接导入开发者工具的工程、真机构建、"
           "一条命令出小程序码的脚本。", indent=True)

    h1(doc, "三种“扫码打开”别混为一谈", "2")
    table(doc, ["方式", "扫出来是什么", "需要什么", "适合"], [
        ["小程序码", "直接打开小程序指定页面", "已注册小程序 + AppID/AppSecret", "海报、展签、文创卡片（首选）"],
        ["普通链接二维码", "先扫到 https 链接，微信按后台规则跳到小程序", "小程序 + 后台配置映射规则 + 域名校验文件", "已有网页版、想复用同一张码"],
        ["H5 二维码", "打开网页（不是小程序）", "无", "答辩现场、临时演示（已可用）"],
    ], widths=[3.0, 6.2, 5.2, 2.2], size=9, align_center=[0])

    h1(doc, "上架流程（约 30 分钟 + 审核等待）", "3")
    steps = [
        ("① 注册", "mp.weixin.qq.com → 立即注册 → 小程序。个人主体可用身份证+手机号；场馆/学校建议企业主体，类目更宽。"),
        ("② 拿凭证", "开发管理 → 开发设置：复制 AppID，生成 AppSecret（只显示一次，存好）。"),
        ("③ 导入工程", "微信开发者工具 → 导入项目 → 目录选 hongji-yanan/miniprogram → AppID 填你自己的"
                    "（现在写的是 touristappid，游客模式，只能本地预览）。"),
        ("④ 模拟器自检", "依次点 8 个快捷问题、切三种模式、点来源弹窗、生成问答卡、保存到相册。全过再进行下一步。"),
        ("⑤ 真机预览", "工具右上角“预览”，手机扫码。注意：真机上相册权限、字体渲染与模拟器略有差异。"),
        ("⑥ 上传", "工具右上角“上传”，版本号 1.0.0，备注写“延安红色文旅史实问答，回答带来源”。"),
        ("⑦ 提审", "后台 → 版本管理 → 提交审核。类目建议：工具 → 信息查询，或 教育 → 在线教育。"
                 "说明里写清“只回答知识库内 91 条带来源史实，超出即拒答”。"),
        ("⑧ 发布", "审核通过后点“发布”。发布前扫小程序码只能看到“开发版”，发布后才是正式版。"),
        ("⑨ 出码", "python tools/wxacode.py --page pages/index/index --scene poster"
                 "（需要 WX_APPID / WX_SECRET 环境变量），或在后台“设置 → 基本设置 → 小程序码”下载。"),
        ("⑩ 回填", "把生成的码覆盖到 miniprogram/images/wxacode.png，问答卡上的占位框会自动变成真码。"),
    ]
    for k, v in steps:
        bullet(doc, "**%s**：%s" % (k, v))

    h1(doc, "问答卡上的码怎么放", "4")
    p(doc, "卡片右下角预留了 250×250 的码位。工程会尝试加载 miniprogram/images/wxacode.png：", indent=True)
    table(doc, ["情况", "卡片表现"], [
        ["还没有码", "画一个虚线框，写“小程序码 / 红迹·延安”，不影响保存与转发"],
        ["放入了真码", "自动渲染二维码，下方固定文案“扫码继续问”"],
    ], widths=[4.6, 12.0], size=9.5, align_center=[0])

    h1(doc, "审核最容易被卡的四点", "5")
    num_item(doc, 1, "**内容合规**：涉及党史内容，必须能说明来源。把《02_知识库》的来源列印成附件，随审核备注一起提交；"
                     "回答里已经带机构、文件、日期，这是最有力的材料。")
    num_item(doc, 2, "**类目不符**：不要选“新闻资讯”，选“工具-信息查询”或“教育-在线教育”，与实际功能一致。")
    num_item(doc, 3, "**诱导分享**：文案里不要出现“分享才能生成/解锁”。本作品是“愿意分享才分享”，符合规范。")
    num_item(doc, 4, "**收集个人信息**：本作品不做登录、不收集手机号；`data/usage.jsonl` 只在自建服务端记录问句与命中，"
                     "小程序端不落盘。")

    h1(doc, "联网改写为什么默认关闭", "6")
    p(doc, "小程序的 `wx.request` 只能访问**已备案并加入 request 合法域名**的 https 域名。`onrender.com` 这类境外域名"
           "不能直接填。所以小程序端默认 `useLLM = false`，走离线精确检索（91 条全在本地，断网也能答）。", indent=True)
    p(doc, "要开联网改写，按这个顺序：① 备案一个域名 → ② 反向代理到自建服务（server.py 或 Render）→ "
           "③ 小程序后台配置 request 合法域名 → ④ 改 miniprogram/app.js 里的 useLLM 与 apiBase。"
           "事实层不变，只是把“怎么说”交给模型。", indent=True)

    h1(doc, "小程序端自测结果", "7")
    table(doc, ["指标", "结果", "说明"], [
        ["知识库", "%d 条 / %d 个来源" % (mp["kb"]["count"], mp["kb"]["sources"]), "与 Web 端同一份 data/kb.json 生成"],
        ["自身问法命中", "%d / %d" % (mp["self"]["hit"], mp["self"]["total"]), "91 条问法逐条命中自己"],
        ["同义问法", "%d / %d" % (mp["paraphrase"]["hit"], mp["paraphrase"]["total"]), "换说法仍命中正确条目"],
        ["越界提问", "拒答 %d 条 + 拒答样板 %d 条" % (mp["oos"]["refused"], mp["oos"]["soft"]),
         "另有 1 条已知误命中（概念类），与 Web 端一致"],
        ["三种模式", "全部有输出（%s）" % " / ".join("%s %d 字" % (m["mode"], m["len"]) for m in mp["modes"]),
         "史实 / 研学 / 一句话"],
        ["包体积", "约 180 KB", "主包上限 2 MB，余量充足"],
    ], widths=[3.2, 6.4, 7.0], size=9, align_center=[0])
    p(doc, "复跑：`node tools/selftest_mp.js`（结果写入 docs/selftest_mp.json）。", size=9, color=GREY)

    h1(doc, "工程结构", "8")
    quote(doc, "miniprogram/\n"
               "├─ app.json / app.js / app.wxss      # 全局配置与样式\n"
               "├─ project.config.json               # AppID 在这里改（当前 touristappid）\n"
               "├─ data/kb.js                        # 91 条知识库（自动生成）\n"
               "├─ utils/engine.js                   # 与网页版同一份检索引擎\n"
               "├─ pages/index/                      # 对话页：三模式、来源、拒答\n"
               "├─ pages/card/                       # 问答卡：Canvas 绘制、存相册、转发\n"
               "└─ images/wxacode.png                # 小程序码（跑 wxacode.py 后生成）")

    doc.save(os.path.join(OUT, "09_微信小程序上架与小程序码.docx"))
    print("ok 09")


if __name__ == "__main__":
    main()
