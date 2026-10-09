#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线自检：用确定性用例证明关键约束，不联网、不调用大模型。

正向用例（P）证明能力可用；负向用例（N）证明约束真的会拦住错误行为——
尤其是「标记必须由模型发起工具调用才出现」，这是本挑战的核心命题。

用法：python3 scripts/selfcheck.py    # 退出码 0 = 全绿
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import agent as agentmod  # noqa: E402
import gazetteer  # noqa: E402
import memory as memmod  # noqa: E402
import render_map  # noqa: E402
import tools as toolmod  # noqa: E402

CLOUD_HOSTS = ["api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com",
               "dashscope.aliyuncs.com", "open.bigmodel.cn", "api.deepseek.com"]
PLACEHOLDERS = ["✍️", "TODO", "TBD", "FIXME", "待补", "待填", "lorem ipsum"]
STDLIB = {"json", "time", "pathlib", "typing", "math", "collections", "sys", "os",
          "argparse", "random", "datetime", "re", "tempfile", "shutil", "unicodedata",
          "html", "itertools", "functools", "csv", "statistics", "urllib", "hashlib",
          "textwrap", "dataclasses", "copy", "string", "io", "__future__"}
LOCAL_MODULES = {"agent", "tools", "memory", "render_map", "gazetteer", "selfcheck", "run_agent"}

R: list[tuple[str, bool, str]] = []


def check(cid: str, ok: bool, detail: str = "") -> bool:
    R.append((cid, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {cid}  {detail}")
    return bool(ok)


class FakeClient:
    """假模型：按脚本回放 tool_calls，用于离线验证 Agent 循环（不发网络请求）。"""

    # 签名与 OllamaClient 保持一致，这样才能顶替它在 MapAgent 里被构造
    def __init__(self, model="fake", host="", timeout=1, temperature=0.2, num_ctx=8192,
                 think=None, script=None) -> None:
        self.model, self.host, self.think = model, host, think
        self.script, self.i = list(script or []), 0

    def chat(self, messages, tool_specs):  # noqa: ANN001
        msg = self.script[self.i] if self.i < len(self.script) else {"content": "（结束）", "tool_calls": []}
        self.i += 1
        return {"message": msg, "eval_count": 1, "done_reason": "stop"}

    def tags(self):
        return {"models": []}


def call(tool_name: str, **args) -> dict:
    """构造一条「模型请求调用工具」的助手消息（模拟 Ollama /api/chat 的返回形态）。"""
    return {"content": "", "tool_calls": [
        {"id": f"c_{tool_name}", "type": "function",
         "function": {"name": tool_name, "arguments": args}}]}


def fake_agent(tmp: Path, script: list[dict]):
    real = agentmod.OllamaClient
    agentmod.OllamaClient = FakeClient
    try:
        mem = memmod.Memory(tmp / "memory")
        ag = agentmod.MapAgent(model="fake", memory=mem, run_log=tmp / "logs" / "run_log.jsonl")
    finally:
        agentmod.OllamaClient = real
    ag.client = FakeClient(script=script)
    return ag, mem


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="c4d_selfcheck_"))

    # ---- P01~P04 地名索引（技能的可信底座）----
    rows = gazetteer.PLACES
    check("P01 索引条目与字段完整", len(rows) >= 12 and all(
        {"name", "lat", "lon", "category", "city"} <= set(r) for r in rows), f"共 {len(rows)} 条")
    sias = gazetteer.lookup("郑州西亚斯学院")
    ok = bool(sias) and 34.3 < sias["lat"] < 34.9 and 113.4 < sias["lon"] < 114.2
    check("P02 郑州西亚斯学院命中且坐标在郑州范围内", ok,
          f"{sias['name']} {sias['lat']},{sias['lon']} @{sias['city']}" if sias else "未命中")
    en = gazetteer.lookup("SIAS University")
    check("P03 英文别名与中文名解析到同一点", bool(en) and bool(sias) and en["lat"] == sias["lat"],
          f"SIAS University -> {en['lat']},{en['lon']}" if en else "别名未命中")
    hits = gazetteer.search("博物馆")
    check("P04 关键词模糊检索可用", len(hits) >= 1, f"命中 {len(hits)} 条")

    # ---- P05~P06 工具注册表自洽 ----
    names = toolmod.tool_names()
    rt = toolmod.ToolRuntime(memory=memmod.Memory(tmp / "t1"), model="fake")
    missing = [n for n in names if getattr(rt, f"t_{n}", None) is None]
    check("P05 每个工具声明都有对应实现", not missing, f"{len(names)} 个工具，缺失 {missing}")
    shape_ok = all(t.get("type") == "function" and isinstance(t["function"].get("parameters", {}).get("required"), list)
                   and t["function"].get("description") for t in toolmod.TOOL_SPECS)
    check("P06 工具 Schema 结构合法（含 description/required）", shape_ok, f"{len(names)} 个 Schema")

    # ---- N07~N08 核心负向：不调用工具就没有标记 ----
    empty = memmod.Memory(tmp / "t2")
    html0 = render_map.render({"places": empty.load_places(), "title": "空态"}, out_path=str(tmp / "empty.html"))
    blank = Path(html0).read_text(encoding="utf-8")
    check("N07 空记忆渲染出 0 个标记",
          empty.load_places() == [] and 'data-name="' not in blank and "暂无标记" in blank,
          f"{Path(html0).name}，文件 {Path(html0).stat().st_size} B，列表项 0")
    ag0, mem0 = fake_agent(tmp / "n8", [{"content": "好的，我不会替你补点。", "tool_calls": []}])
    s0 = ag0.run("帮我把郑州的景点都标上（我故意不说具体名字）")
    check("N08 模型不发起调用时地图为空", s0["places"] == 0 and s0["status"] == "done",
          f"status={s0['status']} places={s0['places']}")

    # ---- N09~N12 负向：错误输入必须被明确拦住 ----
    r = rt.t_add_place_from_index("不存在的地名XYZ")
    check("N09 索引外的地名被拒", r.get("ok") is False and r.get("error") == "NOT_IN_INDEX", json.dumps(r, ensure_ascii=False)[:80])
    r = rt.dispatch("no_such_tool", {"x": 1})
    check("N10 未知工具返回 UNKNOWN_TOOL", r.get("ok") is False and r.get("error") == "UNKNOWN_TOOL", r.get("error", ""))
    r = rt.dispatch("add_place", {"name": "只有名字"})
    check("N11 缺必填参数返回 BAD_ARGUMENTS", r.get("ok") is False and r.get("error") == "BAD_ARGUMENTS", r.get("error", ""))
    bad = toolmod.ToolRuntime(memory=memmod.Memory(tmp / "t3"), model="fake",
                              renderer=lambda p: (_ for _ in ()).throw(RuntimeError("渲染器故障")))
    r = bad.dispatch("render_map", {})
    check("N12 工具内部异常回流为 TOOL_EXCEPTION（不崩循环）",
          r.get("ok") is False and r.get("error") == "TOOL_EXCEPTION", r.get("detail", "")[:60])

    # ---- P13~P15 记忆：追加式、可移除、可跨会话 ----
    m = memmod.Memory(tmp / "t4")
    before = m.stats()["events"]
    m.add_place("测试点A", 34.5, 113.5, "校园", model="fake")
    m.add_place("测试点B", 34.6, 113.6, "博物馆", model="fake")
    m.remove_place("测试点B", model="fake")
    check("P13 标记增删正确（2 加 1 删 = 1 条）", len(m.load_places()) == 1, f"剩余 {len(m.load_places())} 条")
    check("P14 事件日志只追加、删除仍留痕（可审计）", m.stats()["events"] == before + 3,
          f"事件 {before} -> {m.stats()['events']}")
    m2 = memmod.Memory(tmp / "t4")
    check("P15 记忆跨实例持久化", [p["name"] for p in m2.load_places()] == ["测试点A"],
          str([p["name"] for p in m2.load_places()]))

    # ---- P16~P17 渲染产物 ----
    places = [{"name": "郑州西亚斯学院", "lat": 34.527, "lon": 113.745, "category": "校园", "note": ""},
              {"name": "河南博物院", "lat": 34.7901, "lon": 113.6629, "category": "博物馆", "note": ""}]
    out = render_map.render({"places": places, "title": "自检地图", "center_lat": 34.6, "center_lon": 113.7},
                            out_path=str(tmp / "m.html"))
    doc = Path(out).read_text(encoding="utf-8")
    # 交互能力来自**内联**的 Leaflet 本体（_leaflet_id / leaflet-pane 是库内部标识），
    # 而不是某个 CDN 域名；并且要求产物不含外链 script/link，即真正的自包含单文件。
    inter = all(k in doc for k in ("_leaflet_id", "leaflet-pane", "fitBounds",
                                   "L.circleMarker(", 'data-name="', "L.tileLayer("))
    selfcontained = re.search(r'<(?:script|link)[^>]*(?:src|href)\s*=\s*[^>]{0,2}https?://', doc) is None
    named = all(p["name"] in doc and p["category"] in doc for p in places)
    markers = doc.count('data-name="') == len(places)
    check("P16 地图自包含且含交互能力与全部标记", inter and selfcontained and named and markers,
          f"{Path(out).stat().st_size} B，内联库={inter}，无外链={selfcontained}，标记数={markers}")
    low = doc.lower()
    bad_tok = [t for t in PLACEHOLDERS if t.lower() in low]
    check("P17 渲染产物无占位符", not bad_tok, str(bad_tok))

    # ---- P18~P19 离线与零依赖约束 ----
    src = {p.name: p.read_text(encoding="utf-8") for p in sorted(SCRIPTS.glob("*.py"))}
    runtime_src = {k: v for k, v in src.items() if k != "selfcheck.py"}  # 自检自身含对照词表，不参与扫描
    hits = [h for h in CLOUD_HOSTS if any(h in t for t in runtime_src.values())]
    check("P18 只连本机端点、无云端域名", "http://127.0.0.1:11434" in src["agent.py"] and not hits,
          f"OLLAMA_HOST=127.0.0.1:11434，云端域名 {hits or '无'}")
    imports: set[str] = set()
    for text in src.values():
        for line in text.splitlines():
            mm = re.match(r"\s*(?:from|import)\s+([A-Za-z_][\w.]*)", line)
            if mm:
                imports.add(mm.group(1).split(".")[0])
    alien = sorted(i for i in imports if i not in STDLIB and i not in LOCAL_MODULES)
    check("P19 仅使用标准库与本地模块", not alien, f"外部依赖 {alien or '无'}")

    # ---- P20~P22 Agent 循环端到端（假模型，确定性）----
    ag1, mem1 = fake_agent(tmp / "p20", [
        call("add_place_from_index", name="郑州西亚斯学院", category="校园"),
        call("add_place_from_index", name="河南博物院", category="博物馆"),
        call("render_map", out_path=str(tmp / "p20" / "map.html"), title="自检"),
        {"content": "已把两个地点标好并渲染地图。", "tool_calls": []},
    ])
    s1 = ag1.run("标出郑州西亚斯学院和河南博物院，然后渲染地图")
    doc1 = (tmp / "p20" / "map.html").read_text(encoding="utf-8")
    check("P20 模型调用驱动标记落盘并成图",
          s1["places"] == 2 and doc1.count('data-name="') == 2
          and all(n in doc1 for n in ("郑州西亚斯学院", "河南博物院")) and s1["final"].startswith("已把"),
          f"places={s1['places']} 列表项={doc1.count('data-name=') } status={s1['status']}")
    ag2, _ = fake_agent(tmp / "p21", [call("no_such_tool", x=1), {"content": "工具不可用，我换个方式。", "tool_calls": []}])
    s2 = ag2.run("用不存在的工具做事")
    check("P21 工具报错后循环继续而非崩溃", s2["status"] == "done" and s2["tool_calls"][0]["ok"] is False,
          f"status={s2['status']} first_ok={s2['tool_calls'][0]['ok']}")
    ag3, mem3 = fake_agent(tmp / "p22", [
        call("remember_fact", text="用户周末常去郑州西亚斯学院"),
        {"content": "记住了。", "tool_calls": []},
    ])
    s3 = ag3.run("记住我周末常去郑州西亚斯学院")
    check("P22 语义记忆可写入并读回", s3["facts"] == 1 and "西亚斯" in mem3.facts()[0],
          str(mem3.facts())[:60])

    # ---- 汇总 ----
    total = len(R)
    passed = sum(1 for _, ok, _ in R if ok)
    neg = sum(1 for cid, _, _ in R if cid.startswith("N"))
    print("-" * 62)
    print(f"自检结果：{passed}/{total} PASS（其中负向用例 {neg} 条）")
    print("VERDICT: " + ("GREEN" if passed == total else "RED"))
    for cid, ok, _ in R:
        if not ok:
            print(f"  !! 未通过 {cid}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
