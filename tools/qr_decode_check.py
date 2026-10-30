# -*- coding: utf-8 -*-
"""二维码正确性校验。

判据三条，全部要过：
  1. 格式信息是合法 BCH 码字，且解出的纠错等级/掩码与写入一致；
  2. 数据区 RS 校验余数为 0（说明数据 + 纠错按标准编码）；
  3. 解开后还原出的文本与原始 URL 相同。
"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, r"C:\Users\zph\Documents\deepseek-harness\default-workspace\hongji-yanan\tools")
import qr_local as Q

# 标准中格式信息在左上角的读取顺序（索引 i = 第 i 位，i=0 为最低位）
LEFT_COORDS = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
               (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]


def bch_valid(value):
    """value 为 15 位带掩码串：异或掩码后应对生成多项式取模为 0。"""
    t = value ^ 0x5412
    for i in range(14, 9, -1):
        if (t >> i) & 1:
            t ^= 0x537 << (i - 10)
    return (t & 0x3FF) == 0


def load_modules(path):
    im = np.array(Image.open(path).convert("L"))
    dark = im < 128
    h, w = dark.shape
    # 先用"全白边"反推单个模块的像素数：找第一行/第一列出现黑色模块的位置
    rows = np.where(dark.any(axis=1))[0]
    cols = np.where(dark.any(axis=0))[0]
    y0, y1 = rows[0], rows[-1] + 1
    x0, x1 = cols[0], cols[-1] + 1
    # 二维码实际内容区尺寸 = 模块数 × scale；从可能的最小 scale 起试着整除
    size = scale = None
    for ver in range(1, 11):
        s = 17 + 4 * ver
        for cand in range(2, 41):
            if s * cand == (x1 - x0) and s * cand == (y1 - y0):
                size, scale = s, cand
                break
        if size:
            break
    if not size:
        # 回退：按画布总宽除以模块数加白边
        for ver in range(1, 11):
            s = 17 + 4 * ver
            if w % (s + 8) == 0:
                size = s
                scale = w // (s + 8)
                y0 = x0 = scale * 4
                break
    if not size:
        raise SystemExit("无法判定模块尺寸（画布 %dx%d，内容区 %dx%d）"
                         % (w, h, x1 - x0, y1 - y0))
    m = np.zeros((size, size), dtype=np.uint8)
    for r in range(size):
        for c in range(size):
            blk = dark[y0 + r * scale:y0 + (r + 1) * scale, x0 + c * scale:x0 + (c + 1) * scale]
            m[r][c] = 1 if blk.mean() > 0.5 else 0
    return m, size, scale


def read_format(m):
    v = 0
    for i, (r, c) in enumerate(LEFT_COORDS):
        v |= (int(m[r][c]) & 1) << i
    data = (v ^ 0x5412) >> 10
    return v, (data >> 3) & 3, data & 7


def main(path, expect):
    m, size, scale = load_modules(path)
    ver = (size - 17) // 4
    v, ec, mask = read_format(m)
    print("模块 %dx%d 版本 %d 缩放 %d" % (size, size, ver, scale))
    print("格式串 %s  BCH合法=%s  纠错等级=%d  掩码=%d" % (format(v, "015b"), bch_valid(v), ec, mask))

    func = Q._is_function(ver, size)
    bits = []
    col, upward = size - 1, True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for c in (col, col - 1):
                if not func[r][c]:
                    b = int(m[r][c]) & 1
                    if Q.MASK_FUNCS[mask](r, c):
                        b ^= 1
                    bits.append(b)
        col -= 2
        upward = not upward
    bits = bits[:(len(bits) // 8) * 8]
    cws = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

    a, b_, ecc, c, d = Q.ECC_H[ver]
    sizes = [a] * b_ + ([c] * d if c else [])
    total = sum(sizes) + ecc * len(sizes)
    print("码字总数 %d（读出 %d）" % (total, len(cws)))
    if len(cws) < total:
        print("数据不足，判失败")
        return 1

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
    ok_rs = all(all(x == 0 for x in rs(groups[gi] + eccs[gi])) for gi in range(len(sizes)))
    print("RS 校验:", "通过" if ok_rs else "失败")

    data = [x for g in groups for x in g]
    abits = []
    for x in data:
        abits += [(x >> i) & 1 for i in range(7, -1, -1)]
    mode = int("".join(map(str, abits[0:4])), 2)
    cc = 8 if ver <= 9 else 16
    count = int("".join(map(str, abits[4:4 + cc])), 2)
    p = 4 + cc
    raw = [int("".join(map(str, abits[p + 8 * i:p + 8 * i + 8])), 2) for i in range(count)]
    text = bytes(raw).decode("utf-8", "replace")
    print("解出:", repr(text))

    ok = bch_valid(v) and ok_rs and mode == 4 and text == expect
    print("结果:", "通过" if ok else "失败")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
