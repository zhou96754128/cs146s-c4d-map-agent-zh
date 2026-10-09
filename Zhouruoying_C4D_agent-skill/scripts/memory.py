#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记忆层：Agent 的持久化记忆。

分两类：
1. **空间记忆（places）**——地图上出现的所有标记。
   采用「追加事件日志 + 物化快照」双写：
   - ``memory/places_events.jsonl``：只追加，每条 = 一次模型发起的工具调用（含时间戳、
     模型名、原始参数）。这是「标记由模型生成」的**不可篡改证据**。
   - ``memory/places.json``：由事件日志重放得到的当前快照，供渲染层直接消费。
2. **语义记忆（facts）**——Agent 自己决定要长期记住的一句话事实，
   由 ``remember_fact`` 工具写入 ``memory/facts.md``。

会话记忆 ``memory/session.jsonl``：逐轮记录 user/model/tool 消息，用于跨轮上下文。

零第三方依赖：只用标准库。
"""

from __future__ import annotations

import json
import time
from pathlib import Path


class Memory:
    """Agent 的持久化记忆存储。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "places_events.jsonl"
        self.places_path = self.root / "places.json"
        self.session_path = self.root / "session.jsonl"
        self.facts_path = self.root / "facts.md"

    # ---------------- 空间记忆 ----------------

    def _append_event(self, event: dict) -> None:
        event.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_tool_call(self, model: str, tool: str, args: dict, result_ok: bool) -> None:
        """记录一次模型发起的工具调用（无论成功与否）。"""
        self._append_event({
            "kind": "tool_call", "model": model, "tool": tool,
            "args": args, "ok": bool(result_ok),
        })

    def add_place(self, name: str, lat: float, lon: float, category: str = "",
                  note: str = "", model: str = "", source: str = "model") -> dict:
        rec = {
            "name": name, "lat": round(float(lat), 5), "lon": round(float(lon), 5),
            "category": category or "未分类", "note": note or "",
        }
        self._append_event({"kind": "add_place", "model": model, "source": source, "place": rec})
        return rec

    def remove_place(self, name: str, model: str = "") -> bool:
        existed = any(p["name"] == name for p in self.load_places())
        if existed:
            self._append_event({"kind": "remove_place", "model": model, "name": name})
        return existed

    def update_place(self, name: str, category: str = "", note: str = "", model: str = "") -> bool:
        existed = any(p["name"] == name for p in self.load_places())
        if existed:
            patch = {k: v for k, v in (("category", category), ("note", note)) if v}
            self._append_event({"kind": "update_place", "model": model, "name": name, "patch": patch})
        return existed

    def load_places(self) -> list[dict]:
        """重放事件日志得到当前标记集合（后者覆盖前者，remove 生效）。"""
        if not self.events_path.exists():
            return []
        order: list[str] = []
        state: dict[str, dict] = {}
        with self.events_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = ev.get("kind")
                if kind == "add_place":
                    rec = dict(ev["place"])
                    rec["added_by"] = ev.get("model", "")
                    if rec["name"] not in state:
                        order.append(rec["name"])
                    state[rec["name"]] = rec
                elif kind == "update_place":
                    nm = ev.get("name")
                    if nm in state:
                        state[nm].update(ev.get("patch") or {})
                elif kind == "remove_place":
                    nm = ev.get("name")
                    if nm in state:
                        state.pop(nm, None)
                        if nm in order:
                            order.remove(nm)
        return [state[n] for n in order]

    def save_snapshot(self) -> str:
        """把当前标记集合物化为 places.json，供渲染层使用。"""
        places = self.load_places()
        payload = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "note": "本文件由记忆层从 places_events.jsonl 重放生成；标记数据源自模型工具调用，非人工预置。",
            "count": len(places),
            "places": places,
        }
        self.places_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(self.places_path)

    # ---------------- 语义记忆 ----------------

    def remember(self, text: str, model: str = "") -> None:
        self._append_event({"kind": "remember", "model": model, "text": text})
        stamp = time.strftime("%Y-%m-%d %H:%M")
        with self.facts_path.open("a", encoding="utf-8") as fh:
            fh.write(f"- ({stamp}) {text}\n")

    def facts(self) -> list[str]:
        if not self.facts_path.exists():
            return []
        return [ln.strip() for ln in self.facts_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    # ---------------- 会话记忆 ----------------

    def log_turn(self, role: str, content: str, extra: dict | None = None) -> None:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "role": role, "content": content}
        if extra:
            rec.update(extra)
        with self.session_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def recent_turns(self, limit: int = 12) -> list[dict]:
        if not self.session_path.exists():
            return []
        lines = self.session_path.read_text(encoding="utf-8").splitlines()
        out: list[dict] = []
        for ln in lines[-limit:]:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out

    def stats(self) -> dict:
        events = 0
        if self.events_path.exists():
            events = sum(1 for ln in self.events_path.read_text(encoding="utf-8").splitlines() if ln.strip())
        return {
            "places": len(self.load_places()),
            "facts": len(self.facts()),
            "events": events,
            "root": str(self.root),
        }
