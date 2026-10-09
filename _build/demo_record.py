#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C4D 录屏演示驱动：一条命令把挑战正文要求的四项必现信息打满屏。

挑战正文《📎 需要提交什么》要求「截图/录屏中必须清晰显示以下信息」：
  1. 运行的 Gemma 4 模型名称及版本
  2. 运行工具（如 Ollama v0.20.2）
  3. 设备信息（CPU/GPU、内存、操作系统）
  4. 模型实际运行中的推理速度（tok/s）

用法：
  python3 _build/demo_record.py               # 环境信息 + 推理测速 + 跑 Agent + 打开地图
  python3 _build/demo_record.py --no-agent    # 只打印环境信息 + 推理测速（约 5 秒）

只读探针 + 子进程编排，只用标准库。
注意：带 Agent 的完整模式会重写 logs/ 与 memory/（run_agent.py 的既有行为）；
仓库里归档的那次 GREEN 实跑记录不会被本脚本改写，只在本地重新跑一遍。
"""
import argparse
import json
import platform
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HOST = "http://127.0.0.1:11434"
MODEL = "gemma4:e4b"
SPEED_PROMPT = "用两句话介绍郑州西亚斯学院的所在地与办学定位。"
ROOT = Path(__file__).resolve().parent.parent


def line(ch="=", n=72):
    print(ch * n)


def title(text):
    line()
    print(text)
    line()


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"<err {e}>"


def post(path, payload, timeout=600):
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def show_model():
    title("【必现信息 1/4】本地运行的 Gemma 4 模型名称与版本")
    try:
        show = post("/api/show", {"model": MODEL}, timeout=60)
        det = show.get("details") or {}
        info = show.get("model_info") or {}
        ctx = info.get("gemma4.context_length") or info.get("llama.context_length")
        print(f"  模型名称    : {MODEL}")
        print(f"  家族 / 规格 : {det.get('family')} / {det.get('parameter_size')}")
        print(f"  量化级别    : {det.get('quantization_level')}（{det.get('format')}）")
        print(f"  上下文长度  : {ctx}")
        print(f"  能力标签    : {det.get('families') or show.get('capabilities')}")
        print(f"  模型摘要    : {det.get('parent_model') or MODEL}")
    except Exception as e:  # noqa: BLE001
        print(f"  <无法读取模型信息：{e}>")
    try:
        with urllib.request.urlopen(HOST + "/api/tags", timeout=20) as r:
            tags = json.loads(r.read().decode("utf-8"))
        for m in tags.get("models", []):
            if m.get("name") == MODEL:
                print(f"  本地摘要值  : {(m.get('digest') or '')[:12]}")
                print(f"  磁盘占用    : {m.get('size')} 字节（{(m.get('size') or 0) / 1e9:.2f} GB）")
    except Exception as e:  # noqa: BLE001
        print(f"  <无法读取 /api/tags：{e}>")
    print(f"  推理端点    : {HOST}（本机回环，仅本机可访问）")


def show_tool():
    title("【必现信息 2/4】运行工具")
    print(f"  ollama --version : {sh(['ollama', '--version']) or '<未找到 ollama>'}")
    print(f"  python           : {platform.python_version()}（{sys.executable}）")
    print(f"  node             : {sh(['node', '--version']) or '<未找到 node>'}")


def show_device():
    title("【必现信息 3/4】设备信息")
    mem = int(sh(["sysctl", "-n", "hw.memsize"]) or 0)
    print(f"  芯片 / CPU : {sh(['sysctl', '-n', 'machdep.cpu.brand_string']) or platform.processor()}")
    print(f"  内存       : {mem} 字节（{mem / 1e9:.1f} GB）")
    print(f"  操作系统   : macOS {sh(['sw_vers', '-productVersion'])}（Build {sh(['sw_vers', '-buildVersion'])}）")
    print(f"  架构       : {platform.machine()}")
    hw = sh(["system_profiler", "SPHardwareDataType"])
    for ln in hw.splitlines():
        s = ln.strip()
        if s.startswith(("Model Name", "Model Identifier", "Chip", "Total Number of Cores", "Memory")):
            print(f"  {s}")
    print("  GPU        : Apple 统一内存架构（Metal 加速，由 Ollama 自动调用）")


def show_speed():
    title("【必现信息 4/4】模型实际运行中的推理速度")
    payload = {
        "model": MODEL,
        "prompt": SPEED_PROMPT,
        "stream": False,
        "options": {"num_predict": 160, "temperature": 0},
    }
    print(f"  提示词：{SPEED_PROMPT}")
    t0 = time.time()
    gen = post("/api/generate", payload)
    wall = time.time() - t0
    ec = gen.get("eval_count") or 0
    ed = gen.get("eval_duration") or 0
    pc = gen.get("prompt_eval_count") or 0
    pd = gen.get("prompt_eval_duration") or 0
    print(f"  模型回答：{(gen.get('response') or '').strip()[:200]}")
    print()
    print(f"  生成速度 : {ec / (ed / 1e9):.2f} tok/s（生成 {ec} tokens）")
    print(f"  提示处理 : {pc / (pd / 1e9):.2f} tok/s（提示 {pc} tokens）")
    print(f"  本次耗时 : {wall:.2f} s（含模型加载）")
    print("  以上数字由本机 Ollama 的 eval_duration / eval_count 直接算出，非估算。")


def run_agent():
    title("跑一遍 Agent：一句话 → 多轮工具调用 → 可交互地图")
    cmd = [sys.executable, str(ROOT / "scripts" / "run_agent.py"), "--model", MODEL]
    print("  命令：" + " ".join(cmd))
    line("-")
    rc = subprocess.call(cmd, cwd=str(ROOT))
    line("-")
    print(f"  Agent 退出码：{rc}")
    return rc


def open_map():
    maps = sorted(ROOT.glob("Zhouruoying_C4D_*地图.html")) or sorted(ROOT.glob("Zhouruoying_C4D_map.html"))
    if not maps:
        print("  <未找到地图 HTML>")
        return
    target = maps[0]
    print(f"  打开地图：{target.name}（{target.stat().st_size} 字节，单文件内联，无需联网）")
    subprocess.call(["open", str(target)])


def main():
    ap = argparse.ArgumentParser(description="C4D 录屏演示驱动")
    ap.add_argument("--no-agent", action="store_true", help="跳过 Agent 实跑，只出环境与测速")
    ap.add_argument("--no-open", action="store_true", help="不自动打开地图")
    args = ap.parse_args()

    print()
    title("C4D 本地大模型地图 Agent —— 录屏演示（全程本机，不调用任何云端 API）")
    show_model()
    show_tool()
    show_device()
    show_speed()
    if not args.no_agent:
        rc = run_agent()
        if not args.no_open and rc == 0:
            open_map()
    line()
    print("演示结束。四项必现信息已全部打印在上方。")
    line()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
