#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Edge 无头模式给 01_环境与模型信息.html 截图（带超时保护，避免 Edge 卡死）。

用法：python3 _build/shot_env.py [输出png] [profile名]
默认输出 Zhouruoying_C4D_output_screenshots/01_环境与模型信息.png

注意：页面文件名含中文，必须做 URL 百分号编码，否则 Edge 打不开。
不要用 make_evidence.py 重生成该 HTML——那是净化前的版本，会带回本机绝对路径。
"""
from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import quote

EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
BASE = "/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent"
PAGE = BASE + "/Zhouruoying_C4D_output_screenshots/01_环境与模型信息.html"


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else BASE + "/Zhouruoying_C4D_output_screenshots/01_环境与模型信息.png"
    prof = sys.argv[2] if len(sys.argv) > 2 else "edgeprof_env"
    if os.path.exists(out):
        os.remove(out)
    url = "file://" + quote(PAGE)
    cmd = [
        EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        "--user-data-dir=" + BASE + "/_build/" + prof,
        "--window-size=1500,1000", "--virtual-time-budget=20000",
        "--screenshot=" + out, url,
    ]
    print("EDGE_CMD(prefix) =", " ".join(cmd[:6]), "...")
    try:
        rc = subprocess.run(cmd, timeout=90, capture_output=True).returncode
        print("SHOT_RC =", rc)
    except subprocess.TimeoutExpired:
        print("SHOT_RC = TIMEOUT(90s)")
    ok = os.path.exists(out) and os.path.getsize(out) > 1000
    size = os.path.getsize(out) if os.path.exists(out) else -1
    print("PNG =", os.path.basename(out))
    print("PNG_EXISTS =", os.path.exists(out), "bytes =", size, "ok =", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
