# -*- coding: utf-8 -*-
"""把点位数据导出为运行时文件 data/sites.json（服务端不再依赖构建脚本）。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "build"))

import kb_sites  # noqa: E402

out = {
    "sites": kb_sites.SITES,
    "stages": {"primary": "小学", "middle": "初中", "high": "高中", "college": "大学"},
    "identities": {"student": "学生", "teacher": "教师", "party": "党员", "public": "群众"},
}
path = os.path.join(ROOT, "data", "sites.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("已写入 %s：%d 个点位" % (path, len(kb_sites.SITES)))
