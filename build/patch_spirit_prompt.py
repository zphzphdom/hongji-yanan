# -*- coding: utf-8 -*-
"""把「融合延安精神」写进系统提示词（安全替换，避免引号转义问题）。"""

import io

P = r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\server.py"
s = io.open(P, encoding="utf-8").read()

old = '    "6. 只输出正文，不要输出来源行（来源由系统附加）。"\n)'
new = (
    '    "6. 只输出正文，不要输出来源行（来源由系统附加）。\\n"\n'
    '    "7. 只要内容与延安时期的人、事、旧址、精神相关，就用一句话把这段内容与「延安精神」四条中的一条自然联系起来"\n'
    '    "（坚定正确的政治方向／解放思想、实事求是／全心全意为人民服务／自力更生、艰苦奋斗）。"\n'
    '    "不要生硬贴标签，不要每次罗列四条；与延安无关的问题（如天气、交通）不必强行关联。"\n'
    ")"
)

assert old in s, "SYSTEM 结尾锚点未找到"
s = s.replace(old, new, 1)
io.open(P, "w", encoding="utf-8").write(s)

import ast
ast.parse(s)
print("已写入系统提示词第 7 条")
