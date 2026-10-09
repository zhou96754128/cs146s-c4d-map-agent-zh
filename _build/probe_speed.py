#!/usr/bin/env python3
"""本机推理速度探针：直连本机 ollama /api/generate，读取真实 eval 计数与耗时。
只用标准库，无第三方依赖。输出 JSON 到 stdout 并可落盘。"""
import json
import platform
import subprocess
import sys
import time
import urllib.request

HOST = "http://127.0.0.1:11434"
MODEL = "gemma4:e4b"
PROMPT = "用两句话介绍郑州西亚斯学院的所在地与办学定位。"


def ollama_get(path):
    with urllib.request.urlopen(HOST + path, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"<err {e}>"


def main():
    out = {"host": HOST, "model": MODEL}
    out["ollama_version"] = sh(["ollama", "--version"])
    tags = ollama_get("/api/tags")
    out["models"] = [
        {
            "name": m.get("name"),
            "digest": (m.get("digest") or "")[:12],
            "size_bytes": m.get("size"),
            "quantization_level": (m.get("details") or {}).get("quantization_level"),
            "parameter_size": (m.get("details") or {}).get("parameter_size"),
            "family": (m.get("details") or {}).get("family"),
        }
        for m in tags.get("models", [])
    ]
    show = ollama_get("/api/show?model=" + MODEL) if False else None
    try:
        req = urllib.request.Request(
            HOST + "/api/show",
            data=json.dumps({"model": MODEL}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            show = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        out["show_error"] = str(e)
    if show:
        det = show.get("details") or {}
        out["model_detail"] = {
            "format": det.get("format"),
            "family": det.get("family"),
            "parameter_size": det.get("parameter_size"),
            "quantization_level": det.get("quantization_level"),
            "context_length": (show.get("model_info") or {}).get("gemma4.context_length")
            or (show.get("model_info") or {}).get("llama.context_length"),
            "capabilities": show.get("capabilities"),
        }

    out["device"] = {
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu": platform.processor() or sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "chip": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "mem_bytes": int(sh(["sysctl", "-n", "hw.memsize"]) or 0),
        "macos": sh(["sw_vers", "-productVersion"]),
        "model_identifier": sh(["system_profiler", "SPHardwareDataType"]),
    }

    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "stream": False,
        "options": {"num_predict": 160, "temperature": 0},
    }
    t0 = time.time()
    req = urllib.request.Request(
        HOST + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        gen = json.loads(r.read().decode("utf-8"))
    wall = time.time() - t0

    ec = gen.get("eval_count") or 0
    ed = gen.get("eval_duration") or 0
    pc = gen.get("prompt_eval_count") or 0
    pd = gen.get("prompt_eval_duration") or 0
    out["generate"] = {
        "prompt": PROMPT,
        "response": gen.get("response", "")[:400],
        "eval_count": ec,
        "eval_duration_ns": ed,
        "prompt_eval_count": pc,
        "prompt_eval_duration_ns": pd,
        "load_duration_ns": gen.get("load_duration"),
        "total_duration_ns": gen.get("total_duration"),
        "wall_sec": round(wall, 2),
        "tok_per_sec_eval": round(ec / (ed / 1e9), 2) if ed else None,
        "tok_per_sec_prompt": round(pc / (pd / 1e9), 2) if pd else None,
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
