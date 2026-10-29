# -*- coding: utf-8 -*-
"""延安全域 50 条问答规格。ref 指向已核验史料条目；无来源的事实一律不进库。"""

WECHAT = "微信公众号「延安革命纪念馆」"

NO_ANSWER = ("这个问题我需要查证，建议咨询延安市文化和旅游局或对应场馆的官方渠道"
             "（延安市文旅局官网、微信公众号「延安革命纪念馆」）。为避免提供不准确的信息，我不做推测。")

SPEC = [
    # ---- A 旧址与场馆（26）
    dict(id="A01", q="宝塔山为什么是延安的象征？", ref="spot_baotashan", kind="fact", scene="参观中", image="宝塔山·仰拍"),
    dict(id="A02", q="宝塔山上的宝塔是什么年代的？", ref="spot_baotashan", kind="fact", scene="参观中", image="宝塔山", tags2=["宝塔山", "塔", "砖塔"]),
    dict(id="A03", q="杨家岭革命旧址有什么可看的？", ref="spot_yangjialing", kind="fact", scene="参观中"),
    dict(id="A04", q="党的七大是什么时候、在哪里开幕的？", ref="spot_yangjialing", kind="fact", scene="研学"),
    dict(id="A05", q="延安文艺座谈会是哪一年开的？", ref="spot_yangjialing", kind="fact", scene="研学"),
    dict(id="A06", q="枣园革命旧址是什么地方？", ref="spot_zaoyuan", kind="fact", scene="参观中",
         extra=[{"name": "延安市人民政府", "doc": "枣园革命旧址",
                 "date": "2025-11-12", "url": "https://yanan.gov.cn/sq/yaly/1523664512878718977.html"}],
         ans="枣园革命旧址位于延安城西北 8 公里处，是园林式的革命纪念地，中共中央书记处曾驻此地，"
             "其间领导整风运动和大生产运动、筹备党的七大；园内窑洞与纺车等实物再现了「自己动手、丰衣足食」的生活。"
             "关于进驻时间有两种官方口径：延安革命纪念地管理局记为 1943 年 10 月—1947 年 3 月，"
             "延安市人民政府页面记为 1944 年—1947 年 3 月。两种都列，不合并、不平均。"),
    dict(id="A07", q="枣园在延安时期承担了什么角色？", ref="spot_zaoyuan", kind="fact", scene="研学",
         extra=[{"name": "延安市人民政府", "doc": "枣园革命旧址",
                 "date": "2025-11-12", "url": "https://yanan.gov.cn/sq/yaly/1523664512878718977.html"}],
         ans="枣园是中共中央书记处驻地。据延安市人民政府页面，1944 年至 1947 年 3 月，中央书记处由杨家岭迁驻此地；"
             "其间领导全党开展整风运动、推动解放区军民的大生产运动，并筹备了中国共产党「七大」。"
             "2016 年 12 月，枣园革命旧址列入全国红色旅游经典景区名录。"),
    dict(id="A08", q="延安革命纪念馆是什么时候建的？", ref="spot_memorial", kind="fact", scene="参观前",
         extra=[{"name": "延安市人民政府", "doc": "延安革命纪念馆",
                 "date": "2024-03-06", "url": "https://yanan.gov.cn/sq/yaly/1523664512497037314.html"}],
         ans="延安革命纪念馆是新中国成立后最早建立的革命纪念馆之一，1950 年 1 月建馆，原馆址在南关交际处；"
             "1954 年迁往杨家岭原中共中央机关旧址，1955 年迁至凤凰山麓并定名「延安革命纪念馆」，"
             "1973 年 6 月迁往延河东岸的杨家岭—王家坪现址。1996 年被中宣部定为全国爱国主义教育示范基地，"
             "2008 年被评为首批国家一级博物馆。"),
    dict(id="A09", q="纪念馆里到底有多少件文物？", ref="spot_memorial", kind="fact", scene="参观中",
         extra=[{"name": "延安市人民政府", "doc": "延安革命纪念馆",
                 "date": "2024-03-06", "url": "https://yanan.gov.cn/sq/yaly/1523664512497037314.html"}],
         ans="馆藏总量存在两种公开口径：陕西日报 2026 年 4 月的报道记为「馆藏文物 3.5 万余件」，另有资料记为"
             "「藏品 11 万余件（组）」，两者统计范围与截止时间可能不同，我们不合并、不平均。"
             "可以确认的展陈数据是：新馆陈列展出面积 1.43 万平方米，展出文物 2500 余件、历史照片 1400 余张，"
             "按历史顺序分列 11 个单元。"),
    dict(id="A10", q="去延安革命纪念馆需要预约吗？", ref=("service", "yanan_memorial"), kind="service", scene="参观前",
         ans="需要预约。2024 年 6 月 4 日起实行实名预约，渠道为微信公众号「延安革命纪念馆」或官网 yagmjng.com。"),
    dict(id="A11", q="延安革命纪念馆门票多少钱？", ref=("service", "yanan_memorial"), kind="service", scene="参观前",
         ans="延安革命纪念馆免费开放，不售门票。馆内是否提供收费讲解或特展，以馆方现场公告为准。"),
    dict(id="A12", q="王家坪革命旧址有什么历史？", ref="spot_wangjiaping", kind="fact", scene="参观中"),
    dict(id="A13", q="凤凰山麓是中共中央到延安后的第一站吗？", ref="spot_fenghuangshan", kind="fact", scene="研学"),
    dict(id="A14", q="鲁迅艺术文学院是一所什么样的学校？", ref="spot_luyi", kind="fact", scene="研学"),
    dict(id="A15", q="六届六中全会在哪里召开的？", ref="spot_luyi", kind="fact", scene="研学"),
    dict(id="A16", q="清凉山为什么被称为「红色新闻山」？", ref="spot_qingliangshan", kind="fact", scene="研学"),
    dict(id="A18", q="南泥湾大生产运动是怎么回事？", ref="spot_nanniwan", kind="fact", scene="参观中"),
    dict(id="A19", q="壶口瀑布值得去吗？", ref="spot_hukou", kind="fact", scene="参观前"),
    dict(id="A20", q="黄河乾坤湾是什么景观？", ref="spot_qiankunwan", kind="fact", scene="参观前"),
    dict(id="A21", q="黄帝陵为什么被称为「天下第一陵」？", ref="spot_huangdiling", kind="fact", scene="参观前"),
    dict(id="A22", q="吴起长征胜利纪念园纪念的是什么？", ref="spot_wuyi_memorial", kind="fact", scene="研学"),
    dict(id="A23", q="瓦窑堡会议是什么会议？", ref="spot_wayaobao", kind="fact", scene="研学"),
    dict(id="A24", q="洛川会议决定了什么？", ref="spot_luochuan_meeting", kind="fact", scene="研学"),
    dict(id="A25", q="刘志丹烈士陵园是做什么的？", ref="spot_zhidan_memorial", kind="fact", scene="研学"),
    dict(id="A26", q="安塞有哪些非遗可以看？", ref="spot_ansai_culture", kind="fact", scene="参观前"),

    # ---- B 延安十三年主线（8）
    dict(id="B01", q="中共中央在延安一共待了多少年？", ref="overview_yanan", kind="fact", scene="参观中"),
    dict(id="B02", q="1947 年中共中央为什么撤离延安？", ref="spot_wangjiaping", kind="fact", scene="研学"),
    dict(id="B03", q="转战陕北一共持续了多长时间？", kind="boundary", scene="研学", ref="spot_wangjiaping",
         ans="知识库只收录了 1947 年 3 月 18 日毛泽东由王家坪撤离延安、开始转战陕北这一节点；转战陕北的完整"
             "起止时间与里程我没有可直接引用的权威来源，不做推算。建议查阅馆方展陈或《中国共产党历史》相关卷册。"),
    dict(id="B04", q="「窑洞对」讲的是什么内容？", kind="boundary", scene="研学", ref="spot_yangjialing",
         ans="可核验的史料只能确认「窑洞对」发生在杨家岭革命旧址。具体对话内容存在多个版本，我手上没有可直接"
             "引用的原文，因此不做复述。建议查阅馆方展陈说明或权威党史出版物。"),
    dict(id="B05", q="「自己动手、丰衣足食」和哪里有关？", ref="spot_zaoyuan", kind="fact", scene="参观中"),
    dict(id="B06", q="中央红军是什么时候到达陕北的？", ref="spot_wuyi_memorial", kind="fact", scene="研学"),
    dict(id="B07", q="中央红军长征的落脚点在哪里？", ref=["spot_wuyi_memorial", "spot_wayaobao"], kind="combo", scene="研学"),
    dict(id="B08", q="《实践论》《矛盾论》是在哪里写的？", ref="spot_fenghuangshan", kind="fact", scene="研学"),

    # ---- C 城市、到达与供给（6）
    dict(id="C01", q="从西安到延安怎么走最快？", ref="transport_rail", kind="fact", scene="参观前"),
    dict(id="C02", q="延安有机场吗？能飞哪些城市？", ref="transport_air", kind="fact", scene="参观前"),
    dict(id="C03", q="延安 2024 年接待了多少游客？", ref="tourism_2024", kind="fact", scene="离馆后"),
    dict(id="C04", q="延安有多少个 A 级景区、住宿条件怎么样？", ref="tourism_supply", kind="fact", scene="参观前"),
    dict(id="C05", q="延安现在的城市情况怎么样？", ref="overview_yanan", kind="fact", scene="离馆后"),
    dict(id="C06", q="延安有哪些 5A 级景区？", ref="tourism_supply", kind="fact", scene="参观前"),

    # ---- D 时代意义与政策（4）
    dict(id="D01", q="国家为什么要支持革命老区发展？", ref="policy_3hao", kind="fact", scene="研学"),
    dict(id="D02", q="2026 年的新政策提到人工智能了吗？", ref="policy_2026_laoqu", kind="fact", scene="研学"),
    dict(id="D03", q="《智慧旅游创新发展行动计划》是什么？", ref="policy_smart_tourism", kind="fact", scene="研学"),
    dict(id="D04", q="全国红色旅游一年有多少人次？", ref="red_tourism_national", kind="fact", scene="研学"),

    # ---- E 边界与拒答样板（6）
    dict(id="E01", q="今天延安的场馆都开放吗？人多不多？", kind="boundary", scene="客服", ref="spot_memorial",
         ans="今天的开放状态和实时客流我无法确认，这类信息每天都在变。建议出发前查看各场馆微信公众号的当日公告"
             "（延安革命纪念馆：微信公众号「延安革命纪念馆」；宝塔山、杨家岭、枣园可查延安革命纪念地管理局发布渠道）。"),
    dict(id="E02", q="明天延安天气怎么样？会影响参观吗？", kind="boundary", scene="客服", ref="spot_memorial",
         ans="我不接入实时天气数据，也不做天气推测。建议查看中央气象台或当地气象部门的预报；壶口、乾坤湾属于"
             "户外点位，雨雪天需多留车程。"),
    dict(id="E03", q="能帮我订门票或者代办预约吗？", kind="boundary", scene="客服", ref="spot_memorial",
         ans="我只做讲解和史料问答，不能代订门票或代办预约。延安革命纪念馆请通过" + WECHAT +
             "或官网 yagmjng.com 自行预约；其他场馆各有独立渠道。"),
    dict(id="E04", q="梁家河的门票和开放时间是多少？", kind="boundary", scene="客服", ref="spot_wayaobao",
         ans="梁家河未列入延安市 A 级景区名录，门票、开放时间与预约渠道没有官方公开文件，我不报价、不推测。"
             "建议以延川县文旅部门或梁家河村当日公告为准。"),
    dict(id="E05", q="纪念馆的馆长是谁？讲解员怎么联系？", kind="boundary", scene="客服", ref="spot_memorial",
         ans=NO_ANSWER),
    dict(id="E06", q="帮我写一段直播带货文案吧。", kind="boundary", scene="客服", ref="spot_memorial",
         ans="我只负责延安红色文旅的讲解，不带货、不写商业文案。想听听某个旧址的故事吗？"),
]
