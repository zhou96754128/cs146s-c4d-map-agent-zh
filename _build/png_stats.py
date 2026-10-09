#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯标准库解码 PNG 并给出像素级取证：不依赖 PIL。

用途：证明「地图截图里真的有瓦片（颜色分布丰富）且真的画出了分类标记
（命中 CATEGORY_COLORS 调色板）」，而不是一张空白页。

用法：python3 _build/png_stats.py <png> [<png2> ...]
"""
from __future__ import annotations

import struct
import sys
import zlib

# 与 scripts/render_map.py 的 CATEGORY_COLORS 一致（分类 -> 颜色）
PALETTE = {
    "校园": (0x25, 0x63, 0xEB),
    "交通枢纽": (0xDC, 0x26, 0x26),
    "博物馆": (0x7C, 0x3A, 0xED),
    "人文景点": (0xD9, 0x77, 0x06),
    "遗址公园": (0x0D, 0x94, 0x88),
    "城镇": (0x65, 0xA3, 0x0D),
    "商业地标": (0xDB, 0x27, 0x77),
    "公园": (0x16, 0xA3, 0x4A),
    "展馆": (0x08, 0x91, 0xB2),
}
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode(path: str):
    raw = open(path, "rb").read()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "not a png"
    pos, idat, plte = 8, [], None
    w = h = depth = ctype = interlace = None
    while pos < len(raw):
        (ln,) = struct.unpack(">I", raw[pos:pos + 4])
        ctag = raw[pos + 4:pos + 8]
        body = raw[pos + 8:pos + 8 + ln]
        if ctag == b"IHDR":
            w, h, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", body)
        elif ctag == b"IDAT":
            idat.append(body)
        elif ctag == b"PLTE":
            plte = body
        elif ctag == b"IEND":
            break
        pos += 12 + ln
    assert depth == 8, f"only 8-bit supported, got {depth}"
    assert interlace == 0, "interlaced png not supported"
    ch = CHANNELS[ctype]
    data = zlib.decompress(b"".join(idat))
    stride = w * ch
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _y in range(h):
        ft = data[p]
        p += 1
        line = bytearray(data[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                up = prev[i]
                ul = prev[i - ch] if i >= ch else 0
                line[i] = (line[i] + _paeth(left, up, ul)) & 0xFF
        out += line
        prev = line
    return w, h, ch, ctype, bytes(out), plte


def stats(path: str) -> None:
    w, h, ch, ctype, px, plte = decode(path)
    colors = set()
    near_white = 0
    total = w * h
    hits = {k: 0 for k in PALETTE}
    for i in range(0, len(px), ch):
        if ctype == 3:
            idx = px[i]
            r, g, b = plte[idx * 3], plte[idx * 3 + 1], plte[idx * 3 + 2]
        elif ctype in (0, 4):
            r = g = b = px[i]
        else:
            r, g, b = px[i], px[i + 1], px[i + 2]
        colors.add((r >> 2, g >> 2, b >> 2))  # 量化到 6bit 抗噪
        if r > 245 and g > 245 and b > 245:
            near_white += 1
        for name, (cr, cg, cb) in PALETTE.items():
            if abs(r - cr) <= 24 and abs(g - cg) <= 24 and abs(b - cb) <= 24:
                hits[name] += 1
    hit_total = sum(hits.values())
    print("=" * 64)
    print("文件:", path)
    print("  尺寸:", f"{w}x{h}", "色彩类型:", ctype, "通道:", ch)
    print("  唯一颜色数(6bit 量化):", len(colors), "/ 上限", min(total, 262144))
    print("  近白像素占比: %.1f%%" % (100.0 * near_white / total))
    print("  命中分类调色板的像素:", hit_total)
    for name, n in hits.items():
        if n:
            print("    -", name, n)
    verdict = []
    verdict.append("瓦片/底图已渲染" if len(colors) > 3000 else "颜色极单调(疑空白底图)")
    verdict.append("标记已绘制" if hit_total > 200 else "未见分类标记")
    print("  判定:", " / ".join(verdict))


if __name__ == "__main__":
    for a in sys.argv[1:]:
        stats(a)
