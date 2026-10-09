# C4D｜本地大模型 Agent · 郑州足迹地图

用**本机**大模型（Ollama + Gemma 4）驱动的地图 Agent：自然语言 → 工具调用 → 交互式地图。
**不依赖任何云端 API**，坐标来自本地索引而非模型即兴生成。

- 提交身份：`2025105400318`（Zhouruoying）
- 挑战：**C4D**（`ch-20260717031455-uzqs9k`）
- 运行环境：MacBook Pro `Mac17,9` / Apple **M5 Pro** / 统一内存 **24 GB** / macOS 26.5
- 运行时：**Ollama 0.34.4**（`http://127.0.0.1:11434`，仅回环）

## 一、交付物清单

| 交付物 | 文件 |
| --- | --- |
| 方案设计 | `Zhouruoying_C4D_方案设计.md` |
| Agent 技能 | `Zhouruoying_C4D_agent-skill/`（打包版 `Zhouruoying_C4D_Agent技能.skill`） |
| 地图产物 | `Zhouruoying_C4D_map.html`（= `Zhouruoying_C4D_郑州足迹地图.html`） |
| 运行截图 | `Zhouruoying_C4D_output_screenshots/` |
| 验证报告 | `Zhouruoying_C4D_验证报告.md` |
| 教学说明 | `Zhouruoying_C4D_教学说明.md` |
| AI 日志 | `Zhouruoying_C4D_AI日志.md` |
| 拿来说明 | `Zhouruoying_C4D_拿来说明.md` |
| demo 运行记录 | `Zhouruoying_C4D_demo运行记录.md` |
| 项目自评 | `Zhouruoying_C4D_项目自评.md` |
| AAR 复盘 | `Zhouruoying_C4D_AAR.md` |

## 二、快速复现

```bash
python3 scripts/run_agent.py --offline-check          # 1. 环境体检 → rc=0
python3 scripts/selfcheck.py                          # 2. 结构自检 22/22 PASS
python3 scripts/run_agent.py --model gemma4:e4b       # 3. 端到端 demo → verdict=GREEN
python3 _build/png_stats.py Zhouruoying_C4D_output_screenshots/02_地图渲染结果.png
python3 _build/png_where.py Zhouruoying_C4D_output_screenshots/02_地图渲染结果.png
python3 _build/demo_record.py --no-agent              # 4. 录屏用：一条命令打印环境信息 + 实测 tok/s
python3 _build/demo_record.py                         # 5. 录屏用（完整体验）：环境 + 测速 + 跑 Agent + 打开地图
```

> **演示录屏**：挑战正文要求截图/录屏中清晰显示「模型名称版本 / 运行工具 / 设备信息 / 实测 tok/s」四项。
> `_build/demo_record.py` 把这四项按顺序打满一屏，配合 `scripts/run_agent.py` 再录一遍端到端过程即可。

## 三、目录结构

```
Zhouruoying_C4D_map-agent/
├── scripts/                  # 源码（零第三方依赖，仅标准库）
│   ├── agent.py              # Agent 主循环（系统提示 + 工具编排）
│   ├── tools.py              # 工具协议（get_place / add_place / update_place / remember_fact / render_map）
│   ├── gazetteer.py          # 本地地名索引（坐标唯一来源）
│   ├── memory.py             # 点位与语义记忆（仅追加事件流）
│   ├── render_map.py         # 渲染单文件 Leaflet HTML（按 hash 选底图源）
│   ├── run_agent.py          # 命令行入口 / demo 驱动 / 环境体检
│   └── selfcheck.py          # 22 项结构自检（含 6 项负向）
├── Zhouruoying_C4D_agent-skill/   # 技能包源码形态（SKILL.md + scripts/ + references/ + vendor/）
├── vendor/                   # 内联 Leaflet 1.9.4（不依赖 CDN）
├── memory/                   # places.json + places_events.jsonl
├── logs/                     # session_summary.json / probe_net.json / probe_speed.json / run_log.jsonl
├── _build/                   # 验证与取证脚本（status / probe / png_* / demo_record）
└── Zhouruoying_C4D_output_screenshots/   # 01 环境与模型信息 / 02 地图渲染结果
```

## 四、关键指标（实测）

| 指标 | 值 |
| --- | --- |
| 结构自检 | **22/22 PASS**，`VERDICT: GREEN`，`rc=0` |
| 端到端 demo | **`verdict=GREEN`**，`rc=0`，5 轮自然语言 |
| 数据落地 | `places=6` / `facts=1` / `events=19` |
| 渲染由模型发起 | `render_tool_calls=1`、`render_fallback=false` |
| 地图产物 | **170,272 B**，零外部 `<script>`/`<link>`，6 个标记 |
| 截图取证 | 0/20 房格为默认灰底；分类调色板命中 1,767 像素 |
| 吞吐 | **76.16 tok/s** 生成 / 312.92 tok/s 提示词处理 |

## 五、设计红线

**坐标绝不交给模型即兴生成。** 模型只负责「听懂人话 + 选工具」，地名→经纬度一律走本地 `gazetteer.py`。
好处：模型换版本、换提示词，点位也不会漂；且「查出来的坐标 = 写进去的坐标」可逐位核对。

详见 `Zhouruoying_C4D_方案设计.md` 与 `Zhouruoying_C4D_拿来说明.md`。
