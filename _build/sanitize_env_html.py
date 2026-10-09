#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""净化 01_环境与模型信息.html 中的本机绝对路径（只改这一个文件）。"""
import os

BASE = "/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent"
SP = os.path.join(BASE, "Zhouruoying_C4D_output_screenshots", "01_环境与模型信息.html")
ABS = BASE  # 需要抹掉的前缀

txt = open(SP, "r", encoding="utf-8").read()
before = txt.count("/Users/xiaowo")
txt = txt.replace(ABS, "<项目根目录>")
after = txt.count("/Users/xiaowo")
open(SP, "w", encoding="utf-8").write(txt)
print(f"before={before} after={after} bytes={len(txt.encode('utf-8'))}")

if after:
    for i, line in enumerate(txt.splitlines(), 1):
        if "/Users/xiaowo" in line:
            print(f"  REMAIN {i}: {line.strip()[:160]}")
