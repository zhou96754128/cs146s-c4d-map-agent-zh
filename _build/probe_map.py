#!/usr/bin/env python3
"""检查渲染产物的关键性质（只读）。

自检脚本 selfcheck.py 的 P16 曾用「产物里是否含 unpkg.com/leaflet」作为
「交互能力已就位」的判据；该判据在把 Leaflet 改为内联后失效。本脚本用于
把产物的真实构成打出来，供修正断言时对照。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def report(path: Path) -> None:
    doc = path.read_text(encoding="utf-8")
    print("=" * 64)
    print("文件:", path.name, "字节:", len(doc.encode("utf-8")))
    probes = ["unpkg", "fitBounds", "L.circleMarker(", 'data-name="', "_leaflet_id",
              "leaflet-pane", "tile.openstreetmap", "autonavi", "__mapAgentReady",
              "L.tileLayer(", "L.map("]
    for k in probes:
        print(f"  {k!r:<26} 出现 {doc.count(k)} 次")
    ext_script = re.findall(r"<script[^>]*\bsrc\s*=\s*[\"'][^\"']+[\"']", doc)
    ext_link = re.findall(r"<link[^>]*\bhref\s*=\s*[\"'][^\"']+[\"']", doc)
    print("  外链 script 标签:", ext_script or "无")
    print("  外链 link 标签:", [x[:100] for x in ext_link] or "无")
    urls = re.findall(r"https?://[^\s\"')]+", doc)
    seen: list[str] = []
    for u in urls:
        host = u.split("/")[2]
        if host not in seen:
            seen.append(host)
    print("  文档中出现的域名:", seen or "无")
    print("  标记数量 data-name=:", doc.count('data-name="'))


def main() -> int:
    targets = sys.argv[1:] or ["Zhouruoying_C4D_map.html"]
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = BASE / t
        if not p.exists():
            print("缺失:", p)
            continue
        report(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
