# -*- coding: utf-8 -*-
"""生成 05_测试记录表_20人.xlsx"""
import os
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from common import OUT

RED = "8C1F28"
HDR = PatternFill("solid", fgColor=RED)
HF = Font(name="微软雅黑", size=9.5, bold=True, color="FFFFFF")
BODY = Font(name="微软雅黑", size=9.5)
THIN = Side(style="thin", color="D9C9C9")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
TOP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

COLS = [
    ("编号", 7), ("日期", 11), ("测试对象", 11), ("年龄段", 9), ("接触方式", 11),
    ("问题 1", 20), ("问题 2", 20), ("问题 3", 20),
    ("准确性\n1—5 分", 9), ("是否编造", 9), ("拒答是否得当", 11),
    ("问了几轮", 8), ("是否愿意分享", 11), ("最大的问题", 26), ("备注", 18),
]

ROWS = 20


def main():
    wb = Workbook()
    ws = wb.active
    ws.title = "测试记录"

    ws.merge_cells("A1:O1")
    c = ws["A1"]
    c.value = "红迹·延安 · 20 人真实测试记录（每人 2—3 问，扫码体验）"
    c.font = Font(name="微软雅黑", size=14, bold=True, color=RED)
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 28

    for i, (name, w) in enumerate(COLS, 1):
        cell = ws.cell(row=2, column=i, value=name)
        cell.fill, cell.font, cell.border, cell.alignment = HDR, HF, BOX, CENTER
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[2].height = 36

    for r in range(3, 3 + ROWS):
        ws.cell(row=r, column=1, value="T%02d" % (r - 2)).font = BODY
        for i in range(1, len(COLS) + 1):
            cell = ws.cell(row=r, column=i)
            cell.border = BOX
            cell.font = BODY
            cell.alignment = TOP if i in (6, 7, 8, 14, 15) else CENTER
        ws.row_dimensions[r].height = 30

    last = 2 + ROWS
    ws.freeze_panes = "F3"
    dv = [
        ('"同学,游客,研学学生,亲友"', "C", "测试对象"),
        ('"18 岁以下,18—25,26—40,41—60,60 岁以上"', "D", "年龄段"),
        ('"我递手机,看海报扫码,线上链接"', "E", "接触方式"),
        ('"1,2,3,4,5"', "I", "准确性"),
        ('"有,无"', "J", "是否编造"),
        ('"是,否"', "K", "拒答是否得当"),
        ('"1,2,3,4,5"', "L", "问了几轮"),
        ('"愿意,看情况,不愿意"', "M", "是否愿意分享"),
    ]
    for formula, col, _ in dv:
        v = DataValidation(type="list", formula1=formula, allow_blank=True)
        ws.add_data_validation(v)
        v.add("%s3:%s%d" % (col, col, last))

    # ---------------- 汇总
    s = wb.create_sheet("自动汇总")
    s.column_dimensions["A"].width = 4
    s.column_dimensions["B"].width = 26
    s.column_dimensions["C"].width = 16
    s.column_dimensions["D"].width = 52
    s["B1"] = "自动汇总（改上面 20 行，这里跟着变）"
    s["B1"].font = Font(name="微软雅黑", size=14, bold=True, color=RED)

    metrics = [
        ("有效样本数", "=COUNTA('测试记录'!A3:A%d)" % last, "填写了的测试编号个数"),
        ("平均准确性（1—5）", "=IFERROR(AVERAGE('测试记录'!I3:I%d),\"\")" % last, "低于 4.0 必须先改知识库，不要改话术"),
        ("出现编造的条数", "=COUNTIF('测试记录'!J3:J%d,\"有\")" % last, "答辩口径：这个数必须是 0"),
        ("编造率", "=IFERROR(COUNTIF('测试记录'!J3:J%d,\"有\")/COUNTA('测试记录'!J3:J%d),\"\")" % (last, last), "只有 0 才能说“没有编造”"),
        ("拒答得当条数", "=COUNTIF('测试记录'!K3:K%d,\"是\")" % last, "该拒的拒了、且话说得清楚"),
        ("平均提问轮次", "=IFERROR(AVERAGE('测试记录'!L3:L%d),\"\")" % last, "低于 2 轮说明没问起来，卡片入口要前置"),
        ("愿意分享占比", "=IFERROR(COUNTIF('测试记录'!M3:M%d,\"愿意\")/COUNTA('测试记录'!M3:M%d),\"\")" % (last, last), "低于 40% 先改摘要写法，不要先改设计"),
        ("扫码进入占比", "=IFERROR(COUNTIF('测试记录'!E3:E%d,\"看海报扫码\")/COUNTA('测试记录'!E3:E%d),\"\")" % (last, last), "检验二维码在真实场景是否被扫"),
    ]
    r = 3
    for name, formula, note in metrics:
        s.cell(row=r, column=2, value=name).font = Font(name="微软雅黑", size=10, bold=True)
        cell = s.cell(row=r, column=3, value=formula)
        cell.font = Font(name="微软雅黑", size=11, bold=True, color=RED)
        cell.alignment = Alignment(horizontal="center")
        cell.number_format = "0.0%" if "率" in name or "占比" in name else ("0.00" if "平均" in name else "0")
        s.cell(row=r, column=4, value=note).font = Font(name="微软雅黑", size=9, color="595959")
        r += 1

    r += 1
    s.cell(row=r, column=2, value="按对象拆开的准确率").font = Font(name="微软雅黑", size=11, bold=True, color=RED)
    r += 1
    for who in ["同学", "游客", "研学学生", "亲友"]:
        s.cell(row=r, column=2, value=who).font = Font(name="微软雅黑", size=10)
        cell = s.cell(row=r, column=3, value="=IFERROR(AVERAGEIF('测试记录'!C3:C%d,\"%s\",'测试记录'!I3:I%d),\"—\")" % (last, who, last))
        cell.alignment = Alignment(horizontal="center")
        cell.font = Font(name="微软雅黑", size=11, bold=True, color=RED)
        cell.number_format = "0.00"
        r += 1

    r += 1
    s.cell(row=r, column=2, value="结论（测完手写 3 行）").font = Font(name="微软雅黑", size=11, bold=True, color=RED)
    for i, label in enumerate(["① 最常问的 3 个问题（补进知识库）",
                               "② 改了什么（一句话）",
                               "③ 还有哪个问题答不住（写进局限）"]):
        r += 1
        s.cell(row=r, column=2, value=label).font = Font(name="微软雅黑", size=9.5)
        s.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
        s.cell(row=r, column=3).fill = PatternFill("solid", fgColor="FBF7F3")
        s.cell(row=r, column=3).border = BOX

    # ---------------- 访谈提纲
    g = wb.create_sheet("访谈提纲")
    g.column_dimensions["A"].width = 4
    g.column_dimensions["B"].width = 30
    g.column_dimensions["C"].width = 66
    g["B1"] = "访谈提纲（照着念，不要临场发挥）"
    g["B1"].font = Font(name="微软雅黑", size=14, bold=True, color=RED)
    qs = [
        ("开场（必说）", "这不是考试，也没有标准答案。你随便问，觉得哪里不对直接说，我在改。"),
        ("Q1 第一印象", "打开这个页面，你知道它是干什么的吗？"),
        ("Q2 真实性", "你信它说的吗？为什么信 / 为什么不信？"),
        ("Q3 来源", "你会点开那个来源看原文吗？点开之后呢？"),
        ("Q4 分享", "这张问答卡你会发朋友圈吗？会 / 不会 / 看情况，为什么？"),
        ("Q5 改动", "如果要发，你会改哪一句？（记录他具体改的那个词）"),
        ("Q6 场景", "下次来延安，你会在什么时候打开它？进馆前、在展柜前，还是回去以后？"),
        ("收尾（必说）", "如果它答不上来，你希望它怎么回答？"),
    ]
    r = 3
    for k, v in qs:
        g.cell(row=r, column=2, value=k).font = Font(name="微软雅黑", size=10, bold=True)
        c2 = g.cell(row=r, column=3, value=v)
        c2.font = Font(name="微软雅黑", size=10)
        c2.alignment = Alignment(wrap_text=True, vertical="top")
        g.row_dimensions[r].height = 30
        r += 1

    wb.save(os.path.join(OUT, "05_测试记录表_20人.xlsx"))
    print("ok 05")


if __name__ == "__main__":
    main()
