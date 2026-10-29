# -*- coding: utf-8 -*-
"""扩容：从 data/spots.json 生成 18 个点位的服务问答，再补 6 条未被引用的史料。

原则不变：没有来源的条目一律不生成。服务类事实（门票/开放时间/预约/电话）统一挂
《延安市 A 级旅游景区基本信息表》（延安市文旅局，2026-10-26）。
"""
from common import KB, SPOTS


def _clean(s):
    return (s or "").strip()


def spot_rows():
    rows = []
    for sid, s in SPOTS.items():
        name = s["name"]
        kb_id = s.get("kb_id")
        ticket = _clean(s.get("ticket"))
        hours = _clean(s.get("open_time"))
        booking = _clean(s.get("booking"))
        phone = _clean(s.get("phone"))
        level = _clean(s.get("level"))

        if ticket or hours:
            parts = []
            if ticket:
                parts.append("门票：%s" % ticket)
            if hours:
                parts.append("开放时间：%s" % hours)
            rows.append(dict(
                id="S%02d" % (len(rows) + 1),
                q="%s需要门票吗？几点开放？" % name,
                ref=("service", sid), kind="service", scene="参观前", conf="高",
                ans="%s。%s。以上为公开信息，出行前请以官方当日公告为准。" % (name, "；".join(parts)),
            ))

        ways = []
        if booking:
            ways.append(booking)
        if phone:
            ways.append("咨询电话 %s" % phone)
        if ways:
            rows.append(dict(
                id="S%02d" % (len(rows) + 1),
                q="%s怎么预约？有咨询电话吗？" % name,
                ref=("service", sid), kind="service", scene="客服", conf="高",
                ans="%s。预约与咨询方式：%s。节假日与团队参观建议提前确认。" % (name, "；".join(ways)),
            ))

        # 等级类问题统一由 tourism_supply 那条回答，不按点位重复生成，避免和史实条目抢命中
    return rows


EXTRA = [
    dict(id="X01", q="延安有哪些地理标志农产品？", ref="gi_overview", kind="fact", scene="离馆后"),
    dict(id="X02", q="延安农民的收入水平怎么样？", ref="income_2024", kind="fact", scene="研学"),
    dict(id="X03", q="安塞南沟村是怎么靠直播卖苹果的？", ref="case_nangou", kind="fact", scene="研学"),
    dict(id="X04", q="老区的农产品有哪些上行渠道？", ref="channel_832", kind="fact", scene="研学"),
    dict(id="X05", q="国家支持革命老区特色产业的具体方向是什么？", ref="policy_industry", kind="fact", scene="研学"),
    dict(id="X06", q="中共中央西北局旧址是什么地方？", ref="spot_xibeiju", kind="fact", scene="参观中"),
]


def extra_spec():
    return spot_rows() + EXTRA
