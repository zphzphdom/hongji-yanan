# -*- coding: utf-8 -*-
"""点位学习全流程自测：python tools/selftest_learn.py [base]"""

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788"


def req(path, body=None, timeout=120):
    h = {"Content-Type": "application/json", "X-Visitor": "selftest-runner"}
    body = dict(body or {}) if body is not None else None
    if body is not None:
        body.setdefault("visitor", "selftest-runner")
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=h,
                               method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as x:
            return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    ok_all = True

    # 1) 无需登录
    s, _ = req("/api/console/dashboard")
    print("[免登录后台] %s" % ("OK" if s == 200 else "FAIL %s" % s))
    ok_all &= s == 200

    # 2) 点位列表
    s, j = req("/api/progress", {})
    sites = j.get("sites") or []
    print("[点位] %d 个：%s" % (len(sites), "、".join(x["name"] for x in sites)))

    # 3) 学生每种学段的任务都能下发并提交（选择题全对分支）
    for site in sites:
        for stage in ("primary", "middle", "high", "college"):
            s1, t = req("/api/task", {"site": site["id"], "identity": "student", "stage": stage})
            task = t.get("task") or {}
            if task.get("mode") == "party":
                print("  FAIL %s 走了党员分支" % site["name"])
                ok_all = False
                continue
            q = task.get("question") or {}
            s2, r = req("/api/submit", {"site": site["id"], "identity": "student",
                                        "stage": stage, "choice": [q.get("answer")]})
            good = s2 == 200 and (r.get("result") or {}).get("ok")
            if not good:
                ok_all = False
            print("  %-14s %-4s 提交=%s ok=%s" % (site["name"], stage, s2,
                                                 (r.get("result") or {}).get("ok")))

    # 4) 错误答案应判错并给引导
    s, t = req("/api/task", {"site": sites[0]["id"], "identity": "student", "stage": "middle"})
    q = t["task"]["question"]
    wrong = (q["answer"] + 1) % len(q["options"])
    s, r = req("/api/submit", {"site": sites[0]["id"], "identity": "student",
                               "stage": "middle", "choice": [wrong]})
    res = r.get("result") or {}
    print("[错答] ok=%s 反馈=%s" % (res.get("ok"), (res.get("feedback") or "")[:24]))
    ok_all &= res.get("ok") is False and bool(res.get("feedback"))

    # 5) 文本提交
    s, r = req("/api/submit", {"site": sites[0]["id"], "identity": "student", "stage": "high",
                               "text": "我在展板上看到 1945 年 4 月 23 日七大开幕，地点是中央大礼堂。"})
    res = r.get("result") or {}
    print("[文本提交] ok=%s score=%s" % (res.get("ok"), res.get("score")))
    ok_all &= s == 200 and bool(res.get("feedback"))

    # 6) 党员：讲解 + 判断题
    s, t = req("/api/task", {"site": sites[0]["id"], "identity": "party", "stage": "high"})
    task = t.get("task") or {}
    print("[党员分支] mode=%s 讲稿=%s 题数=%d" % (task.get("mode"), bool(task.get("script")),
                                                len(task.get("questions") or [])))
    ok_all &= task.get("mode") == "party" and bool(task.get("script")) and len(task["questions"]) >= 2
    s, r = req("/api/submit", {"site": sites[0]["id"], "identity": "party",
                               "choice": [x["answer"] for x in task["questions"]]})
    print("[党员提交] ok=%s" % (r.get("result") or {}).get("ok"))
    ok_all &= bool((r.get("result") or {}).get("ok"))

    # 7) 全部完成
    s, p = req("/api/progress", {})
    prog = p.get("progress") or {}
    print("[进度] %d/%d allDone=%s" % (prog.get("done"), prog.get("total"), prog.get("allDone")))
    ok_all &= prog.get("allDone") is True

    # 8) 纪念卡：单点位 + 全线
    s, m1 = req("/api/memorial", {"site": sites[0]["id"]})
    s, m2 = req("/api/memorial", {})
    c1, c2 = m1.get("card") or {}, m2.get("card") or {}
    print("[纪念卡] 单点=%s / 全线=%s" % (c1.get("title"), c2.get("title")))
    ok_all &= c1.get("title") == "点位完成纪念卡" and c2.get("title") == "全线完成纪念卡"

    print("\n结果：", "通过" if ok_all else "未通过")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
