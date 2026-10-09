#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C4D 提交前扣分项自筛（只读）。逐项打印 PASS / RISK / NA，不做任何修改。"""
import hashlib
import os
import re
import zipfile

BASE = "/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent"

REQUIRED_GLOBS_KEYS = ["Agent技能", "demo", "AI日志", "AAR"]
NAMED = [
    "Zhouruoying_C4D_方案设计.md",
    "Zhouruoying_C4D_agent-skill",
    "Zhouruoying_C4D_map.html",
    "Zhouruoying_C4D_output_screenshots",
    "Zhouruoying_C4D_验证报告.md",
    "Zhouruoying_C4D_教学说明.md",
    "Zhouruoying_C4D_AI日志.md",
    "Zhouruoying_C4D_拿来说明.md",
    "README.md",
]
PLACEHOLDERS = ["TODO", "TBD", "FIXME", "待补", "待填", "占位", "lorem ipsum", "✍️"]
SKIP_DIRS = {"__pycache__", ".git", "_build", "vendor", "_shotprobe"}
SCAN_EXT = (".md", ".py", ".html", ".txt", ".json", ".yaml", ".yml")

results = []
def rec(level, item, detail):
    results.append((level, item, detail))

# 1) 必交物存在性
names = os.listdir(BASE)
for g in REQUIRED_GLOBS_KEYS:
    hit = [n for n in names if g in n]
    rec("PASS" if hit else "RISK", f"必交物 glob *{g}*", ", ".join(hit) if hit else "未命中")
for n in NAMED:
    p = os.path.join(BASE, n)
    rec("PASS" if os.path.exists(p) else "RISK", f"点名交付 {n}", "存在" if os.path.exists(p) else "缺失")

# 2) 占位符扫描（排除自检脚本自身 / 审计脚本自身）
hits = []
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for f in files:
        if not f.endswith(SCAN_EXT):
            continue
        fp = os.path.join(root, f)
        if f in ("selfcheck.py", "audit9_deductions.py"):
            continue
        try:
            txt = open(fp, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for pat in PLACEHOLDERS:
            if pat.lower() in txt.lower():
                rel = os.path.relpath(fp, BASE)
                for i, line in enumerate(txt.splitlines(), 1):
                    if pat.lower() in line.lower():
                        hits.append(f"{rel}:{i}:{pat}")
rec("PASS" if not hits else "RISK", "占位符扫描", "无" if not hits else "; ".join(hits[:12]))

# 3) 绝对路径泄漏（交付物正文里不该出现本机 home 路径）
leak = []
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for f in files:
        if not f.endswith((".md", ".py", ".html")):
            continue
        fp = os.path.join(root, f)
        if f in ("status_c4d.py", "audit9_deductions.py"):
            continue
        try:
            txt = open(fp, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if "/Users/xiaowo" in txt:
            leak.append(os.path.relpath(fp, BASE))
rec("PASS" if not leak else "RISK", "绝对路径泄漏", "无" if not leak else ", ".join(leak[:10]))

# 4) __pycache__ / 垃圾文件
junk = []
for root, dirs, files in os.walk(BASE):
    if "__pycache__" in dirs:
        junk.append(os.path.relpath(os.path.join(root, "__pycache__"), BASE))
    for f in files:
        if f in (".DS_Store",) or f.endswith(".pyc"):
            junk.append(os.path.relpath(os.path.join(root, f), BASE))
rec("PASS" if not junk else "RISK", "缓存/垃圾文件", "无" if not junk else ", ".join(junk[:10]))

# 5) .skill 包结构
sp = os.path.join(BASE, "Zhouruoying_C4D_Agent技能.skill")
if os.path.exists(sp):
    with zipfile.ZipFile(sp) as z:
        mem = z.namelist()
        bad = z.testzip()
    rec("PASS" if bad is None else "RISK", ".skill 完整性", f"{len(mem)} 成员, testzip={bad}")
    need = ["SKILL.md"]
    missing = [x for x in need if not any(m.endswith(x) for m in mem)]
    rec("PASS" if not missing else "RISK", ".skill 含 SKILL.md", "OK" if not missing else f"缺 {missing}")
else:
    rec("RISK", ".skill 存在性", "未找到")

# 6) scripts 根目录 vs skill 目录 字节一致
root_s = os.path.join(BASE, "scripts")
skill_s = os.path.join(BASE, "Zhouruoying_C4D_agent-skill", "scripts")
diff = []
if os.path.isdir(root_s) and os.path.isdir(skill_s):
    for f in sorted(os.listdir(root_s)):
        if not f.endswith(".py"):
            continue
        a, b = os.path.join(root_s, f), os.path.join(skill_s, f)
        if not os.path.exists(b):
            diff.append(f"{f}:skill缺")
            continue
        ha = hashlib.sha256(open(a, "rb").read()).hexdigest()[:16]
        hb = hashlib.sha256(open(b, "rb").read()).hexdigest()[:16]
        if ha != hb:
            diff.append(f"{f}:{ha}!={hb}")
    rec("PASS" if not diff else "RISK", "scripts 根↔skill 一致", "全部一致" if not diff else ", ".join(diff))
else:
    rec("RISK", "scripts 根↔skill 一致", "目录缺失")

# 7) 地图产物：外部依赖 / 标记数
mh = os.path.join(BASE, "Zhouruoying_C4D_map.html")
if os.path.exists(mh):
    doc = open(mh, "r", encoding="utf-8", errors="ignore").read()
    ext = re.findall(r"<(?:script|link)[^>]*(?:src|href)=[\"'](https?://[^\"']+)", doc)
    rec("PASS" if not ext else "RISK", "地图外部 script/link", "无" if not ext else ", ".join(ext[:8]))
    rec("PASS" if "unpkg.com" not in doc else "RISK", "地图零 CDN 引用", str(doc.count("unpkg.com")))
    rec("PASS" if doc.count('data-name="') == 6 else "RISK", "地图标记数", str(doc.count('data-name="')))
    rec("PASS" if "window.__mapAgentReady" in doc else "RISK", "就绪信号", str(doc.count("window.__mapAgentReady")))

# 8) 哈希快照
for f in ["Zhouruoying_C4D_map.html", "Zhouruoying_C4D_郑州足迹地图.html", "Zhouruoying_C4D_Agent技能.skill"]:
    p = os.path.join(BASE, f)
    if os.path.exists(p):
        b = open(p, "rb").read()
        rec("NA", f"哈希 {f}", f"{len(b)} B / {hashlib.sha256(b).hexdigest()[:16]}")

print("== C4D 提交前扣分项自筛 ==")
risk = 0
for lvl, item, detail in results:
    if lvl == "RISK":
        risk += 1
    print(f"[{lvl}] {item} :: {detail}")
print(f"\nRISK 合计 = {risk}")
