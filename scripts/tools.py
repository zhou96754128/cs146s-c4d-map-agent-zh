#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能层：Agent 可调用的工具（function calling）注册表。

每个工具由三部分组成：
- ``spec``：给本地大模型看的 JSON Schema（Ollama ``/api/chat`` 的 ``tools`` 字段格式）；
- ``handler``：真实实现（纯 Python，零依赖）；
- ``post``：可选的记忆层副作用（写事件日志）。

设计原则：**模型负责「决定做什么」，工具负责「把决定落成可复核的事实」**。
坐标在地图上是否出现，取决于模型是否发起了 ``add_place`` 调用；工具不会自作主张补点。
"""

from __future__ import annotations

from typing import Any, Callable

import gazetteer


def _tool(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


_STR = {"type": "string"}
_NUM = {"type": "number"}

TOOL_SPECS: list[dict] = [
    _tool("get_place", "按名称精确查询地名坐标（支持中文名与英文别名，如 SIAS University）。"
                      "只能查到本地索引里已有的地名；查不到就改用 search_places 或询问用户。",
          {"name": {**_STR, "description": "地名，例如 郑州西亚斯学院 / SIAS University"}}, ["name"]),
    _tool("search_places", "按关键词模糊检索本地地名索引，返回若干候选及其坐标。",
          {"keyword": _STR, "limit": {"type": "integer", "description": "最多返回条数，默认 5"}}, ["keyword"]),
    _tool("add_place", "把一个新的地点标记加入地图（写入持久记忆）。"
                       "标记数据以本调用为准——坐标必须由你根据已知信息给出，不要编造而应先用 get_place/search_places 核实。",
          {"name": _STR, "lat": _NUM, "lon": _NUM, "category": _STR, "note": _STR}, ["name", "lat", "lon"]),
    _tool("add_place_from_index", "便捷用法：给出地名，由本地索引解析坐标后加入地图；索引查不到会明确报错。",
          {"name": _STR, "category": _STR, "note": _STR}, ["name"]),
    _tool("update_place", "修改已存在标记的分类或备注。",
          {"name": _STR, "category": _STR, "note": _STR}, ["name"]),
    _tool("remove_place", "从地图与记忆中移除一个标记。", {"name": _STR}, ["name"]),
    _tool("list_places", "列出当前地图上的全部标记（可按分类过滤）。",
          {"category": _STR}, []),
    _tool("count_places", "统计当前标记数量与分类分布。", {}, []),
    _tool("remember_fact", "把一句值得长期记住的事实写入语义记忆（下次会话仍可读到）。",
          {"text": _STR}, ["text"]),
    _tool("recall_facts", "读回此前记住的全部事实。", {}, []),
    _tool("render_map", "把当前记忆里的标记渲染成可缩放、可点击的交互式地图（Leaflet HTML）。"
                        "这是唯一产出地图文件的手段，渲染前请先确认标记集合无误。",
          {"out_path": _STR, "title": _STR, "center_lat": _NUM, "center_lon": _NUM,
           "zoom": {"type": "integer", "description": "初始缩放级别，默认 11"}}, []),
    _tool("print_state", "打印当前记忆状态（标记数 / 事实数 / 事件数），用于自检。", {}, []),
]


class ToolRuntime:
    """工具执行器：持有记忆句柄与模型名，负责分派与副作用记录。"""

    def __init__(self, memory, model: str = "", renderer: Callable[[dict], str] | None = None) -> None:
        self.memory = memory
        self.model = model
        self.renderer = renderer
        self.calls: list[dict] = []

    # -- 具体工具 --
    def t_get_place(self, name: str) -> dict:
        hit = gazetteer.lookup(name)
        if not hit:
            return {"ok": False, "error": "NOT_IN_INDEX", "name": name,
                    "hint": "本地索引无此条目；可用 search_places 模糊找，或直接给出你确信的坐标调用 add_place。"}
        return {"ok": True, "place": {k: hit[k] for k in ("name", "lat", "lon", "category", "city", "address", "accuracy")}}

    def t_search_places(self, keyword: str, limit: int = 5) -> dict:
        hits = gazetteer.search(keyword, int(limit or 5))
        return {"ok": bool(hits), "count": len(hits),
                "results": [{k: h[k] for k in ("name", "lat", "lon", "category", "city")} for h in hits]}

    def t_add_place(self, name: str, lat: float, lon: float, category: str = "", note: str = "") -> dict:
        rec = self.memory.add_place(name, lat, lon, category, note, model=self.model, source="model")
        return {"ok": True, "added": rec, "total": len(self.memory.load_places())}

    def t_add_place_from_index(self, name: str, category: str = "", note: str = "") -> dict:
        hit = gazetteer.lookup(name)
        if not hit:
            return {"ok": False, "error": "NOT_IN_INDEX", "name": name}
        rec = self.memory.add_place(hit["name"], hit["lat"], hit["lon"],
                                    category or hit["category"], note or hit["note"],
                                    model=self.model, source="index")
        return {"ok": True, "added": rec, "total": len(self.memory.load_places())}

    def t_update_place(self, name: str, category: str = "", note: str = "") -> dict:
        ok = self.memory.update_place(name, category, note, model=self.model)
        return {"ok": ok, "name": name} if ok else {"ok": False, "error": "NOT_FOUND", "name": name}

    def t_remove_place(self, name: str) -> dict:
        ok = self.memory.remove_place(name, model=self.model)
        return {"ok": ok, "removed": name, "total": len(self.memory.load_places())}

    def t_list_places(self, category: str = "") -> dict:
        rows = self.memory.load_places()
        if category:
            rows = [r for r in rows if r.get("category") == category]
        return {"ok": True, "count": len(rows), "places": rows}

    def t_count_places(self) -> dict:
        rows = self.memory.load_places()
        dist: dict[str, int] = {}
        for r in rows:
            dist[r.get("category", "未分类")] = dist.get(r.get("category", "未分类"), 0) + 1
        return {"ok": True, "total": len(rows), "by_category": dist}

    def t_remember_fact(self, text: str) -> dict:
        self.memory.remember(text, model=self.model)
        return {"ok": True, "remembered": text, "facts": len(self.memory.facts())}

    def t_recall_facts(self) -> dict:
        f = self.memory.facts()
        return {"ok": True, "count": len(f), "facts": f}

    def t_render_map(self, out_path: str = "", title: str = "", center_lat: float = 0.0,
                     center_lon: float = 0.0, zoom: int = 11) -> dict:
        if self.renderer is None:
            return {"ok": False, "error": "NO_RENDERER"}
        self.memory.save_snapshot()
        payload = {
            "places": self.memory.load_places(),
            "title": title or "本地大模型驱动的地图 Agent",
            "out_path": out_path,
            "center_lat": center_lat, "center_lon": center_lon, "zoom": int(zoom or 11),
        }
        written = self.renderer(payload)
        return {"ok": True, "html": written, "markers": len(payload["places"])}

    def t_print_state(self) -> dict:
        return {"ok": True, **self.memory.stats()}

    # -- 分派 --
    def dispatch(self, name: str, args: dict[str, Any]) -> dict:
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            return {"ok": False, "error": "UNKNOWN_TOOL", "tool": name}
        try:
            result = fn(**args)
        except TypeError as exc:
            result = {"ok": False, "error": "BAD_ARGUMENTS", "detail": str(exc), "tool": name}
        except Exception as exc:  # noqa: BLE001 —— 工具异常必须回流给模型，让它自我纠正
            result = {"ok": False, "error": "TOOL_EXCEPTION", "detail": f"{type(exc).__name__}: {exc}", "tool": name}
        self.memory.log_tool_call(self.model, name, args, bool(result.get("ok")))
        self.calls.append({"tool": name, "args": args, "ok": bool(result.get("ok"))})
        return result


def tool_names() -> list[str]:
    return [t["function"]["name"] for t in TOOL_SPECS]
