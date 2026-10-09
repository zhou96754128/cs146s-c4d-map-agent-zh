#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C4D demo 驱动：用**本机** Ollama 上的本地大模型驱动地图 Agent（不访问云端 API）。

用法：
    python3 scripts/run_agent.py --reset                 # 清空记忆后跑默认多轮 demo
    python3 scripts/run_agent.py --task "把郑州东站标出来"
    python3 scripts/run_agent.py --model gemma4:e4b --reset
    python3 scripts/run_agent.py --offline-check         # 只检查本机端点与模型可用性

产物：
    memory/places_events.jsonl  追加式事件日志（标记增删、工具调用、记忆写入）
    memory/places.json          标记快照（由事件日志重放生成）
    memory/session.jsonl        会话轮次
    memory/facts.md             语义记忆
    logs/run_log.jsonl          逐步轨迹（模型原始输出 + 工具参数 + 工具返回）
    logs/session_summary.json   本次运行的机器可读摘要
    map.html                    交互式地图（单文件）
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import agent as agentmod  # noqa: E402
import memory as memmod  # noqa: E402

MAP_OUT_NAME = "Zhouruoying_C4D_郑州足迹地图.html"
MAP_TITLE = "我的郑州足迹（本地大模型 Agent 生成）"
# 渲染意图下模型若整轮不调工具（典型：反问用户要中心点），注入一次纠正指令让它自己改正
NUDGE_MSG = ("请立即调用 render_map 工具完成渲染：out_path、center_lat、center_lon、zoom 全部省略，"
             "直接使用默认值，不要反问用户，不要跳过这一步。")

DEFAULT_TASKS = [
    "把「郑州西亚斯学院」和「黄帝故里景区」标到地图上，分别按校园和人文景点分类。",
    "再标出「郑州新郑国际机场」「郑州东站」「河南博物院」「二七广场」，"
    "分类依次是交通枢纽、交通枢纽、博物馆、商业地标。",
    "河南博物院其实更适合归到人文景点，帮我把它的分类改过来。",
    "记住一句话：我周末常去的地方是郑州西亚斯学院、河南博物院和二七广场。",
    "把地图渲染出来，标题用「我的郑州足迹（本地大模型 Agent 生成）」。",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="本地大模型地图 Agent 驱动脚本")
    p.add_argument("--model", default="qwen3:8b", help="本机 Ollama 模型名（默认 qwen3:8b）")
    p.add_argument("--task", action="append", default=[], help="一轮任务，可重复；缺省用内置多轮 demo")
    p.add_argument("--max-steps", type=int, default=12, help="单轮最多工具步数")
    p.add_argument("--reset", action="store_true", help="先清空 memory/ 与 logs/")
    p.add_argument("--no-think", action="store_true", help="关闭模型思考段（更快）")
    p.add_argument("--host", default=agentmod.OLLAMA_HOST, help="Ollama 端点，默认本机 11434")
    p.add_argument("--offline-check", action="store_true", help="只检查端点/模型可用性后退出")
    return p.parse_args()


def offline_check(model: str, host: str) -> int:
    import urllib.error
    import urllib.request

    print(f"[offline-check] 端点 {host}")
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=10) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"[offline-check] 本地模型服务不可达：{exc}（未联网检查已跳过）")
        return 2
    names = [m.get("name") for m in tags.get("models", [])]
    print(f"[offline-check] 本机已有模型：{names}")
    if model not in names:
        print(f"[offline-check] 目标模型 {model} 尚未就绪（可能需要先 ollama pull）")
        return 3
    print(f"[offline-check] OK：{model} 已就绪，全部推理在本机完成")
    return 0


def main() -> int:
    args = parse_args()
    if args.offline_check:
        return offline_check(args.model, args.host)

    mem_dir, log_dir = ROOT / "memory", ROOT / "logs"
    if args.reset:
        for d in (mem_dir, log_dir):
            if d.exists():
                shutil.rmtree(d)
        print(f"[reset] 已清空 {mem_dir.name}/ 与 {log_dir.name}/")

    memory = memmod.Memory(mem_dir)
    run_log = log_dir / "run_log.jsonl"
    ag = agentmod.MapAgent(model=args.model, memory=memory, run_log=run_log,
                           max_steps=args.max_steps, host=args.host,
                           think=False if args.no_think else None)

    tasks = args.task or DEFAULT_TASKS
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"=== C4D demo | 模型 {args.model} | 端点 {args.host} | 共 {len(tasks)} 轮 ===")
    summaries: list[dict] = []
    for idx, task in enumerate(tasks, 1):
        t0 = time.time()
        print(f"\n--- 第 {idx} 轮 ---\n用户：{task}")
        try:
            s = ag.run(task)
        except Exception as exc:  # noqa: BLE001 —— demo 要留下失败证据而不是静默中断
            s = {"status": "exception", "error": f"{type(exc).__name__}: {exc}", "model": args.model,
                 "steps_used": 0, "tool_calls": [], "final": ""}
            ag._log("exception", detail=s["error"])  # noqa: SLF001
        # 显式重试纠偏：渲染意图下模型整轮未调用任何工具时，驱动层注入一次纠正指令，
        # 由模型自己补上 render_map；日志留证（nudge 事件），不靠兜底渲染掩盖短板。
        if ("渲染" in task or "地图" in task) and not s.get("tool_calls"):
            ag._log("nudge", turn=idx, reason="渲染意图但本轮无工具调用，注入一次纠正指令")  # noqa: SLF001
            print("     ↳ [nudge] 本轮无工具调用，注入纠正指令重试一次")
            try:
                s2 = ag.run(NUDGE_MSG)
            except Exception as exc:  # noqa: BLE001
                s2 = {"status": "exception", "error": f"{type(exc).__name__}: {exc}", "model": args.model,
                      "steps_used": 0, "tool_calls": [], "final": ""}
            s["tool_calls"] = list(s.get("tool_calls", [])) + list(s2.get("tool_calls", []))
            s["final"] = s2.get("final") or s.get("final", "")
            s["status"] = s2.get("status", s["status"])
            s["places"] = s2.get("places", s.get("places", 0))
            s["nudged"] = True
        s["task"], s["turn"] = task, idx
        s["elapsed_sec"] = round(time.time() - t0, 2)
        calls = ", ".join(c["tool"] + ("✔" if c["ok"] else "✘") for c in s.get("tool_calls", [])) or "（无工具调用）"
        print(f"Agent：{s.get('final','')}\n     工具：{calls}\n     状态：{s['status']} · 标记 {s.get('places',0)} · 耗时 {s['elapsed_sec']}s")
        summaries.append(s)

    # 兜底渲染：若整场会话里模型一次都没成功渲染地图，则由驱动层用**模型已写入的标记**
    # 直接渲染一次，确保 demo 一定产出地图产物；标记内容仍全部来自模型，渲染是确定性的。
    render_calls = [c for s in summaries for c in s.get("tool_calls", [])
                    if c["tool"] == "render_map" and c["ok"]]
    map_path = ROOT / MAP_OUT_NAME
    fallback_render = False
    if not render_calls or not map_path.exists():
        fallback_render = True
        ag._log("fallback_render", reason="模型未调用 render_map，由驱动层按模型已写入的标记渲染",
                places=len(memory.load_places()))  # noqa: SLF001
        written = agentmod.render_map.render({"places": memory.load_places(), "title": MAP_TITLE},
                                             default_out=MAP_OUT_NAME)
        map_path = Path(written)
        if not map_path.is_absolute():
            map_path = ROOT / map_path

    total_places = memory.stats()["places"]
    ok = all(s["status"] in ("done", "max_steps") for s in summaries) and total_places > 0
    summary = {
        "model": args.model, "host": args.host, "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "turns": len(summaries), "places": total_places, "facts": memory.stats()["facts"],
        "events": memory.stats()["events"], "run_log": str(run_log),
        "map_file": str(map_path), "render_tool_calls": len(render_calls),
        "render_fallback": fallback_render,
        "results": summaries, "verdict": "GREEN" if ok else "RED",
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "session_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 结束：标记 {total_places} 个 · 语义记忆 {summary['facts']} 条 · 事件 {summary['events']} 条 · VERDICT {summary['verdict']} ===")
    print(f"    地图：{map_path}（模型渲染调用 {len(render_calls)} 次"
          f"{'，已走驱动层兜底渲染' if fallback_render else ''}）")
    print(f"    轨迹：{run_log}\n    摘要：{log_dir / 'session_summary.json'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
