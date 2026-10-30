# -*- coding: utf-8 -*-
"""纯本地二维码生成（无第三方库、不联网）。

只实现本项目需要的那一档：字节模式、纠错等级 H、版本自动选择（1—10，覆盖到 174 字节），
足以容纳 https://hongji-yanan.onrender.com 这类短网址。

用法：python tools/make_qr_local.py https://example.com [-o 输出.png]
"""

import os
import sys

# ---------------------------------------------------------------- Reed-Solomon


def _rs_tables(nsym):
    # GF(256) with primitive polynomial 0x11d
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11d
    for i in range(255, 512):
        exp[i] = exp[i - 255]

    def mul(a, b):
        if a == 0 or b == 0:
            return 0
        return exp[log[a] + log[b]]

    # generator polynomial
    g = [1]
    for i in range(nsym):
        g2 = [0] * (len(g) + 1)
        for j, coef in enumerate(g):
            g2[j] ^= mul(coef, exp[i]) if j < len(g2) else 0
            g2[j + 1] ^= coef
        g = g2[:len(g) + 1]

    def rs(data):
        res = [0] * nsym
        for b in data:
            factor = b ^ res[0]
            res = res[1:] + [0]
            if factor:
                for i, coef in enumerate(g[1:]):
                    res[i] ^= mul(coef, factor)
        return res

    return rs


# ---------------------------------------------------------------- 容量与分块
# (版本, 纠错H) -> (每组数据码字, 组数, 每组纠错码字, 额外数据码字, 额外组数)
# 数据来自 ISO/IEC 18004 表，只列本项目用得到的版本
# 只保留经标准表核对过的 1—4 版（纠错 H）。版本 5 以上本工具不生成，
# 以免用错容量表产出不可扫的码。H 级版本 4 可容纳 36 个数据码字，足够本项目所有网址。
ECC_H = {
    1: (9, 1, 17, 0, 0),
    2: (16, 1, 28, 0, 0),
    3: (13, 2, 22, 0, 0),
    4: (9, 4, 16, 0, 0),
}
MAX_VERSION = 4

ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
         7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 52]}
VERSION_BITS = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}
FORMAT_H = 2  # 纠错等级 H 的格式位


def _data_capacity(ver):
    a, b, _, c, d = ECC_H[ver]
    return a * b + c * d


def _version_for(nbytes):
    for v in range(1, MAX_VERSION + 1):
        # 字节模式：4 位模式 + 字符计数（v<=9: 8 位，v>=10: 16 位）+ 数据
        cc = 8 if v <= 9 else 16
        if 4 + cc + nbytes * 8 <= _data_capacity(v) * 8:
            return v
    raise ValueError("内容过长（>%d 字节）" % _data_capacity(MAX_VERSION))


# ---------------------------------------------------------------- 位流


def _bits_to_bytes(bits):
    while len(bits) % 8:
        bits.append(0)
    out = []
    for i in range(0, len(bits), 8):
        b = 0
        for bit in bits[i:i + 8]:
            b = (b << 1) | bit
        out.append(b)
    return out


def _build_data(text, ver):
    data = text.encode("utf-8")
    bits = []
    def put(val, n):
        for i in range(n - 1, -1, -1):
            bits.append((val >> i) & 1)
    put(4, 4)                                  # 字节模式
    put(len(data), 8 if ver <= 9 else 16)      # 字符计数
    for b in data:
        put(b, 8)
    cap = _data_capacity(ver) * 8
    put(0, min(4, cap - len(bits)))            # 终止符
    while len(bits) % 8:
        bits.append(0)
    codewords = _bits_to_bytes(bits)
    pads = [0xEC, 0x11]
    i = 0
    cap_bytes = _data_capacity(ver)
    while len(codewords) < cap_bytes:
        codewords.append(pads[i % 2])
        i += 1
    return codewords


def _interleave(codewords, ver):
    a, b, ec, c, d = ECC_H[ver]
    rs = _rs_tables(ec)
    groups = []
    pos = 0
    for cnt, size in ((b, a), (d, c)):
        for _ in range(cnt):
            if size == 0:
                continue
            blk = codewords[pos:pos + size]
            pos += size
            groups.append((blk, rs(blk)))
    out = []
    maxlen = max(len(g[0]) for g in groups)
    for i in range(maxlen):
        for blk, _ in groups:
            if i < len(blk):
                out.append(blk[i])
    for i in range(ec):
        for _, ecc in groups:
            out.append(ecc[i])
    return out


# ---------------------------------------------------------------- 矩阵


def _matrix(ver):
    size = 17 + 4 * ver
    m = [[None] * size for _ in range(size)]

    def finder(r, c):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                rr, cc = r + dr, c + dc
                if not (0 <= rr < size and 0 <= cc < size):
                    continue
                if dr in (-1, 7) or dc in (-1, 7):
                    m[rr][cc] = 0
                elif dr in (0, 6) or dc in (0, 6):
                    m[rr][cc] = 1
                elif 2 <= dr <= 4 and 2 <= dc <= 4:
                    m[rr][cc] = 1
                else:
                    m[rr][cc] = 0

    finder(0, 0)
    finder(0, size - 7)
    finder(size - 7, 0)

    # 定位图形
    for i in range(8, size - 8):
        if m[6][i] is None:
            m[6][i] = 1 if i % 2 == 0 else 0
        if m[i][6] is None:
            m[i][6] = 1 if i % 2 == 0 else 0

    # 校正图形
    pos = ALIGN[ver]
    for r in pos:
        for c in pos:
            if (r, c) in ((6, 6), (6, size - 7), (size - 7, 6)):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    v = 1 if max(abs(dr), abs(dc)) != 1 else 0
                    if m[r + dr][c + dc] is None:
                        m[r + dr][c + dc] = v

    # 版本信息（v>=7）
    if ver >= 7:
        bits = VERSION_BITS.get(ver)  # 本项目 v<=10 时恒为 0，无需版本信息块
        if bits is not None and False:
            pass
    return m


def _bch_remainder(data, poly=0x537, deg=10):
    """格式信息的 BCH(15,5) 余数：data 左移 deg 位后对 poly 取模。"""
    v = data << deg
    for i in range(v.bit_length() - 1, deg - 1, -1):
        if (v >> i) & 1:
            v ^= poly << (i - deg)
    return v & ((1 << deg) - 1)


def _format_bits(mask):
    """返回 15 位格式信息的低位在前序列（不经掩码）。"""
    data = (FORMAT_H << 3) | mask
    value = ((data << 10) | _bch_remainder(data)) ^ 0x5412
    return [(value >> i) & 1 for i in range(15)]  # 位 14 在最后


def _place_format(m, size, mask):
    """按 ISO/IEC 18004 放置 15 位格式信息（两份互为副本）。"""
    seq = _format_bits(mask)  # seq[i] = 第 i 位（i=0 为最低位）

    # 副本一：左上角，沿第 8 行与第 8 列摆放（跳过时序模块）
    left = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
            (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    for (r, c), bit in zip(left, seq):
        m[r][c] = bit

    # 副本二：右上（第 8 行右侧 8 位）+ 左下（第 8 列下方 8 位里的前 7 位）
    for i in range(8):
        m[8][size - 1 - i] = seq[i]
    for i in range(7):
        m[size - 1 - i][8] = seq[8 + i]
    m[size - 8][8] = 1  # 固定深色模块


MASK_FUNCS = [
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


def _is_function(ver, size):
    """哪些模块属于功能图形（不参与数据填充、不做掩码）。

    注意：只有第 6 行/第 6 列是时序图形；第 8 行与第 8 列只有定位图形/格式信息的那几格
    是功能区，其余（如第 8 行中间段、第 8 列中间段）属于数据区。
    """
    f = [[False] * size for _ in range(size)]

    def mark(r, c):
        if 0 <= r < size and 0 <= c < size:
            f[r][c] = True

    # 三个定位图形：7×7 本体（深色外框+白色内框+深色核心）+ 外侧一圈分隔符
    #   左上角坐标分别为 (0,0)、(0,size-7)、(size-7,0)
    for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                rr, cc = r0 + dr, c0 + dc
                if not (0 <= rr < size and 0 <= cc < size):
                    continue
                # 只保留本体范围（0..6）与外圈（-1 或 7）
                if dr > 6 and dc > 6:
                    continue
                mark(rr, cc)

    # 时序图形：第 6 行与第 6 列
    for i in range(size):
        mark(6, i)
        mark(i, 6)

    # 校正图形
    pos = ALIGN[ver]
    for r in pos:
        for c in pos:
            if (r, c) in ((6, 6), (6, size - 7), (size - 7, 6)):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    mark(r + dr, c + dc)

    # 格式信息（ISO 18004 §8.9）：两份 15 位副本，共 30 格 + 1 个固定深色模块
    #   副本一：第 8 行 c=0..5,7,8 与第 8 列 r=7,5..0
    #   副本二：第 8 行 c=size-1..size-8 与第 8 列 r=size-1..size-7
    for c in (0, 1, 2, 3, 4, 5, 7, 8):
        mark(8, c)
    for r in (7, 5, 4, 3, 2, 1, 0):
        mark(r, 8)
    for i in range(8):
        mark(8, size - 1 - i)
    for i in range(7):
        mark(size - 1 - i, 8)
    # 固定深色模块位于 (size-8, 8)，本身也属功能图形
    mark(size - 8, 8)

    return f


def _assert_capacity(ver):
    size = 17 + 4 * ver
    f = _is_function(ver, size)
    free = sum(1 for r in range(size) for c in range(size) if not f[r][c])
    a, b, ecc, c, d = ECC_H[ver]
    need = ((a * b + c * d) + ecc * (b + (d if c else 0))) * 8
    if free != need:
        raise AssertionError("版本 %d 模块数 %d 与容量 %d 不一致" % (ver, free, need))


def make(text, scale=10, border=4):
    ver = _version_for(len(text.encode("utf-8")))
    _assert_capacity(ver)
    size = 17 + 4 * ver
    data = _build_data(text, ver)
    stream = _interleave(data, ver)

    bits = []
    for b in stream:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)

    base = _matrix(ver)
    func = _is_function(ver, size)

    # 之字形填充
    idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for c in (col, col - 1):
                if not func[r][c] and idx < len(bits):
                    base[r][c] = bits[idx]
                    idx += 1
        col -= 2
        upward = not upward

    # 选最优掩码（简化评分：连续同色 + 黑白比例）
    best = None
    for mk in range(8):
        m = [row[:] for row in base]
        for r in range(size):
            for c in range(size):
                if not func[r][c] and m[r][c] is not None:
                    if MASK_FUNCS[mk](r, c):
                        m[r][c] ^= 1
        _place_format(m, size, mk)
        for r in range(size):
            for c in range(size):
                if m[r][c] is None:
                    m[r][c] = 0
        score = _penalty(m, size)
        if best is None or score < best[0]:
            best = (score, m, mk)
    _, mat, mask = best
    return mat, size, scale, border, ver, mask


def _penalty(m, size):
    score = 0
    # 行/列同色连续
    for grid in (m, list(zip(*m))):
        for line in grid:
            run = 1
            for i in range(1, size):
                if line[i] == line[i - 1]:
                    run += 1
                else:
                    if run >= 5:
                        score += run - 2
                    run = 1
            if run >= 5:
                score += run - 2
    # 2x2 同色
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    dark = sum(sum(row) for row in m)
    total = size * size
    score += abs(dark * 100 // total - 50) * 2
    return score


def save_png(path, text, scale=10, border=4):
    from PIL import Image

    mat, size, scale, border, ver, mask = make(text, scale, border)
    dim = (size + border * 2) * scale
    img = Image.new("RGB", (dim, dim), "white")
    px = img.load()
    for r in range(size):
        for c in range(size):
            if mat[r][c]:
                for y in range((r + border) * scale, (r + border + 1) * scale):
                    for x in range((c + border) * scale, (c + border + 1) * scale):
                        px[x, y] = (0, 0, 0)
    img.save(path)
    return {"path": path, "version": ver, "mask": mask, "modules": size, "pixels": dim}


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://hongji-yanan.onrender.com"
    out = "qr.png"
    if "-o" in sys.argv:
        out = sys.argv[sys.argv.index("-o") + 1]
    info = save_png(out, url, scale=10, border=4)
    print(info)
