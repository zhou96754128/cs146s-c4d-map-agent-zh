#!/usr/bin/env python3
"""探测本机对各瓦片/依赖源的网络可达性（只读、无副作用）。

用途：C4D 地图的底图瓦片与 Leaflet 资源分别来自哪里，必须先实测能不能到达，
再决定「内联 / 换源 / 离线」三种策略。结果写入 logs/probe_net.json。
"""
from __future__ import annotations

import json
import socket
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TARGETS = [
    ("OSM 底图瓦片", "https://tile.openstreetmap.org/0/0/0.png"),
    ("unpkg CDN（Leaflet）", "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
    ("高德底图瓦片", "https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x=0&y=0&z=1"),
    ("高德底图瓦片(备用)", "https://webst01.is.autonavi.com/appmaptile?style=7&x=0&y=0&z=1"),
    ("天地图瓦片", "https://t0.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX=0&TILEROW=0&TILECOL=0"),
    ("Carto 底图瓦片", "https://a.basemaps.cartocdn.com/light_all/0/0/0.png"),
    ("GitHub（对照，已知可达）", "https://github.com/robots.txt"),
]


def probe(name: str, url: str, timeout: float = 8.0) -> dict:
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "c4d-probe/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
        return {"name": name, "url": url, "ok": True, "status": getattr(r, "status", 0),
                "bytes": len(body), "sec": round(time.time() - t0, 2)}
    except Exception as e:  # noqa: BLE001 - 探测脚本需要把所有失败都记下来
        return {"name": name, "url": url, "ok": False,
                "error": f"{type(e).__name__}: {e}", "sec": round(time.time() - t0, 2)}


def main() -> int:
    socket.setdefaulttimeout(8)
    rows = [probe(n, u) for n, u in TARGETS]
    for r in rows:
        mark = "OK  " if r["ok"] else "FAIL"
        extra = f"{r['bytes']} B / {r['sec']}s" if r["ok"] else r["error"]
        print(f"[{mark}] {r['name']:<26} {extra}")
    reachable = [r["name"] for r in rows if r["ok"]]
    print("-" * 60)
    print("可达：", reachable or "无")
    out = BASE / "logs" / "probe_net.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"targets": rows, "reachable": reachable},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("写入", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
