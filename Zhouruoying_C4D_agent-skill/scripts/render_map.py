#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染层：把记忆层的标记渲染成单文件交互式地图（Leaflet）。

交互能力：滚轮/双击缩放、拖拽平移、点击标记弹出详情、侧栏点击定位、
分类图例、自适应视野（fitBounds）。产出为**单文件 HTML**，双击即可打开。

零第三方依赖：只用标准库；Leaflet 资产优先**本地内联**（读同包 vendor/），
缺失时回退 CDN。内联后产物是完全自包含的单文件 HTML，断网也能打开交互与查看标记。

底图源是唯一需要联网的部分，因此做了**探活选源**：先探测主源（OpenStreetMap）
的 1 张瓦片，2.5 秒内取不到就自动切到备用源（高德），避免出现满屏空白；
当前底图源与切换原因都会在页面左下角如实标注。实测本机（中国大陆网络）
OSM 瓦片超时不可达、高德可达，故该回退路径不是纸面设计，而是真实生效的路径。
另支持用 URL hash 强制指定底图源：#osm / #amap / #offline，便于受限网络下复现。
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

CATEGORY_COLORS = {
    "校园": "#2563eb", "交通枢纽": "#dc2626", "博物馆": "#7c3aed",
    "人文景点": "#d97706", "遗址公园": "#0d9488", "城镇": "#65a30d",
    "商业地标": "#db2777", "公园": "#16a34a", "展馆": "#0891b2",
    "未分类": "#6b7280",
}


def color_for(cat: str) -> str:
    return CATEGORY_COLORS.get(cat, "#6b7280")


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>__TITLE__</title>
__LEAFLET_CSS__
<style>
  html,body{margin:0;height:100%;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
  #app{display:flex;height:100%}
  #panel{width:310px;min-width:310px;overflow:auto;background:#0f172a;color:#e2e8f0;padding:16px 14px;box-sizing:border-box}
  #panel h1{font-size:15px;margin:0 0 4px;line-height:1.4}
  #panel .meta{font-size:11px;color:#94a3b8;line-height:1.7;margin-bottom:10px}
  #panel .badge{display:inline-block;background:#1e293b;border:1px solid #334155;border-radius:999px;padding:1px 8px;margin:1px 3px 1px 0;font-size:11px}
  .item{display:flex;gap:8px;padding:7px 8px;border-radius:8px;cursor:pointer;align-items:flex-start}
  .item:hover{background:#1e293b}
  .dot{width:10px;height:10px;border-radius:50%;margin-top:4px;flex:0 0 auto}
  .nm{font-size:12.5px;line-height:1.35}
  .sub{font-size:11px;color:#94a3b8;margin-top:2px}
  #map{flex:1}
  .leaflet-popup-content{font-size:12.5px;line-height:1.6}
  .leaflet-popup-content b{font-size:13.5px}
  #foot{font-size:10.5px;color:#64748b;margin-top:12px;border-top:1px solid #1e293b;padding-top:8px;line-height:1.6}
</style>
</head>
<body>
<div id="app">
  <div id="panel">
    <h1>__TITLE__</h1>
    <div class="meta">
      标记 <b>__COUNT__</b> 个 · 生成于 __GENERATED__<br />
      数据来源：本地大模型工具调用（memory/places_events.jsonl）
    </div>
    <div id="cats">__CATEGORIES__</div>
    <div id="list">__LIST__</div>
    <div id="foot">滚轮缩放 · 拖拽平移 · 点击标记看详情 · 点侧栏条目定位<br />当前底图源：<span id="basemapsrc">探测中…</span></div>
    <div id="offlinenote" style="display:none;font-size:10.5px;color:#fbbf24;margin-top:8px;line-height:1.6"></div>
  </div>
  <div id="map"></div>
</div>
__LEAFLET_JS__
<script>
  var PLACES = __PLACES_JSON__;
  var CENTER = [__CENTER_LAT__, __CENTER_LON__];
  var ZOOM = __ZOOM__;
  var map = L.map('map').setView(CENTER, ZOOM);
  // 底图源：主源 OpenStreetMap，备用源高德。先探活 1 张瓦片，再决定用哪个。
  var TILE_SOURCES = [
    { name: 'OpenStreetMap', subdomains: 'abc',
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; OpenStreetMap contributors' },
    { name: '高德地图（备用底图）', subdomains: '1234',
      url: 'https://webst0{s}.is.autonavi.com/appmaptile?style=7&x={x}&y={y}&z={z}',
      attribution: '&copy; 高德地图 AutoNavi' }
  ];
  function note(msg){
    var el = document.getElementById('offlinenote');
    if (el) { el.style.display = 'block'; el.textContent = msg; }
  }
  var tiles = null, picked = 0, switching = false;
  function basemap(i){
    picked = i;
    var s = TILE_SOURCES[i];
    if (tiles) { map.removeLayer(tiles); }
    tiles = L.tileLayer(s.url, {maxZoom: 19, subdomains: s.subdomains, attribution: s.attribution});
    tiles.on('tileerror', onTileError);
    tiles.addTo(map);
    var el = document.getElementById('basemapsrc');
    if (el) el.textContent = s.name;
  }
  function onTileError(){
    if (switching || picked >= TILE_SOURCES.length - 1) return;
    switching = true;
    note('主底图源（' + TILE_SOURCES[picked].name + '）瓦片加载失败，已自动切换到备用底图；标记、名称、分类与坐标不受影响。');
    basemap(picked + 1);
  }
  (function pickBasemap(){
    // 也支持用 URL hash 直接指定底图源：#osm / #amap / #offline。
    // 在受限网络下复现固定底图、或做截图/录屏时非常有用。
    var force = (location.hash || '').replace('#', '').toLowerCase();
    if (force === 'offline') {
      note('离线模式（#offline）：不加载任何底图瓦片；标记、名称、分类与坐标照常可用。');
      return;
    }
    if (force === 'amap') { basemap(1); return; }
    if (force === 'osm') { basemap(0); return; }
    var img = new Image(), done = false;
    var timer = setTimeout(function(){
      if (done) return; done = true;
      note('2.5 秒内未取到主底图瓦片（本机网络下 OpenStreetMap 不可达），已改用备用底图；标记与坐标不受影响。');
      basemap(1);
    }, 2500);
    img.onload = function(){ if (done) return; done = true; clearTimeout(timer); basemap(0); };
    img.onerror = function(){
      if (done) return; done = true; clearTimeout(timer);
      note('主底图源不可达，已改用备用底图；标记与坐标不受影响。');
      basemap(1);
    };
    img.src = TILE_SOURCES[0].url.replace('{s}','a').replace('{z}','1').replace('{x}','0').replace('{y}','0');
  })();
  L.control.scale({imperial:false}).addTo(map);
  var markers = {};
  function popupHtml(p){
    var s = '<b>' + p.name + '</b><br/>分类：' + p.category;
    if (p.note) s += '<br/>备注：' + p.note;
    s += '<br/>坐标：' + p.lat + ', ' + p.lon;
    if (p.added_by) s += '<br/><span style="color:#64748b">由 ' + p.added_by + ' 写入</span>';
    return s;
  }
  function addMarker(p){
    var m = L.circleMarker([p.lat, p.lon], {
      radius: 8, color: '#ffffff', weight: 2, fillColor: p.color, fillOpacity: 0.95
    }).addTo(map);
    m.bindPopup(popupHtml(p));
    markers[p.name] = m;
  }
  PLACES.forEach(addMarker);
  if (PLACES.length > 1) {
    map.fitBounds(PLACES.map(function(p){ return [p.lat, p.lon]; }), {padding:[40,40]});
  }
  document.querySelectorAll('.item').forEach(function(el){
    el.addEventListener('click', function(){
      var m = markers[el.getAttribute('data-name')];
      if (m) { map.setView(m.getLatLng(), 15); m.openPopup(); }
    });
  });
  window.__mapAgentReady = true;
</script>
</body>
</html>
"""


def _leaflet_tags() -> tuple[str, str]:
    """优先内联本地 Leaflet 资产（同包 vendor/），缺失时回退 CDN。

    内联后产物是**完全自包含的单文件 HTML**：断网也能打开、交互、看标记。
    """
    here = Path(__file__).resolve().parent
    for base in (here.parent / "vendor", here / "vendor"):
        css, js = base / "leaflet.css", base / "leaflet.js"
        if css.exists() and js.exists():
            return (f"<style>\n{css.read_text(encoding='utf-8')}\n</style>",
                    f"<script>\n{js.read_text(encoding='utf-8')}\n</script>")
    return ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />',
            '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>')


def render(payload: dict, out_path: str = "", default_out: str = "map.html") -> str:
    places = payload.get("places") or []
    target = Path(out_path or payload.get("out_path") or default_out)
    if target.suffix.lower() != ".html":
        target = target.with_suffix(".html")
    target.parent.mkdir(parents=True, exist_ok=True)

    enriched = []
    for p in places:
        q = dict(p)
        q["color"] = color_for(p.get("category", "未分类"))
        enriched.append(q)

    dist = Counter(p.get("category", "未分类") for p in enriched)
    cats = "".join(
        f'<span class="badge"><span class="dot" style="display:inline-block;background:{color_for(c)}"></span> {c} {n}</span>'
        for c, n in sorted(dist.items(), key=lambda t: -t[1])
    )
    items = "".join(
        f'<div class="item" data-name="{p["name"]}">'
        f'<span class="dot" style="background:{p["color"]}"></span>'
        f'<span><span class="nm">{p["name"]}</span>'
        f'<div class="sub">{p.get("category","未分类")} · {p["lat"]}, {p["lon"]}</div></span></div>'
        for p in enriched
    )

    lat = payload.get("center_lat") or (enriched[0]["lat"] if enriched else 34.5270)
    lon = payload.get("center_lon") or (enriched[0]["lon"] if enriched else 113.7450)

    html = (_TEMPLATE
            .replace("__TITLE__", str(payload.get("title") or "本地大模型驱动的地图 Agent"))
            .replace("__COUNT__", str(len(enriched)))
            .replace("__GENERATED__", time.strftime("%Y-%m-%d %H:%M:%S"))
            .replace("__CATEGORIES__", cats or '<span class="badge">暂无标记</span>')
            .replace("__LIST__", items)
            .replace("__PLACES_JSON__", json.dumps(enriched, ensure_ascii=False))
            .replace("__CENTER_LAT__", f"{float(lat):.5f}")
            .replace("__CENTER_LON__", f"{float(lon):.5f}")
            .replace("__ZOOM__", str(int(payload.get("zoom") or 11))))
    # Leaflet 资产最后替换（内联正文可能含其它下划线占位符形态，放最后最安全）
    css_tag, js_tag = _leaflet_tags()
    html = html.replace("__LEAFLET_CSS__", css_tag).replace("__LEAFLET_JS__", js_tag)
    target.write_text(html, encoding="utf-8")
    return str(target)
