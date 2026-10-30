# -*- coding: utf-8 -*-
"""二维码自校验（不依赖图像识别）：

1. 生成矩阵 → 读回两份格式位，验证 BCH 合法且两份一致；
2. 去掉掩码、读回数据区 → 反交织 → RS 校验余数为 0；
3. 还原出文本并比对原始 URL。

这三条同时成立，说明码符合同一标准（扫码软件按同样规则读取）。
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import qr_local as Q

LEFT = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]


def bch_ok(v):
    t = v ^ 0x5412
    for i in range(14, 9, -1):
        if (t >> i) & 1:
            t ^= 0x537 << (i - 10)
    return (t & 0x3FF) == 0


def check(text):
    mat, size, scale, border, ver, mask = Q.make(text)
    func = Q._is_function(ver, size)

    # 1) 格式位：两个副本都要能读出同一个合法值
    v_left = sum((mat[r][c] & 1) << i for i, (r, c) in enumerate(LEFT))
    v_right = 0
    for i in range(8):
        v_right |= (mat[8][size - 1 - i] & 1) << i
    for i in range(7):
        v_right |= (mat[size - 1 - i][8] & 1) << (8 + i)
    fmt_good = bch_ok(v_left) and bch_ok(v_right) and v_left == v_right
    got_mask = ((v_left ^ 0x5412) >> 10) & 7

    # 2) 去掩码读回数据区
    bits = []
    col, up = size - 1, True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if up else range(size)
        for r in rows:
            for c in (col, col - 1):
                if not func[r][c]:
                    b = int(mat[r][c]) & 1
                    if Q.MASK_FUNCS[got_mask](r, c):
                        b ^= 1
                    bits.append(b)
        col -= 2
        up = not up
    bits = bits[:(len(bits) // 8) * 8]
    cws = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

    a, b_, ecc, c, d = Q.ECC_H[ver]
    sizes = [a] * b_ + ([c] * d if c else [])
    total = sum(sizes) + ecc * len(sizes)
    if len(cws) < total:
        return False, "码字不足（读出 %d / 需要 %d）" % (len(cws), total), {}

    groups = [[] for _ in sizes]
    pos = 0
    for i in range(max(sizes)):
        for gi, sz in enumerate(sizes):
            if i < sz:
                groups[gi].append(cws[pos])
                pos += 1
    eccs = [[] for _ in sizes]
    for _ in range(ecc):
        for gi in range(len(sizes)):
            eccs[gi].append(cws[pos])
            pos += 1
    rs = Q._rs_tables(ecc)
    rs_ok = all(all(x == 0 for x in rs(groups[gi] + eccs[gi])) for gi in range(len(sizes)))

    data = [x for g in groups for x in g]
    ab = []
    for x in data:
        ab += [(x >> i) & 1 for i in range(7, -1, -1)]
    mode = int("".join(map(str, ab[0:4])), 2)
    cc = 8 if ver <= 9 else 16
    count = int("".join(map(str, ab[4:4 + cc])), 2)
    p = 4 + cc
    raw = [int("".join(map(str, ab[p + 8 * i:p + 8 * i + 8])), 2) for i in range(count)]
    out = bytes(raw).decode("utf-8", "replace")

    info = {"version": ver, "mask": got_mask, "modules": size, "rs": rs_ok,
            "format": fmt_good, "decoded": out}
    ok = fmt_good and rs_ok and mode == 4 and out == text
    return ok, ("格式位=%s 掩码=%d RS=%s 还原=%r" % (fmt_good, got_mask, rs_ok, out)), info


if __name__ == "__main__":
    urls = sys.argv[1:] or ["https://hongji-yanan.onrender.com",
                            "https://zphzphdom.github.io/hongji-yanan/"]
    bad = 0
    for u in urls:
        ok, msg, info = check(u)
        print(("✓ " if ok else "✗ ") + u)
        print("   " + msg)
        bad += 0 if ok else 1
    print("\n结果：", "全部通过" if bad == 0 else "%d 个失败" % bad)
    sys.exit(0 if bad == 0 else 1)
