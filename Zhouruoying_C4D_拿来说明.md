# C4D｜拿来说明（怎么把这套东西用起来）

> 作者：Zhouruoying　｜　日期：2026-10-09
> 一句话：这是一个**完全跑在本机**的地图 Agent——你用中文说要标哪些地方，它自己调工具把地点查出来、写进记忆、渲染成一张可交互的地图。**全程不调用任何云端 API。**

## 一、你拿到的是四类东西

| 类别 | 文件 | 用途 |
| --- | --- | --- |
| **成品地图** | `Zhouruoying_C4D_map.html`（= `Zhouruoying_C4D_郑州足迹地图.html`，170,272 B） | **双击就能看**，单文件、含内联 Leaflet，不联网也能显示点位 |
| **技能包** | `Zhouruoying_C4D_Agent技能.skill`（ZIP，11 个成员） | 想在自己的 Agent 里复用，把它解包丢进你的 agent 目录 |
| **源码** | `scripts/`（agent / gazetteer / memory / render_map / run_agent / tools / selfcheck） | 想改行为、换城市、加工具时读它 |
| **证据** | `Zhouruoying_C4D_验证报告.md`、`output_screenshots/`、`logs/` | 想复核「它真跑过」，按报告里的命令逐条重放 |

## 二、30 秒上手（不装任何东西）

1. 双击 `Zhouruoying_C4D_map.html`，浏览器直接打开；
2. 地图上有 6 个标记，点开每个能看到**名称 / 分类 / 一句说明 / 经纬度**；
3. 网址末尾可加片段切换底图：`#osm` 走 OpenStreetMap、`#amap` 走高德、`#offline` **只画标记不请求任何瓦片**（断网时的正确姿势）。

> 只有街道底图需要联网，**点位与说明都在文件里**，所以断网也不会白屏——只会没有街道底图，标记照常显示。

## 三、装到自己的环境（想自己跑一遍）

**前置**：macOS / Linux，Python 3.12+，本机装有 [Ollama](https://ollama.com)（本交付实测 0.34.4）。

```bash
# 1. 拉模型（挑战点名的 Gemma 4 系列；24GB 统一内存选 E4B 这一档）
ollama pull gemma4:e4b

# 2. 体检：确认端点只回环、模型在位、零第三方依赖
python3 scripts/run_agent.py --offline-check     # → rc=0

# 3. 结构自检：22 项断言（含 6 项负向）
python3 scripts/selfcheck.py                     # → 22/22 PASS, VERDICT: GREEN

# 4. 端到端跑一轮（自然语言 → 工具调用 → 出地图）
python3 scripts/run_agent.py --model gemma4:e4b  # → verdict=GREEN, rc=0
```

跑完你会得到：`memory/places.json`（点位）、`memory/places_events.jsonl`（事件流）、还有地图 HTML。全过程日志在 `logs/session_summary.json`。

**零第三方依赖**：只用 Python 标准库 + Ollama HTTP 接口，不需要 pip install 任何东西。自检 P19 就是断言这一点。

## 四、换成你自己的城市 / 地点

这套 Agent 的价值在于**「坐标不交给模型即兴编」**：地名→经纬度收敛在本地索引 `scripts/gazetteer.py` 里，模型只能通过 `get_place` / `add_place_from_index` 取用。所以要换城市，只改一处：

1. 打开 `scripts/gazetteer.py`，按 `名称 → (纬度, 经度, 分类)` 的格式加你自己的地点；
2. 分类颜色在 `scripts/render_map.py` 的 `CATEGORY_COLORS`（校园 / 交通枢纽 / 博物馆 / 人文景点 / 商业地标…），想加分类先在这里登记颜色；
3. 重新跑第 3、4 步即可。

**为什么这样设计**：模型负责「听懂人话 + 选工具」，坐标由可核对的本地索引提供。这样即使模型换版本，点位也不会漂。第 1 轮它先 `get_place` 拿到 `34.527/113.745`，再 `add_place` 写入，两者逐位一致——这就是「坐标不是编的」的直接证据。

## 五、它自己会做什么、不会做什么

**会**：理解自然语言、按地点分类、调工具写记忆、把描述文字写给每个点位、渲染成图。
**不会**：编造它索引里没有的坐标；底图瓦片不可达时**不会假装成功**，而是只画标记并在右下角给出提示。

## 六、明确限制（如实写）

1. **只有街道底图需要网络**：OSM 瓦片在本机实测不可达，渲染器按「先探测、再选源」自动回退到高德（详见 `logs/probe_net.json`）。
2. **速度与机器有关**：76.16 tok/s 是 M5 Pro / 24 GB / Q4_K_M 的实测值，换机换量化会变。
3. **生成式输出不保证逐字复现**：可复现的是**流程与校验**，不是模型说的每一句话。
4. **无真人录屏**：截图由 Edge headless 生成，等待 `window.__mapAgentReady === true` 后落盘。

## 七、想看「它到底是不是真在干活」

按顺序读这三份，全部可复核：

1. `Zhouruoying_C4D_验证报告.md` —— 六层验证矩阵 + 逐轮工具调用链；
2. `Zhouruoying_C4D_demo运行记录.md` —— 那一轮 demo 的原样流水；
3. `Zhouruoying_C4D_AI日志.md` —— 这次交付里 AI 错在哪、怎么改的（含不是宣传的翻车记录）。
