#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判定地图截图里「地图区域」到底是加载了瓦片，还是 Leaflet 的默认灰底。

思路：把整图切成 5x4 房格，逐格统计「出现比例最高的精确颜色」与其占比。
- 瓦片已加载：格子内颜色分散、主导色占比低（通常 <60%），唯一色数高。
- 瓦片未加载：Leaflet 默认容器底色 #DDDDDD 会占满格子（占比 >95%）。

用法：python3 _build/png_where.py <png>
"""
from __future__ import annotations

import collections
import sys

sys.path.insert(0, "/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent/_build")
import png_stats as P  # noqa: E402


def main() -> None:
    path = sys.argv[1]
    w, h, ch, ctype, px, plte = P.decode(path)

    def rgb_at(x: int, y: int):
        i = (y * w + x) * ch
        if ctype == 3:
            k = px[i] * 3
            return plte[k], plte[k + 1], plte[k + 2]
        if ctype in (0, 4):
            return px[i], px[i], px[i]
        return px[i], px[i + 1], px[i + 2]

    print("尺寸:", f"{w}x{h}")
    print("---- 5x4 房格（主导精确色 / 占比 / 唯一色数）----")
    cells = []
    for gy in range(4):
        row = []
        for gx in range(5):
            x0, x1 = int(gx * w / 5), int((gx + 1) * w / 5)
            y0, y1 = int(gy * h / 4), int((gy + 1) * h / 4)
            cnt = collections.Counter()
            uniq = set()
            n = 0
            for y in range(y0, y1, 2):
                for x in range(x0, x1, 2):
                    c = rgb_at(x, y)
                    cnt[c] += 1
                    uniq.add(c)
                    n += 1
            dom, dn = cnt.most_common(1)[0]
            pct = 100.0 * dn / n
            row.append((dom, pct, len(uniq)))
            cells.append((dom, pct, len(uniq)))
        print("  行%d: " % gy + " | ".join(
            "#%02X%02X%02X %4.1f%% u%-5d" % (c[0], c[1], c[2], p, u) for c, p, u in row))

    grays = [c for c in cells if 0xDA <= c[0][0] <= 0xE0 and abs(c[0][0] - c[0][1]) <= 2 and abs(c[0][1] - c[0][2]) <= 2 and c[1] > 90]
    rich = [c for c in cells if c[2] > 300]
    print("---- 判定 ----")
    print("  疑似 Leaflet 默认灰底(#DDD 占满)的格子:", len(grays), "/", len(cells))
    print("  颜色丰富(唯一色>300)的格子:", len(rich), "/", len(cells))
    if rich and not grays:
        print("  结论: 地图区域已加载真实瓦片内容（非空白灰底）。")
    elif grays and not rich:
        print("  结论: 地图区域仍为默认灰底，瓦片未渲染 —— 截图不可用。")
    else:
        print("  结论: 混合（部分区域有内容，需人工看图核对）。")


if __name__ == "__main__":
    main()
