#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent 主循环：本地大模型（Ollama）驱动的「观察 → 决策 → 调用工具 → 观察」循环。

关键约束（挑战要求）：
- **不依赖云端 API**：只与 http://127.0.0.1:11434 通信；任何外部模型调用一律没有。
- **标记由模型生成**：循环把模型的 tool_calls 落到记忆层，地图标记不是脚本写死的。
- **全过程可复核**：每一步（模型原始输出、工具参数、工具返回）都写入 run 日志 JSONL。

零第三方依赖：只用标准库（urllib）。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import render_map
import tools as toolmod

OLLAMA_HOST = "http://127.0.0.1:11434"

SYSTEM_PROMPT = """你是一个运行在用户本机上的地图助手 Agent（本地大模型，不访问云端 API）。

你可以调用工具来操作一张真实的交互式地图，并且你会拥有持久记忆：
- 地图上出现的每一个标记，都必须由你调用 add_place / add_place_from_index 写入；
- 工具不会替你补点，你不调用就没有标记；
- 先用 get_place / search_places 核实坐标，再写入；索引里没有的地名，如果你确信坐标可以直接 add_place，
  否则应如实告知用户查不到，不要臆造。
- 需要长期记住的结论用 remember_fact 写入。
- 渲染地图时直接调用 render_map：out_path 可以省略（省略即写入默认 HTML 文件），
  不要反问用户保存路径，也不要因为缺少路径而拒绝渲染。

工作方式：能确定的事直接做，做完用一两句话向用户汇报结果（不要输出工具调用的原始 JSON）。
"""


class OllamaClient:
    """极简 Ollama 客户端（/api/chat，非流式）。"""

    def __init__(self, model: str, host: str = OLLAMA_HOST, timeout: int = 300,
                 temperature: float = 0.2, num_ctx: int = 8192,
                 think: bool | None = None) -> None:
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout
        self.temperature, self.num_ctx = temperature, num_ctx
        # None = 用服务端默认；False = 关闭 qwen3 一类模型的「思考段」（demo 里更快、输出更短）
        self.think = think

    def chat(self, messages: list[dict], tool_specs: list[dict]) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "tools": tool_specs,
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        if self.think is not None:
            body["think"] = self.think
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def tags(self) -> dict:
        with urllib.request.urlopen(f"{self.host}/api/tags", timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))


class MapAgent:
    """带记忆与工具的地图 Agent。"""

    def __init__(self, model: str, memory, run_log: Path, max_steps: int = 12,
                 host: str = OLLAMA_HOST, think: bool | None = None) -> None:
        self.model = model
        self.memory = memory
        self.run_log = Path(run_log)
        self.run_log.parent.mkdir(parents=True, exist_ok=True)
        self.max_steps = max_steps
        self.client = OllamaClient(model, host=host, think=think)
        self.rt = toolmod.ToolRuntime(memory=self.memory, model=model, renderer=self._render)

    def _render(self, payload: dict) -> str:
        # 默认输出到规范文件名：模型省略 out_path 时也落到交付物命名，避免出现第二个地图文件
        return render_map.render(payload, default_out="Zhouruoying_C4D_郑州足迹地图.html")

    def _log(self, kind: str, **fields) -> None:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": self.model, "kind": kind}
        rec.update(fields)
        with self.run_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def run(self, task: str, max_steps: int | None = None) -> dict:
        steps = int(max_steps or self.max_steps)
        self._log("task", task=task, max_steps=steps, tools=toolmod.tool_names())
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]
        self.memory.log_turn("user", task)
        trace: list[dict] = []
        final = ""
        status = "max_steps"
        for i in range(1, steps + 1):
            try:
                resp = self.client.chat(messages, toolmod.TOOL_SPECS)
            except urllib.error.URLError as exc:
                status = "llm_unreachable"
                final = f"本地模型不可达：{exc}"
                self._log("error", step=i, detail=final)
                break
            msg = resp.get("message") or {}
            content = (msg.get("content") or "").strip()
            calls = msg.get("tool_calls") or []
            self._log("model", step=i, content=content,
                      tool_calls=[{"name": c.get("function", {}).get("name"),
                                   "arguments": c.get("function", {}).get("arguments")} for c in calls],
                      eval_count=resp.get("eval_count"), total_duration=resp.get("total_duration"))
            if not calls:
                final = content
                status = "done"
                break
            messages.append({"role": "assistant", "content": content, "tool_calls": calls})
            for call in calls:
                fn = call.get("function") or {}
                name = fn.get("name") or ""
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                result = self.rt.dispatch(name, args)
                trace.append({"step": i, "tool": name, "args": args, "ok": bool(result.get("ok"))})
                self._log("tool", step=i, tool=name, args=args, ok=bool(result.get("ok")))
                messages.append({"role": "tool", "tool_name": name,
                                 "content": json.dumps(result, ensure_ascii=False)})
        self.memory.log_turn("assistant", final or "(未产生最终答复)")
        summary = {
            "status": status, "model": self.model, "steps_used": len(trace),
            "tool_calls": trace, "final": final, **self.memory.stats(),
        }
        self._log("result", **{k: summary[k] for k in ("status", "steps_used", "places", "facts", "events")})
        return summary
