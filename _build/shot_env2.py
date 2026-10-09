#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Edge 无头模式给 01_环境与模型信息.html 截图（照抄 shot_map.py 的可用写法）。

用法：python3 _build/shot_env2.py [profile名]
默认输出 Zhouruoying_C4D_output_screenshots/01_环境与模型信息.png

与 shot_env.py 的两处关键差别（都是为了让「截图成功」这件事可被证明）：
1. 先 os.remove(OUT)，再截图 —— 旧文件不会造成「PNG_EXISTS=True」假阳性；
2. 页面文件名含中文，file:// URL 必须做百分号编码，否则 Edge 打不开会挂住。
"""
from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import quote

EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
BASE = "/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent"
PAGE = BASE + "/Zhouruoying_C4D_output_screenshots/01_环境与模型信息.html"
OUT = BASE + "/Zhouruoying_C4D_output_screenshots/01_环境与模型信息.png"


def main() -> int:
    prof = sys.argv[1] if len(sys.argv) > 1 else "edgeprof_env2"
    if os.path.exists(OUT):
        os.remove(OUT)
    url = "file://" + quote(PAGE)
    cmd = [
        EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        "--user-data-dir=" + BASE + "/_build/" + prof,
        "--window-size=1500,1000", "--virtual-time-budget=20000",
        "--screenshot=" + OUT, url,
    ]
    print("URL =", url)
    try:
        rc = subprocess.run(cmd, timeout=60, capture_output=True).returncode
        print("SHOT_RC =", rc)
    except subprocess.TimeoutExpired:
        print("SHOT_RC = TIMEOUT(60s)")
    exists = os.path.exists(OUT)
    size = os.path.getsize(OUT) if exists else -1
    print("PNG =", OUT)
    print("PNG_WRITTEN_THIS_RUN =", exists, "bytes =", size)
    return 0 if (exists and size > 1000) else 1


if __name__ == "__main__":
    raise SystemExit(main())
