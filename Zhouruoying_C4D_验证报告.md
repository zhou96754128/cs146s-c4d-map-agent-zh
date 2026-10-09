# C4D｜验证报告（本地大模型 Agent · 郑州足迹地图）

> 本报告的每一条结论都在本机**真跑**过，命令与退出码、产物字节与哈希、截图取证脚本都在仓库里，可逐条复核。
> 作者：Zhouruoying　｜　验证日期：2026-10-09

## 一、结论摘要

| 判据 | 结果 |
| --- | --- |
| 结构自检（22 项断言，含 6 项负向） | **22/22 PASS**，`VERDICT: GREEN`，`rc=0` |
| 端到端多轮 demo（`gemma4:e4b`，5 轮自然语言） | **`verdict=GREEN`**，`rc=0`，27.88 s |
| 数据落地 | `places=6` / `facts=1` / `events=19`（仅追加事件流） |
| 渲染是否真的由模型发起 | `render_tool_calls=1`、**`render_fallback=false`**（未走兜底提醒） |
| 产物是否可独立打开 | 地图 **170,272 B**，`FITBOUNDS`/`circleMarker`/`data-name` 齐备，**零外部脚本与链接标签** |
| 截图是否真渲染（不是白屏/灰底） | **0/20 房格**为 Leaflet 默认灰底，**18/20 房格**颜色丰富；分类调色板命中 **1,767 像素** |
| 是否依赖云端 API | **否**：模型跑在本机 `127.0.0.1:11434`，自检 P18/P19 断言失败即报错 |

## 二、验证环境

| 项 | 值 | 证据 |
| --- | --- | --- |
| 机器 | MacBook Pro `Mac17,9`，Apple **M5 Pro**，统一内存 **24 GB** | `Zhouruoying_C4D_output_screenshots/01_环境与模型信息.png` |
| 操作系统 | macOS **26.5**（Build 25F71） | 同上 |
| 推理运行时 | **Ollama 0.34.4**（`/usr/local/bin/ollama` → `/Applications/Ollama.app/Contents/Resources/ollama`） | `logs/probe_speed.json` |
| 端点 | `http://127.0.0.1:11434`（仅回环） | `logs/session_summary.json` |
| 模型 | **`gemma4:e4b`**，family `gemma4`，**7.5B**，**Q4_K_M**，ctx 131072，digest `dc35e8d9c606` | `logs/probe_speed.json` |
| 吞吐（实测） | **76.16 tok/s** 生成、**312.92 tok/s** 提示词处理（`eval_count=160`，wall 4.86 s） | `logs/probe_speed.json` |
| 工具链 | Python 3.12.13、Node v24.17.0；截图用 Microsoft Edge headless | `Zhouruoying_C4D_output_screenshots/err02.txt` |

**选型依据**：挑战点名的 Gemma 4 系列里，24 GB 统一内存正好落在官方对照表「16 GB → E4B」这一档；Q4_K_M 在保真度与内存占用之间取平衡。**未使用任何云端 API**——这正是「本地运行验证」这一维要证明的事。

## 三、六层验证矩阵

| 层 | 验的是什么 | 手段 | 结果 |
| --- | --- | --- | --- |
| L1 结构 | 索引/记忆/渲染/工具协议是否自洽 | `scripts/selfcheck.py` 22 项断言（含 6 项负向） | 22/22 PASS |
| L2 端到端 | 自然语言 → 工具调用 → 产物 是否全链路通 | `scripts/run_agent.py --model gemma4:e4b`（5 轮） | GREEN，rc=0 |
| L3 产物 | 地图文件是否自包含、标记是否齐全 | 字节/外部引用/关键 API 字符串扫描 | 170,272 B，零外链，6 标记 |
| L4 视觉取证 | 截图是真地图还是空白/灰底 | `_build/png_where.py` 房格分析 + `_build/png_stats.py` 调色板命中 | 瓦片与标记均已渲染 |
| L5 网络边界 | 底图源到底哪个可达 | `_build/probe_net.py` 7 个端点探测 | OSM 超时；高德可达（10,493 B / 0.16 s） |
| L6 负向 | 出错时会不会静默假装成功 | 6 项负向断言 + 截图失败重试全过程留痕 | 全部按预期报错 |

## 四、L1 结构自检（22 项）

```bash
python3 scripts/selfcheck.py        # → 22/22 PASS, SELFCHECK_RC=0
```

覆盖的关键断言（节选）：

- **P16 产物自包含**：地图为单文件、内联 Leaflet、无外部脚本/样式标签、标记数 = 写入的地点数；
- **P18 无外呼**：`OLLAMA_HOST=127.0.0.1:11434` 且代码内不含云端域名；
- **P19 零第三方依赖**：只用标准库；
- **P20 数据一致性**：`memory/places_events.jsonl` 重放后与 `memory/places.json` 一致；
- **P22 语义记忆读写**：写入后可被检索命中。

**6 项负向断言**（故意喂坏输入，断言必须报错）覆盖：缺字段的工具调用、非法经纬度、越界类别、损坏的记忆文件、不存在的模型名、渲染路径不可写。

## 五、L2 端到端多轮 demo（逐轮证据）

```bash
python3 scripts/run_agent.py --offline-check    # 环境体检 → rc=0
python3 scripts/run_agent.py --model gemma4:e4b # 5 轮 demo → verdict=GREEN, rc=0
```

| 轮 | 用户原话（节选） | 模型实际调用（按发生顺序） | 结果 |
| --- | --- | --- | --- |
| 1 | 标出「郑州西亚斯学院」「黄帝故里景区」，按校园/人文景点分类 | `get_place` ×2 → `add_place` ×2 | places=2，9.58 s |
| 2 | 再标出机场、郑州东站、河南博物院、二七广场 | `add_place_from_index` ×4（并行） | places=6，6.21 s |
| 3 | 河南博物院改归人文景点 | `update_place` | places=6，3.36 s |
| 4 | 记住「周末常去西亚斯、河南博物院、二七广场」 | `remember_fact` | facts=1，2.43 s |
| 5 | 渲染地图，标题「我的郑州足迹」 | `render_map`（**未被兜底提醒**） | places=6，6.90 s |

**三个关键点**
1. **坐标不是模型编的**：第 1 轮先 `get_place` 查出 34.527/113.745 与 34.396/113.741，再 `add_place` 写入，与本地索引**逐位一致**。
2. **模型自己换了更优路径**：第 2 轮改用一个 `add_place_from_index` 完成「查+写」，说明它读懂了工具描述里的推荐用法，而不是照抄第 1 轮。
3. **兜底没被用到**：`render_tool_calls=1`、`render_fallback=false`——「模型忘了渲染就补一次提醒」的代码存在且有单测覆盖，但本轮真实证据是**模型主动调用了 `render_map`**。

## 六、L3 产物自包含 + L4 截图取证

```bash
python3 scripts/selfcheck.py                                  # 22/22 PASS
python3 _build/png_stats.py  Zhouruoying_C4D_output_screenshots/02_地图渲染结果.png
python3 _build/png_where.py  Zhouruoying_C4D_output_screenshots/02_地图渲染结果.png
```

- **产物**：`Zhouruoying_C4D_郑州足迹地图.html` = **170,272 B**，与 `Zhouruoying_C4D_map.html` **逐字节相同**；外部 `<script>`/`<link>` 标签数 = **0**，`unpkg` 出现 0 次（Leaflet 1.9.4 内联自同包 `vendor/`）。
- **截图**：`02_地图渲染结果.png` = **605,226 B / 1500×1000**，sha256 前缀 `65c89a9277f78015`。
- **取证结论**：切 5×4 共 20 个房格，**0 格**出现 Leaflet 默认灰底 `#DDDDDD` 占满（若瓦片没加载，格子会被灰底刷满）；**18/20 格**唯一色数 > 300（最高 626），地图区域主导色是 `#FCF9F2`——**高德 style=7 瓦片的底色**。分类调色板命中 **1,767 像素**（校园 262 / 交通枢纽 452 / 人文景点 449 / 商业地标 265），与写入的 6 个点位、4 个分类吻合。
- 说明：`png_stats.py` 自带的「唯一色数 > 3000」丰富度阈值对**灰白底图**会给出「极单调」的提示，1963 未过线属于**阈值误报**；判定以房格分析 + 调色板命中为准（两项均独立指向"已渲染"）。

## 七、L5 底图可达性与真实回退

```bash
python3 _build/probe_net.py     # → logs/probe_net.json
```

| 端点 | 结果 |
| --- | --- |
| OSM 瓦片 `tile.openstreetmap.org` | **超时不可达** |
| `unpkg.com`（CDN 资产） | 不可达（TLS 握手超时）→ 故 Leaflet **已内置到 `vendor/`**，不再依赖 CDN |
| 高德底图瓦片 `webst01.is.autonavi.com` | **可达：10,493 B / 0.16 s** |
| 高德备用 `webrd01.is.autonavi.com` | 可达：179 B / 0.15 s |
| 天地图 WMTS | HTTP 418 |
| Carto 底图 | 超时 |
| GitHub（对照组） | 可达：16,739 B / 0.49 s |

**这不是论文式的假设，是修出来的**：最初截图脚本反复超时无产出，根因是底图探测的 `Image()` 因 OSM 连接超时而永不触发 `load`，页面到不了 `load` 状态。修法是让渲染器**按 URL hash 选源**（`#osm` / `#amap` / `#offline`）并做可达性预判，截图脚本另加 90 s 硬超时 + 「PNG 字节 > 1000 即成功」判定。本机截图走 `#amap`，走的正是**真实回退分支**。

## 八、L6 负向验证（会不会假装成功）

| 负向场景 | 预期 | 实测 |
| --- | --- | --- |
| 工具调用缺必填字段 | 拒绝并给出可读错误 | ✅ 断言报错 |
| 非法经纬度（越界） | 拒绝 | ✅ |
| 不存在的分类 | 拒绝 | ✅ |
| `memory/*.jsonl` 损坏 | 不静默吞掉 | ✅ |
| 不存在的模型名 | 明确失败 | ✅ |
| 渲染输出路径不可写 | 明确失败 | ✅ |
| 底图瓦片不可达 | **不白屏**：标记照常渲染 + 右下角 `#offlinenote` 提示 | ✅ 见截图与 `#offline` 路由 |

## 九、评审维度对照

| 挑战资料 `rubric.json` 维度（权重） | 证据指针 |
| --- | --- |
| agentCapability（25） | 五、逐轮工具调用链；`logs/session_summary.json` |
| technicalExecution（20） | 四、22 项断言；七、探针与回退；六、零外链产物 |
| artifactCompleteness（15） | 本仓库交付物清单与 README |
| aiUsage（20） | `Zhouruoying_C4D_AI日志.md`（含翻车与修法） |
| reflectionQuality（20） | `Zhouruoying_C4D_AAR.md` |

> 平台评测口径另按「本地运行验证 25% / Agent 能力展示 25% / 地图质量 20% / 完成级别 15% / 可复用性 15%」描述，两套口径的维度命名不同、指向同一批证据：本地运行验证 = 二/四/五，Agent 能力展示 = 五，地图质量 = 六，完成级别与可复用性 = `教学说明.md` + `SKILL.md`。

## 十、复现步骤（从零到出图）

```bash
python3 scripts/run_agent.py --offline-check          # 1. 体检
python3 scripts/selfcheck.py                          # 2. 22 项自检
python3 scripts/run_agent.py --model gemma4:e4b       # 3. 端到端 demo（写记忆 + 出地图）
python3 _build/png_stats.py Zhouruoying_C4D_output_screenshots/02_地图渲染结果.png   # 4a. 像素取证
python3 _build/png_where.py Zhouruoying_C4D_output_screenshots/02_地图渲染结果.png   # 4b. 房格判定
```

## 十一、未被验证 / 明确限制（如实声明）

1. **无真人操作录屏**：截图由 Edge headless 生成，脚本等待 `window.__mapAgentReady === true` 后落盘；`err01.txt` / `err02.txt` 保留了失败尝试的原始错误，未删除。
2. **未做「未审查变体」对比**：挑战把「对比 Gemma 4 与去审查变体」列为**加分项**，本次未做（本机未安装相应变体），因此不在本报告中主张。
3. **速度数字有机器依赖性**：76.16 tok/s 是 **M5 Pro / 24 GB / Q4_K_M** 的实测值，换机换量化会变。
4. **单次运行**：本报告给出的是**一次完整端到端运行**的实录，未做多种子重复性统计（生成式 Agent 的输出不保证逐字复现；可复现的是**流程与校验**，不是模型的每一句话）。
5. **兜底路径的真实证据是「未被触发」**：该分支有单测覆盖，但本次运行的证据只能说明"模型没忘"。

