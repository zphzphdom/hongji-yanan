# -*- coding: utf-8 -*-
"""生成 02_知识库_91条带来源问答.xlsx"""
import os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from common import OUT, build_rows, IP_NAME

HDR_FILL = PatternFill("solid", fgColor="8C1F28")
HDR_FONT = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
BODY = Font(name="微软雅黑", size=10)
SMALL = Font(name="微软雅黑", size=9)
THIN = Side(style="thin", color="D9C9C9")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
ALT = PatternFill("solid", fgColor="FBF7F3")

COLS = [
    ("编号", 8), ("问题（用户会怎么问）", 34), ("标准回答（可直接念给游客）", 62),
    ("来源编号", 10), ("来源机构", 16), ("来源文件 / 页面", 34), ("发布日期", 12),
    ("原文链接", 46), ("可信度", 9), ("适合场景", 11), ("类型", 11),
]


def main():
    rows, reg = build_rows()
    wb = Workbook()
    ws = wb.active
    ws.title = "知识库"

    ws.merge_cells("A1:K1")
    c = ws["A1"]
    c.value = "%s · AI 讲解员知识库（%d 条，全部标源｜每条回答都能翻到原文）" % (IP_NAME, len(rows))
    c.font = Font(name="微软雅黑", size=14, bold=True, color="8C1F28")
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30

    for i, (name, width) in enumerate(COLS, 1):
        cell = ws.cell(row=2, column=i, value=name)
        cell.fill, cell.font, cell.border = HDR_FILL, HDR_FONT, BOX
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[2].height = 34

    for r, row in enumerate(rows, start=3):
        vals = [row["id"], row["q"], row["a"], "、".join(row["src_ids"]), row["org"],
                row["doc"], row["date"], row["url"], row["conf"], row["scene"], row["kind"]]
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = BODY
            cell.border = BOX
            cell.alignment = WRAP if i in (2, 3, 6) else Alignment(vertical="top", horizontal="center")
            if r % 2 == 1:
                cell.fill = ALT
        if row["url"]:
            cell = ws.cell(row=r, column=8)
            cell.hyperlink = row["url"]
            cell.font = Font(name="微软雅黑", size=9, color="1155CC", underline="single")

    last = 2 + len(rows)
    ws.freeze_panes = "C3"
    ws.auto_filter.ref = "A2:K%d" % last

    dv = DataValidation(type="list", formula1='"高,中"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("I3:I%d" % last)
    dv2 = DataValidation(type="list", formula1='"参观前,参观中,研学,离馆后,客服"', allow_blank=True)
    ws.add_data_validation(dv2)
    dv2.add("J3:J%d" % last)

    # ---- 说明页
    s = wb.create_sheet("填写说明与导入步骤")
    s.column_dimensions["A"].width = 4
    s.column_dimensions["B"].width = 22
    s.column_dimensions["C"].width = 88

    def line(r, left, right, bold=False, color="000000", size=10):
        a = s.cell(row=r, column=2, value=left)
        b = s.cell(row=r, column=3, value=right)
        a.font = Font(name="微软雅黑", size=size, bold=True, color=color)
        b.font = Font(name="微软雅黑", size=size, bold=bold, color=color)
        a.alignment = Alignment(vertical="top", wrap_text=True)
        b.alignment = Alignment(vertical="top", wrap_text=True)
        return r + 1

    r = 1
    s.cell(row=r, column=2, value="知识库说明").font = Font(name="微软雅黑", size=15, bold=True, color="8C1F28")
    r += 2
    r = line(r, "为什么是 91 条", "91 条带来源的精准问答，检索命中率与可信度都高于 500 条来源模糊的资料。评委随机点开任意一条，都能顺着「原文链接」打开政府网、部委或央媒原文。")
    r = line(r, "字段怎么用", "「标准回答」直接导入智能体作为回答正文；「来源编号」会出现在每条回答末尾，如 [S03]；「原文链接」供人工核查与答辩展示。")
    r = line(r, "重复问法说明", "同一件史实对应不同问法（如「门票多少」「要买票吗」）会指向同一来源，这是刻意的：口语问法越多，检索越容易命中，来源仍然只有一个，不会造成事实分叉。")
    r = line(r, "拒答样板", "「类型 = 拒答样板」的条目本身就是标准答案：知识库没有的、会变的（天气、客流、余票）、涉及具体房间与人名的，一律按这些条目回答，不做推测。")
    r = line(r, "口径冲突", "馆藏量有两种公开口径（3.5 万余件 / 11 万余件（组）），A02 条保留两种说法并说明「不合并、不平均」，这是本知识库处理冲突数据的统一做法。")
    r += 1
    s.cell(row=r, column=2, value="导入步骤（腾讯元器 / 扣子 通用）").font = Font(name="微软雅黑", size=12, bold=True, color="8C1F28")
    r += 1
    steps = [
        ("①", "把本表「问题 + 标准回答」两列复制成两列纯文本，或直接上传整个 .xlsx（元器支持表格型知识库）。"),
        ("②", "知识库命名：延安革命纪念馆-讲解问答-50条-v1。"),
        ("③", "分段方式选「按行 / 一问一答」，不要按字数切分，否则一条回答会被切断。"),
        ("④", "上传后在智能体里点「命中测试」，用第 01 页的 8 个示例问题逐条试，确认都能命中对应条目。"),
        ("⑤", "把 03 号文档里的「系统提示词」整段粘进人设/指令框，拒答规则必须在提示词里再写一遍。"),
    ]
    for k, v in steps:
        r = line(r, k, v)
    r += 1
    s.cell(row=r, column=2, value="维护规则（答辩「后期谁维护」用）").font = Font(name="微软雅黑", size=12, bold=True, color="8C1F28")
    r += 1
    r = line(r, "谁审", "史料由馆方 / 党史部门审核，团队只做结构化与语言转化；每条新增必须附可打开的原文链接，没有链接不进库。")
    r = line(r, "多久审", "每季度一次；遇展陈调整、票价与开放时间变化，由馆方通知后 3 个工作日内更新，并在「发布日期」列留下新日期。")
    r = line(r, "怎么改", "只增不删：被修订的旧条目改为「已废止」并保留，避免历史回答突然失去出处。")

    wb.save(os.path.join(OUT, "02_知识库_91条带来源问答.xlsx"))
    print("ok 02", len(rows), "rows /", len(reg), "sources")


if __name__ == "__main__":
    main()
