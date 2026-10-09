# C4D｜demo 运行记录（实测，非示意）

> 本文件记录的是**真机真跑**的结果，所有数字可在同目录 `logs/` 下复现。
> 运行者：Zhouruoying　｜　日期：2026-10-09

## 一、运行环境（截图见 `Zhouruoying_C4D_output_screenshots/01_环境与模型信息.png`）

| 项 | 值 |
| --- | --- |
| 机型 | MacBook Pro（Model Identifier **Mac17,9**） |
| 芯片 | **Apple M5 Pro** |
| 统一内存 | **24 GB** |
| 操作系统 | **macOS 26.5**（Build 25F71） |
| 推理运行时 | **Ollama 0.34.4**（`/usr/local/bin/ollama` → `/Applications/Ollama.app/Contents/Resources/ollama`） |
| 端点 | `http://127.0.0.1:11434`（仅回环，无外网调用） |
| 模型 | **`gemma4:e4b`**（GGUF / family `gemma4` / 7.5B / **Q4_K_M** / ctx 131072 / digest `dc35e8d9c606`） |
| 模型能力 | `completion, vision, audio, tools, thinking(默认开)` |
| 实测出词速度 | **76.16 tok/s**（`eval_count=160`，wall 4.86 s） |
| 实测提示词处理 | **312.92 tok/s** |

> 选 `gemma4:e4b` 而非 `qwen3:8b` 的原因：它是本次挑战点名要求的 Gemma 4 系列，且 24 GB 统一内存正好落在官方对照表「16GB → E4B」这一档；Q4_K_M 在保真度与内存之间取平衡。速度探针脚本：`_build/probe_speed.py`（只用标准库，输出 `logs/probe_speed.json`）。

## 二、运行命令与退出码

```bash
# ① 环境体检（不调用模型，验证索引/记忆/渲染三件套就绪）
python3 scripts/run_agent.py --offline-check
#   → 模型列表 ['gemma4:e4b','qwen3:8b']，rc=0

# ② 端到端多轮 demo（5 轮自然语言任务，模型自行决定调哪些工具）
python3 scripts/run_agent.py --model gemma4:e4b
#   → verdict=GREEN，rc=0，耗时 27.88 s（2026-10-09 14:04:48 → 14:05:16）

# ③ 自检（22 项断言，用假模型注入工具调用，不需要启动 Ollama）
python3 scripts/selfcheck.py
#   → 22/22 PASS，rc=0
```

## 三、逐轮真实证据（摘自 `logs/session_summary.json`）

模型：`gemma4:e4b`　｜　`turns=5, places=6, facts=1, events=19`　｜　`render_tool_calls=1, render_fallback=false`　｜　`verdict=GREEN`

| 轮 | 用户原话（节选） | 模型实际调用的工具（按发生顺序） | 结果 |
| --- | --- | --- | --- |
| 1 | 把「郑州西亚斯学院」和「黄帝故里景区」标到地图上，分别按校园和人文景点分类 | `get_place` → `get_place` → `add_place`×2（`steps_used=4`） | places=2，9.58 s |
| 2 | 再标出「郑州新郑国际机场」「郑州东站」「河南博物院」「二七广场」，分类依次是交通枢纽、交通枢纽、博物馆、商业地标 | `add_place_from_index`×4（一步并行，`steps_used=4`） | places=6，6.21 s |
| 3 | 河南博物院其实更适合归到人文景点，帮我把它的分类改过来 | `update_place`（`steps_used=1`） | places=6，3.36 s |
| 4 | 记住一句话：我周末常去的地方是郑州西亚斯学院、河南博物院和二七广场 | `remember_fact`（`steps_used=1`） | facts=1，2.43 s |
| 5 | 把地图渲染出来，标题用「我的郑州足迹（本地大模型 Agent 生成）」 | `render_map`（`steps_used=1`，**未被 nudge**） | places=6，6.90 s |

**这条证据链要说明的三件事**
1. **坐标不是模型编的**：第 1 轮模型先 `get_place` 查索引，拿到 34.527/113.745 与 34.396/113.741 后才 `add_place` 写入——写入的经纬度与本地索引**逐位一致**。
2. **第 2 轮走的是更优路径**：模型自行改用 `add_place_from_index`（一条调用完成「查+写」），说明它理解了工具描述里的推荐路径，而不是死记第 1 轮的写法。
3. **第 5 轮没有触发兜底**：`render_tool_calls=1, render_fallback=false`，说明「模型忘了渲染 → 循环内追加一次提醒再重试」的兜底路径**本次未被用到**（该路径的代码存在并有单测覆盖，但本轮的真实证据是「模型主动调用了 `render_map`」）。

## 四、产物

| 产物 | 说明 |
| --- | --- |
| `Zhouruoying_C4D_map.html` | 正式命名的交互式地图（**170,272 B**，**零外链**：Leaflet 1.9.4 内联自同包 `vendor/`），6 个可点击标记；支持 `#osm` / `#amap` / `#offline` 三种底图路由 |
| `Zhouruoying_C4D_郑州足迹地图.html` | 渲染器实际输出文件（与上一行**逐字节相同**，sha256 一致） |
| `Zhouruoying_C4D_output_screenshots/01_环境与模型信息.png` | 环境 + 模型 + tok/s 证据页截图 |
| `Zhouruoying_C4D_output_screenshots/02_地图渲染结果.png` | 地图页渲染截图（Edge headless，**605,226 B / 1500×1000 / sha256 前缀 `65c89a9277f78015`**）。像素取证（`_build/png_where.py`）：切 20 个房格，**0 格**是 Leaflet 默认灰底、**18 格**颜色丰富；分类调色板命中 **1,767 像素**（校园 262 / 交通枢纽 452 / 人文景点 449 / 商业地标 265）——瓦片与标记都真渲染了 |
| `logs/session_summary.json` / `logs/run_log.jsonl` | 逐轮结构化日志（本文件的数字来源） |
| `memory/places_events.jsonl` | **仅追加**的事件流，19 条，每条带模型名与时间戳；`memory/places.json` 由它重放生成 |

## 五、如实记录的偏差

- **底图策略：先探测、再选源，而不是写死一个源**。本机实测（`_build/probe_net.py` → `logs/probe_net.json`）：OSM 瓦片 `tile.openstreetmap.org` **超时不可达**，高德底图瓦片 `webst01.is.autonavi.com` **可达（10,493 B / 0.16 s）**。渲染器因此不是「写死 OSM + 祈祷」，而是 OSM 优先、**失败时自动回退到高德**——本机这条回退路径是**真实生效**的（截图里地图区域的瓦片底色 `#FCF9F2` 正是高德 style=7 的底色）。
- **支持用 URL hash 指定底图源**：`#osm` / `#amap` / `#offline`。做截图、录屏或在受限网络下复现时，可以钉死底图来源，避免「同一份产物在不同网络下看起来不一样」。
- **离线可用的部分是标记本身**：`#offline` 下不加载任何瓦片，标记、名称、分类、坐标与点击弹窗**照常渲染**，页面右下角 `#offlinenote` 会明示「底图未加载」，**不会白屏**。这是「地图库本地化（Leaflet 内联）+ 底图在线」的边界，如实记录。
- **截图过程中真翻过车，也真修好了**：最初用 `--screenshot` 抓图时 Edge **反复卡死、超时无产出**。排查后定位到根因——底图探测用的 `Image()` 因 OSM 瓦片连接超时而**永远不触发 `load`**，页面因此到不了 `load` 状态，无头截图就一直等。修法不是加大超时，而是**让探测本身不依赖会挂起的网络请求**（hash 路由 + 可达性预判），并给截图脚本加 90 s 硬超时与「PNG 字节 >1000 即视为成功」的判定，避免 Edge 不退出时拖死整条流水线。
- **截图走的是 headless 渲染**，非真人手动操作录屏；页面渲染完成信号为 `window.__mapAgentReady === true`，截图脚本等待该信号后落盘。
- 单轮耗时（2.4–9.6 s）为**该机型该模型**的实测值，换机器/换量化会变。
