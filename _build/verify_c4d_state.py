#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C4D 提交前状态核实（只读）。一次性把盘上真实字节/哈希/交付物齐全度打出来，
避免依赖此前互相矛盾的记录。"""
import hashlib
import os
import zipfile

BASE = "/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent"
SHOTS = os.path.join(BASE, "Zhouruoying_C4D_output_screenshots")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def line(p):
    if not os.path.exists(p):
        return "  MISSING  %s" % os.path.relpath(p, BASE)
    b = open(p, "rb").read()
    return "  %9d B  %s  %s" % (len(b), sha(b)[:16], os.path.relpath(p, BASE))


print("=== C4D map-agent 顶层 ===")
for n in sorted(os.listdir(BASE)):
    p = os.path.join(BASE, n)
    if os.path.isdir(p):
        cnt = sum(len(f) for _, _, f in os.walk(p))
        print("  [dir] %-46s %d files" % (n, cnt))
    else:
        print("  [file]%9d B  %s" % (os.path.getsize(p), n))

print()
print("=== 截图目录 ===")
if os.path.isdir(SHOTS):
    for n in sorted(os.listdir(SHOTS)):
        p = os.path.join(SHOTS, n)
        print("  %9d B  %s" % (os.path.getsize(p), n))
else:
    print("  MISSING shots dir")

print()
print("=== 关键产物字节/哈希 ===")
for n in [
    "Zhouruoying_C4D_map.html",
    "Zhouruoying_C4D_郑州足迹地图.html",
    "Zhouruoying_C4D_Agent技能.skill",
    "Zhouruoying_C4D_方案设计.md",
    "Zhouruoying_C4D_验证报告.md",
    "Zhouruoying_C4D_教学说明.md",
    "Zhouruoying_C4D_AI日志.md",
    "Zhouruoying_C4D_拿来说明.md",
    "Zhouruoying_C4D_demo运行记录.md",
    "Zhouruoying_C4D_项目自评.md",
    "Zhouruoying_C4D_AAR.md",
    "README.md",
]:
    print(line(os.path.join(BASE, n)))

print()
print("=== 8 件命名交付物 + 4 件必交物 glob ===")
named = {
    "方案设计": "Zhouruoying_C4D_方案设计.md",
    "agent-skill 目录": "Zhouruoying_C4D_agent-skill",
    "map.html": "Zhouruoying_C4D_map.html",
    "output_screenshots 目录": "Zhouruoying_C4D_output_screenshots",
    "验证报告": "Zhouruoying_C4D_验证报告.md",
    "教学说明": "Zhouruoying_C4D_教学说明.md",
    "AI日志": "Zhouruoying_C4D_AI日志.md",
    "拿来说明": "Zhouruoying_C4D_拿来说明.md",
    "README(额外)": "README.md",
    "项目自评(额外)": "Zhouruoying_C4D_项目自评.md",
    "AAR(额外)": "Zhouruoying_C4D_AAR.md",
    "demo(额外)": "Zhouruoying_C4D_demo运行记录.md",
}
for k, v in named.items():
    p = os.path.join(BASE, v)
    print("  %-24s %s" % (k, "OK" if os.path.exists(p) else "MISSING"))

print()
print("=== .skill 包内容（包名 / 成员数 / 成员） ===")
sp = os.path.join(BASE, "Zhouruoying_C4D_Agent技能.skill")
if os.path.exists(sp):
    b = open(sp, "rb").read()
    z = zipfile.ZipFile(sp)
    names = z.namelist()
    print("  %d B  sha256:%s  成员=%d  testzip=%s" % (len(b), sha(b)[:16], len(names), z.testzip()))
    for n in names:
        print("    -", n)
else:
    print("  MISSING")

print()
print("=== map html 关键结构 ===")
mp = os.path.join(BASE, "Zhouruoying_C4D_map.html")
if os.path.exists(mp):
    doc = open(mp, encoding="utf-8").read()
    checks = {
        "unpkg 引用(应=0)": doc.count("unpkg.com/leaflet"),
        "L.circleMarker(": doc.count("L.circleMarker("),
        'markers[data-name': doc.count("markers[data-name"),
        'data-name="': doc.count('data-name="'),
        "L.tileLayer(": doc.count("L.tileLayer("),
        "L.map(": doc.count("L.map("),
        "fitBounds": doc.count("fitBounds"),
        "__mapAgentReady": doc.count("__mapAgentReady"),
        "外部 <script src": doc.count("<script src=\"http"),
        "外部 <link href": doc.count("<link rel=\"stylesheet\" href=\"http"),
    }
    for k, v in checks.items():
        print("  %-24s %s" % (k, v))
    for bad in ("/Users/xiaowo/", "待补", "TBD", "TODO", "占位"):
        c = doc.count(bad)
        if c:
            print("  [注意] html 命中 %r x%d" % (bad, c))
else:
    print("  MISSING")

print()
print("=== 已交付文档：绝对路径泄漏 / 占位符自检 ===")
for n in sorted(os.listdir(BASE)):
    if not n.endswith(".md"):
        continue
    doc = open(os.path.join(BASE, n), encoding="utf-8").read()
    hits = []
    for bad in ("/Users/xiaowo/", "TODO", "TBD", "FIXME", "待补", "待填", "lorem ipsum"):
        c = doc.count(bad)
        if c:
            hits.append("%s x%d" % (bad, c))
    if hits:
        print("  %-46s %s" % (n, "; ".join(hits)))

print()
print("=== AAR 是否仍是待确认草稿 ===")
aarp = os.path.join(BASE, "Zhouruoying_C4D_AAR.md")
if os.path.exists(aarp):
    txt = open(aarp, encoding="utf-8").read()
    for kw in ("草稿", "待本人确认", "待确认"):
        print("  %-12s x%d" % (kw, txt.count(kw)))

print()
print("=== __pycache__ / 临时目录 ===")
for root, dirs, files in os.walk(BASE):
    if "__pycache__" in dirs:
        print("  found __pycache__ in", os.path.relpath(root, BASE))
print("  done")
