---
name: map-agent
description: 一个完全跑在本机的本地大模型 Agent 技能：用自然语言提出「把某些地方标到地图上」，本机 Ollama 上运行的大模型自主选择工具、调用地理索引取坐标、写入可重放的记忆层，最后渲染出一个可离线打开、可点击的交互式 Leaflet 地图 HTML。全程不调用任何云端 API，坐标来自本地索引而非模型编造，模型只会「决定调哪个工具、传什么参数」，不会自己写经纬度。
---

# map-agent —— 本地大模型驱动的交互式地图 Agent

> 一句话：**模型负责决策，索引负责坐标，记忆层负责可复现。**

## 1. 它在做什么

用户用一句中文说出需求，Agent 自己拆解成工具调用，最后产出一个能打开的地图文件：

```
自然语言任务
    │
    ▼
┌──────────────────────────────────────────┐
│  Agent 主循环（scripts/agent.py）         │
│  ① 把 12 个工具的描述 + 对话历史发给本机模型 │
│  ② 模型返回 tool_calls（结构化 JSON）      │
│  ③ 本地执行工具，把结果回灌给模型           │
│  ④ 模型不再调用工具 → 输出最终答复          │
└──────────────────────────────────────────┘
    │            │                │
    ▼            ▼                ▼
 地理索引      记忆层           渲染器
gazetteer   memory.py       render_map.py
（坐标来源）  （可重放）       （Leaflet HTML）
```

**为什么不让模型直接写经纬度**：模型对坐标的记忆是不可靠的——它给出的数字看起来合理，但可能落在几百公里外，而使用者无法察觉。本技能把「查坐标」这件事从模型手里拿走，交给一个可审计的本地索引；模型只剩下它真正擅长的部分：**理解意图、选择工具、组织参数**。

## 2. 安装与依赖

```bash
# 本技能只用 Python 标准库，无需 pip install 任何包。
python3 --version          # 需要 3.10+

# 唯一的运行时依赖：本机 Ollama（免费、离线）
#   https://ollama.com/
ollama --version           # 本工程实测于 ollama 0.34.4

# 拉取一个支持 function calling 的本地模型
ollama pull qwen3:8b
# 或挑战指定的 Gemma 4 系列（约 5 GB，首次拉取较慢）
ollama pull gemma4:e4b

# 确认服务在跑
curl -s http://127.0.0.1:11434/api/tags | head -c 200
```

不需要 API key，不需要联网（模型拉取完成后），不需要 GPU 服务器。

## 3. 使用

```bash
# 单轮任务（默认模型 qwen3:8b）
python3 scripts/run_agent.py --task "把郑州西亚斯学院和河南博物院标到地图上，然后渲染地图"

# 指定模型 / 多轮对话 / 换端点
python3 scripts/run_agent.py --model gemma4:e4b \
    --task "把郑州西亚斯学院标到地图上" \
    --task "再把河南博物院加上，然后渲染地图"

# 环境体检（不调用模型，检查索引/记忆/渲染三件套是否就绪）
python3 scripts/run_agent.py --offline-check

# 清空记忆层，从零开始复现
python3 scripts/run_agent.py --reset --task "..."
```

**退出码**（可直接用于调度判断）：

| 退出码 | 含义 |
| --- | --- |
| 0 | 任务完成（`status=done`） |
| 3 | 模型端点不可达（Ollama 没启动） |
| 4 | 达到最大步数仍未收敛 |
| 1 | 参数错误 / 未预期的内部异常 |

## 4. 工具清单（12 个）

工具的定义、参数校验与错误码都在 `scripts/tools.py` 里，模型只能看到名字、描述和参数 schema。

| 工具 | 作用 |
| --- | --- |
| `get_place` | 按名称在本地地理索引里精确/别名查找坐标 |
| `search_places` | 按关键词模糊搜索索引 |
| `add_place` | 手工加一个点（显式给坐标，用于索引里没有的地方） |
| `add_place_from_index` | 从索引取坐标并加一个点（**推荐路径**） |
| `update_place` | 修改已有点的类别/备注 |
| `remove_place` | 删除一个点 |
| `list_places` | 列出当前所有点 |
| `count_places` | 只要数量（给模型省 token） |
| `remember_fact` | 写入一条语义记忆（自由文本事实） |
| `recall_facts` | 按关键词召回语义记忆 |
| `render_map` | 把当前点渲染成 Leaflet HTML |
| `print_state` | 打印当前状态（调试用） |

工具层有三类结构化错误：`UNKNOWN_TOOL`、`BAD_ARGUMENTS`、`TOOL_EXCEPTION`，另加索引未命中时的 `NOT_IN_INDEX`。**错误以文本形式回灌给模型**，所以模型看到「查不到」时会改走 `search_places` 或如实报告，而不是编一个坐标。

## 5. 记忆层（可重放）

`memory/` 下三个文件：

- `places_events.jsonl` —— **仅追加**的事件流，每一条都带模型名与时间戳（真相来源）
- `places.json` —— 由事件流重放生成的当前快照（可随时删除重建）
- `session.jsonl` —— 逐轮的对话轨迹

因为坐标的写入历史是 append-only 的，任何一次渲染结果都可以事后审计：**这个点是谁、在哪一步、用什么参数加进去的**。

## 6. 渲染产物

`render_map` 生成单文件 HTML，包含：

- 每个点一个 `circleMarker`，带 `data-name` 便于外部脚本断言
- `fitBounds` 自动框住所有点；只有一个点时退回 `setView` + `openPopup`
- 渲染完成后在 `window` 上置 `__mapAgentReady = true`（供截图/自动化等待）
- 无点时用默认中心（郑州西亚斯学院附近）兜底，不会产出空白页

**Leaflet 资产的取用顺序**（`scripts/render_map.py::_leaflet_tags`）：

1. **优先内联**同包 `vendor/leaflet.css` + `vendor/leaflet.js`（Leaflet 1.9.4，随包分发）→ 产物**零外链**，断网也能打开；
2. 同包 `vendor/` 缺失时，回退到 `https://unpkg.com/leaflet@1.9.4/dist/` 的 CDN 引用。

> 已知边界：**底图瓦片**（OpenStreetMap 在线瓦片）仍需要联网；离线打开时标记、名称、分类与坐标照常可见与可点击，页面右下角的 `#offlinenote` 会提示这一点，不会白屏。

## 7. 自检

```bash
python3 scripts/selfcheck.py
# 22 项断言：6 条负向（无索引命中 / 坏参数 / 未知工具 / 无点渲染 / 记忆重放 / 幂等）
```

自检全部使用**假模型**（`FakeClient`）注入预设的工具调用脚本，所以它验证的是 Agent 的编排、工具层与记忆层，**不需要真的启动 Ollama**，可在任何机器上复跑。

## 8. 局限（如实记录）

- 地理索引只有 **12 条**，聚焦郑州/河南；索引外的地方必须由使用者显式给坐标（走 `add_place`），本技能**不会**猜。
- 坐标精度为**校园/场馆级**（小数点后 3 位），不用于导航。
- 未做工具返回结果的自动纠错重试：模型一次调用失败后依赖自己下一轮改参。
- 小参数量模型（≤8B）在 3 个以上并行工具调用时偶发顺序错乱，建议一次只给一个地点。
