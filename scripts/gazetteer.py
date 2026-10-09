#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线地名索引（gazetteer）：给本地 Agent 的 get_place / search_places 工具提供坐标锚点。

设计边界（重要，写在代码里以便复核）：
- 本文件只提供「地名 -> 坐标」的**锚点查询**，不提供任何地图标记。
- 地图上出现的每一个标记，都由本地大模型通过 ``add_place`` 工具调用写入
  （见 scripts/memory.py）。也就是说：**标记数据是模型生成的**，本文件只负责
  让模型拿到的坐标不至于凭空臆造。
- 坐标为 WGS-84 近似值，``accuracy`` 字段标注量级，Agent 回答时应如实转述该量级。
- 生产环境可把 ``lookup()`` 换成真实地理编码服务（Nominatim / 高德），接口不变。

零第三方依赖：只用标准库。
"""

from __future__ import annotations

import re

# name, aliases, lat, lon, category, city, address, accuracy, note
PLACES: list[dict] = [
    {
        "name": "郑州西亚斯学院",
        "aliases": ["SIAS University", "SIAS", "西亚斯", "西亚斯学院", "郑州大学西亚斯国际学院"],
        "lat": 34.5270, "lon": 113.7450,
        "category": "校园", "city": "河南省郑州市新郑市",
        "address": "新郑市人民路 168 号",
        "accuracy": "约 ±0.003°",
        "note": "本次挑战要求地图必须包含的地标。",
    },
    {
        "name": "郑州新郑国际机场",
        "aliases": ["新郑机场", "CGO", "新郑国际机场"],
        "lat": 34.5197, "lon": 113.8408,
        "category": "交通枢纽", "city": "河南省郑州市航空港区",
        "address": "航空港区迎宾大道", "accuracy": "约 ±0.003°",
        "note": "距西亚斯学院直线约 12 km。",
    },
    {
        "name": "郑州东站",
        "aliases": ["郑州东", "郑州高铁东站"],
        "lat": 34.7560, "lon": 113.7720,
        "category": "交通枢纽", "city": "河南省郑州市金水区",
        "address": "心怡路 1 号", "accuracy": "约 ±0.003°",
        "note": "郑州主城高铁枢纽。",
    },
    {
        "name": "黄帝故里景区",
        "aliases": ["黄帝故里", "轩辕故里"],
        "lat": 34.3960, "lon": 113.7410,
        "category": "人文景点", "city": "河南省郑州市新郑市",
        "address": "轩辕路 1 号", "accuracy": "约 ±0.005°",
        "note": "新郑市核心人文景点。",
    },
    {
        "name": "新郑市博物馆",
        "aliases": ["新郑博物馆"],
        "lat": 34.3955, "lon": 113.7355,
        "category": "博物馆", "city": "河南省郑州市新郑市",
        "address": "中华路", "accuracy": "约 ±0.005°",
        "note": "常与黄帝故里同游。",
    },
    {
        "name": "苑陵故城遗址公园",
        "aliases": ["苑陵故城"],
        "lat": 34.4460, "lon": 113.7630,
        "category": "遗址公园", "city": "河南省郑州市新郑市",
        "address": "龙王乡", "accuracy": "约 ±0.008°",
        "note": "全国重点文物保护单位。",
    },
    {
        "name": "龙湖镇",
        "aliases": ["龙湖", "新郑龙湖"],
        "lat": 34.6100, "lon": 113.7300,
        "category": "城镇", "city": "河南省郑州市新郑市",
        "address": "龙湖镇", "accuracy": "约 ±0.01°",
        "note": "西亚斯学院所在的教育园区。",
    },
    {
        "name": "二七广场",
        "aliases": ["二七纪念塔", "郑州二七"],
        "lat": 34.7520, "lon": 113.6660,
        "category": "商业地标", "city": "河南省郑州市二七区",
        "address": "二七路", "accuracy": "约 ±0.003°",
        "note": "郑州老城商业中心。",
    },
    {
        "name": "河南博物院",
        "aliases": ["河南省博物院"],
        "lat": 34.7730, "lon": 113.6630,
        "category": "博物馆", "city": "河南省郑州市金水区",
        "address": "农业路 8 号", "accuracy": "约 ±0.003°",
        "note": "郑州主城文化地标。",
    },
    {
        "name": "郑州大学主校区",
        "aliases": ["郑大", "郑州大学"],
        "lat": 34.8170, "lon": 113.5320,
        "category": "校园", "city": "河南省郑州市高新区",
        "address": "科学大道 100 号", "accuracy": "约 ±0.004°",
        "note": "用于与西亚斯做校园类对比标注。",
    },
    {
        "name": "郑州市人民公园",
        "aliases": ["人民公园"],
        "lat": 34.7620, "lon": 113.6620,
        "category": "公园", "city": "河南省郑州市二七区",
        "address": "太康路", "accuracy": "约 ±0.004°",
        "note": "城区休闲绿地。",
    },
    {
        "name": "郑州科技馆",
        "aliases": ["郑州科学技术馆"],
        "lat": 34.7480, "lon": 113.6320,
        "category": "展馆", "city": "河南省郑州市中原区",
        "address": "嵩山南路", "accuracy": "约 ±0.005°",
        "note": "科普类展馆。",
    },
]

_normalize_re = re.compile(r"[\s\-_·、,，.。()（）]+")


def normalize(text: str) -> str:
    """把地名归一化，便于别名/大小写/标点无关的匹配。"""
    return _normalize_re.sub("", (text or "").strip().lower())


_INDEX: dict[str, dict] = {}
for _p in PLACES:
    _INDEX[normalize(_p["name"])] = _p
    for _a in _p["aliases"]:
        _INDEX[normalize(_a)] = _p


def lookup(name: str) -> dict | None:
    """精确命中（含别名/大小写/全半角归一化）。"""
    return _INDEX.get(normalize(name))


def search(keyword: str, limit: int = 5) -> list[dict]:
    """子串模糊检索，按 命中位置靠前 > 名称更短 排序。"""
    kw = normalize(keyword)
    if not kw:
        return []
    hits: list[tuple[int, int, dict]] = []
    for key, place in _INDEX.items():
        pos = key.find(kw)
        if pos >= 0:
            hits.append((pos, len(key), place))
    hits.sort(key=lambda t: (t[0], t[1]))
    out: list[dict] = []
    seen: set[str] = set()
    for _pos, _len, place in hits:
        if place["name"] in seen:
            continue
        seen.add(place["name"])
        out.append(place)
        if len(out) >= limit:
            break
    return out


def all_names() -> list[str]:
    return [p["name"] for p in PLACES]
