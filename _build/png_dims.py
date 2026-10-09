#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印 PNG 的宽高/字节/sha256 前 16 位（无需 PIL）。"""
import hashlib
import os
import struct
import sys

BASE = "/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent"

for rel in sys.argv[1:]:
    p = rel if os.path.isabs(rel) else os.path.join(BASE, rel)
    if not os.path.exists(p):
        print(f"{rel}: MISSING")
        continue
    b = open(p, "rb").read()
    w = h = -1
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", b[16:24])
    print(f"{os.path.basename(p)}: {len(b)} B / {w}x{h} / sha256:{hashlib.sha256(b).hexdigest()[:16]}")
