#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Edge 无头模式给本地地图截图（带超时保护，避免 Edge 卡死拖住整条流水线）。

用法：python3 _build/shot_map.py [hash] [输出png] [profile名]
默认：hash=#amap，输出 Zhouruoying_C4D_output_screenshots/02_地图渲染结果.png
"""
from __future__ import annotations

import os
import subprocess
import sys

EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
BASE = "/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent"
MAP = BASE + "/Zhouruoying_C4D_map.html"


def main() -> int:
    hash_part = sys.argv[1] if len(sys.argv) > 1 else "#amap"
    out = sys.argv[2] if len(sys.argv) > 2 else BASE + "/Zhouruoying_C4D_output_screenshots/02_地图渲染结果.png"
    prof = sys.argv[3] if len(sys.argv) > 3 else "edgeprof_shot"
    if os.path.exists(out):
        os.remove(out)
    cmd = [
        EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        "--user-data-dir=" + BASE + "/_build/" + prof,
        "--window-size=1500,1000", "--virtual-time-budget=20000",
        "--screenshot=" + out, "file://" + MAP + hash_part,
    ]
    print("EDGE_CMD =", " ".join(cmd[:6]), "...")
    try:
        rc = subprocess.run(cmd, timeout=90, capture_output=True).returncode
        print("SHOT_RC =", rc)
    except subprocess.TimeoutExpired:
        print("SHOT_RC = TIMEOUT(90s)")
    ok = os.path.exists(out) and os.path.getsize(out) > 1000
    size = os.path.getsize(out) if os.path.exists(out) else -1
    print("PNG =", out)
    print("PNG_EXISTS =", os.path.exists(out), "bytes =", size, "ok =", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
