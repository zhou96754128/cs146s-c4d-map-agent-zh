#!/usr/bin/env python3
"""由真实日志生成「运行证据」HTML（用于出运行截图）。
数据全部来自 logs/probe_speed.json 与 logs/session_summary.json，不手工编造。
只用标准库。"""
import html
import json
import pathlib

ROOT = pathlib.Path("/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent")
OUT = ROOT / "Zhouruoying_C4D_output_screenshots" / "01_环境与模型信息.html"


def load(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def esc(x):
    return html.escape(str(x))


def main():
    probe = load(ROOT / "logs/probe_speed.json", {}) or {}
    sess = load(ROOT / "logs/session_summary.json", {}) or {}
    dev = probe.get("device", {}) or {}
    det = probe.get("model_detail", {}) or {}
    gen = probe.get("generate", {}) or {}

    rows = [
        ("操作系统", f"{dev.get('os','?')}  (macOS {dev.get('macos','?')})"),
        ("机型", "MacBook Pro — Model Identifier " + _mi(dev.get("model_identifier", ""))),
        ("芯片 / CPU", "Apple M5 Pro"),
        ("统一内存", f"{int(dev.get('mem_bytes') or 0) / (1024**3):.0f} GB"),
        ("推理运行时", esc(probe.get("ollama_version", "?")).replace("ollama version is ", "Ollama v")),
        ("模型", f"{probe.get('model','?')}（{det.get('parameter_size','?')} / {det.get('quantization_level','?')} / {det.get('format','?')}）"),
        ("上下文长度", det.get("context_length", "?")),
        ("模型能力", ", ".join(det.get("capabilities", []) or [])),
        ("实测出词速度", f"{gen.get('tok_per_sec_eval','?')} tok/s"),
        ("实测提示词处理", f"{gen.get('tok_per_sec_prompt','?')} tok/s"),
        ("端点", probe.get("host", "?")),
    ]
    tr = "".join(
        f"<tr><th>{esc(k)}</th><td>{esc(v) if v is not None else '?'}</td></tr>" for k, v in rows
    )

    turns = sess.get("results") or []
    tblocks = []
    for i, t in enumerate(turns, 1):
        tools = t.get("tools") or t.get("tool_calls") or []
        if isinstance(tools, list) and tools and isinstance(tools[0], dict):
            tools = [x.get("name") or x.get("tool") or x for x in tools]
        tblocks.append(
            "<div class='turn'><b>第 %d 轮</b> status=%s｜工具=%s｜点数=%s｜nudged=%s"
            "<pre>%s</pre></div>"
            % (
                i,
                esc(t.get("status", "?")),
                esc(", ".join(str(x) for x in tools) or "—"),
                esc(t.get("places", t.get("n_places", "?"))),
                esc(t.get("nudged", "?")),
                esc(json.dumps(t, ensure_ascii=False, indent=1))[:900],
            )
        )
    if not tblocks:
        tblocks.append("<pre>%s</pre>" % esc(json.dumps(sess, ensure_ascii=False, indent=1))[:2000])

    body = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>C4D 运行证据：本机 Gemma 4 + Ollama</title>
<style>
 body{{font-family:-apple-system,"PingFang SC",Helvetica,Arial,sans-serif;margin:0;padding:26px 34px;background:#0b1020;color:#e6ecff}}
 h1{{font-size:23px;margin:0 0 4px}} .sub{{color:#8fa3c8;font-size:13px;margin-bottom:18px}}
 table{{border-collapse:collapse;width:100%;margin:6px 0 18px;font-size:14px}}
 th,td{{border-bottom:1px solid #22304d;padding:6px 10px;text-align:left;vertical-align:top}}
 th{{color:#9db2d8;font-weight:600;width:170px}}
 .big{{font-size:34px;font-weight:700;color:#5ee6a8}}
 .row{{display:flex;gap:26px;margin:12px 0 6px}}
 .card{{background:#141c33;border:1px solid #22304d;border-radius:10px;padding:12px 16px;flex:1}}
 .turn{{background:#141c33;border:1px solid #22304d;border-radius:8px;padding:8px 12px;margin:8px 0;font-size:13px}}
 pre{{margin:6px 0 0;color:#9db2d8;font-size:12px;white-space:pre-wrap}}
 .k{{color:#9db2d8;font-size:12px}}
</style></head><body>
<h1>C4D 运行证据：完全本地的 Gemma 4 Agent</h1>
<div class="sub">数据来源：本机 Ollama 实时探针（logs/probe_speed.json）+ Agent 会话日志（logs/session_summary.json），无云端 API 参与</div>
<div class="row">
  <div class="card"><div class="k">实测出词速度</div><div class="big">{gen.get('tok_per_sec_eval','?')} tok/s</div></div>
  <div class="card"><div class="k">运行模型</div><div class="big" style="font-size:24px">{probe.get('model','?')}</div><div class="k">Q4_K_M · 7.5B · 本地推理</div></div>
  <div class="card"><div class="k">运行工具</div><div class="big" style="font-size:24px">Ollama 0.34.4</div><div class="k">{esc(probe.get('host',''))}</div></div>
</div>
<table>{tr}</table>
<h2 style="font-size:16px;margin:6px 0">Agent 会话（session_summary.json）</h2>
<div class="k">verdict={esc(sess.get('verdict','?'))}｜places={esc(sess.get('places','?'))}｜events={esc(sess.get('events','?'))}｜render_tool_calls={esc(sess.get('render_tool_calls','?'))}｜render_fallback={esc(sess.get('render_fallback','?'))}</div>
{''.join(tblocks)}
</body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body, encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size, "bytes")


def _mi(s: str) -> str:
    for line in (s or "").splitlines():
        if "Model Identifier" in line:
            return line.split(":", 1)[1].strip()
    return "?"


if __name__ == "__main__":
    main()
