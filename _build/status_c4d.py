#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C4D 状态盘点：关键产物的字节数 / sha256 / 结构断言。只读。"""
import hashlib
import os
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "Zhouruoying_C4D_map.html",
    "Zhouruoying_C4D_郑州足迹地图.html",
    "Zhouruoying_C4D_Agent技能.skill",
    "Zhouruoying_C4D_方案设计.md",
    "Zhouruoying_C4D_验证报告.md",
    "Zhouruoying_C4D_教学说明.md",
    "Zhouruoying_C4D_AI日志.md",
    "Zhouruoying_C4D_demo运行记录.md",
    "Zhouruoying_C4D_拿来说明.md",
    "README.md",
    "Zhouruoying_C4D_项目自评.md",
    "Zhouruoying_C4D_AAR.md",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_map(path):
    with open(path, "r", encoding="utf-8") as f:
        doc = f.read()
    return {
        "bytes": os.path.getsize(path),
        "unpkg": doc.count("unpkg.com"),
        "circleMarker": doc.count("L.circleMarker("),
        "data_name": doc.count('data-name="'),
        "fitBounds": doc.count("fitBounds"),
        "osm_tile": doc.count("tile.openstreetmap"),
        "autonavi": doc.count("autonavi"),
        "hash_osm": doc.count("#osm") + doc.count('"osm"'),
        "ready": doc.count("__mapAgentReady"),
    }


print("== files ==")
for name in FILES:
    p = os.path.join(BASE, name)
    if os.path.exists(p):
        print("%-42s %8d  %s" % (name, os.path.getsize(p), sha256(p)[:16]))
    else:
        print("%-42s %8s  MISSING" % (name, "-"))

print("\n== map probes ==")
for name in ("Zhouruoying_C4D_map.html", "Zhouruoying_C4D_郑州足迹地图.html"):
    p = os.path.join(BASE, name)
    if os.path.exists(p):
        print(name, probe_map(p))
    else:
        print(name, "MISSING")

print("\n== skill zip ==")
sp = os.path.join(BASE, "Zhouruoying_C4D_Agent技能.skill")
if os.path.exists(sp):
    with zipfile.ZipFile(sp) as z:
        names = z.namelist()
        print("members=%d testzip=%s" % (len(names), z.testzip()))
        for n in sorted(names):
            print("   ", n)

print("\n== screenshots ==")
sd = os.path.join(BASE, "Zhouruoying_C4D_output_screenshots")
for n in sorted(os.listdir(sd)):
    print("   %-28s %8d" % (n, os.path.getsize(os.path.join(sd, n))))
