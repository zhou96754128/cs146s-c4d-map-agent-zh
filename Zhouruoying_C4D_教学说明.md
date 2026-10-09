# C4D 教学说明——从零到一张本地生成的地图

> 目标读者：**没有跑过本地大模型的人**。全程命令行 4 条，不需要 GPU 服务器，不需要 API Key，不需要付费。
> 预计耗时：安装 10 分钟 + 模型下载（看网速，5 GB 量级）+ 跑通 2 分钟。

---

## 第 0 步：确认你的设备够不够

| 你的设备 | 建议模型 | 说明 |
| --- | --- | --- |
| 8 GB 内存 | `gemma4:e2b` | 能跑，慢一些 |
| 16 GB 内存 | `gemma4:e4b` | **推荐**，本说明的默认档 |
| 24 GB+ Mac / 16 GB 显存 | `gemma4:31b` | 更聪明，更慢 |
| 完全不想碰命令行 | LM Studio（图形界面） | 见本文末「图形界面替代方案」 |

先看自己的配置：

```bash
sysctl -n machdep.cpu.brand_string    # macOS：看芯片
sysctl -n hw.memsize                  # macOS：看内存字节数（除 1073741824 得 GB）
sw_vers                               # macOS：看系统版本
```

---

## 第 1 步：装 Ollama

Ollama 是一个「把本地模型跑起来」的运行时，免费、开源、装完就有一个 HTTP 服务。

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# 确认装好了（本工程实测于 0.34.4）
ollama --version
```

Windows 用户：到 https://ollama.com/ 下载安装包，双击即可。

**确认服务在跑：**

```bash
curl -s http://127.0.0.1:11434/api/tags
```

如果返回一段 JSON（哪怕是 `{"models":[]}`），说明服务正常。若提示连接失败，先执行一次 `ollama list` 把服务唤醒。

---

## 第 2 步：下载模型

```bash
# 推荐档；体积约 5 GB，视网速可能要几十分钟
ollama pull gemma4:e4b
```

下载过程中可以用另一终端看进度：

```bash
ollama list          # 已完成的模型列表
```

> **下载慢/卡住怎么办**：`ollama pull` 支持断点续传，直接 Ctrl-C 后重新执行 `ollama pull gemma4:e4b` 会从断点接着下，不会重头来。国内网络不稳时，多试几次通常能完成。

---

## 第 3 步：拿到本工程

把 `Zhouruoying_C4D_agent-skill/` 这个目录（或仓库）放到任意位置。**本技能只用 Python 标准库，不需要 pip install 任何包。**

```bash
python3 --version     # 需要 3.10 及以上
```

目录结构确认一下：

```
Zhouruoying_C4D_agent-skill/
├── SKILL.md
├── scripts/
│   ├── run_agent.py     ← 入口
│   ├── agent.py         ← Agent 主循环
│   ├── tools.py         ← 12 个工具
│   ├── gazetteer.py     ← 本地地理索引
│   ├── memory.py        ← 记忆层
│   ├── render_map.py    ← 地图渲染
│   └── selfcheck.py     ← 离线自检
└── references/
```

---

## 第 4 步：先体检，再跑任务

**先跑不依赖模型的体检**，把「环境问题」和「模型问题」分开，出错了容易定位：

```bash
cd Zhouruoying_C4D_agent-skill
python3 scripts/run_agent.py --offline-check
```

这一步会检查地理索引、记忆层读写、渲染器三条链路，**不启动模型**。看到全绿再进行下一步。

**跑真实任务：**

```bash
python3 scripts/run_agent.py --model gemma4:e4b --reset \
  --task "把郑州西亚斯学院、黄帝故里景区、郑州新郑国际机场、郑州东站、河南博物院、二七广场标到地图上，每处带名称、类别和一句说明，然后渲染地图文件"
```

跑完你会看到类似输出：

```
=== C4D demo | 模型 gemma4:e4b | 端点 http://127.0.0.1:11434 | 共 1 轮 ===
--- 第 1 轮 ---
用户：把郑州西亚斯学院、……标到地图上……
Agent：地图已生成，共 6 个标记点……
     工具：add_place_from_index✔ ×6, render_map✔
     状态：done · 标记 6 · 耗时 xx.xs
```

打开当前目录下新出现的 `.html` 文件即可看到地图。

**换模型**只改一个参数：

```bash
python3 scripts/run_agent.py --model gemma4:e2b --task "……"     # 换小模型
python3 scripts/run_agent.py --host 11434 --task "……"            # 换端点
```

---

## 第 5 步（可选）：离线自检

想验证 Agent 的编排逻辑本身有没有问题，不需要模型也行——自检用一个**假模型**注入预设的工具调用：

```bash
python3 scripts/selfcheck.py
```

预期最后一行是 `VERDICT: GREEN`，退出码 0。共 22 项断言，其中 6 项是负向用例（查不到的地址、坏参数、未知工具、无点位渲染、记忆重放、重复执行幂等）。

---

## 常见问题

**Q：`curl http://127.0.0.1:11434` 连不上？**
先运行 `ollama list`。Ollama 的服务是按需拉起的，第一次调用会稍慢。若仍失败，检查端口是否被占用：`lsof -i :11434`。

**Q：报 `status=llm_unreachable`？**
就是上一条——模型服务没起来。本工程的退出码是 3，脚本可以据此判断。

**Q：模型答非所问 / 漏了几个地点？**
小参数量模型一次处理 6 个以上地点时偶发漏点。两个办法：把任务拆成多轮（`--task` 可以写多次），或换更大的 Gemma 4 档位。

**Q：想要一个索引里没有的地方怎么办？**
在任务里直接把坐标说清楚（例如「在 34.500, 113.700 加一个点」），Agent 会走 `add_place`。也可以自己往 `scripts/gazetteer.py` 的 `PLACES` 里加一条——那是唯一的坐标来源。

**Q：地图打开是空白的？**
先分清是「没有街道底图」还是「连标记也没有」。
- 只有标记、没有街道：断网时的正常表现——渲染器探测到瓦片源不可达就只画本地标记。想强制走离线，在网址末尾加 `#offline`（只画标记、不请求任何瓦片）；想指定底图源，用 `#osm` 或 `#amap`。
- 连标记也没有：点位为空。检查任务里说的地方是否都在索引里（索引外的地点必须由人直接给出坐标）。

**Q：怎么从头再来一次？**
`--reset` 清空记忆层；或直接删掉 `memory/` 目录。

---

## 图形界面替代方案（完全不想碰命令行）

1. 到 https://lmstudio.ai/ 下载 **LM Studio**（macOS / Windows / Linux 都有）
2. 在搜索框输入 `Gemma 4`，选择 **E4B** 档位，点下载
3. 用内置聊天窗口让它按 JSON 输出地点（提示词：`只输出 JSON 数组，每项含 name/lat/lng/description`）
4. 把 JSON 贴进 `scripts/`，用 `render_map.py` 生成地图

这条路把「Agent 自动调工具」降级成「人工复制粘贴」，Agent 能力展示会弱很多，但确实是零命令行的入门路径——挑战正文也把它列为非计算机专业同学的推荐路径。

---

## 可复现性说明

- 本工程不依赖任何第三方 Python 包，`python3 --version` 达标即可跑。
- 所有运行记录落在 `logs/`：`demo_stdout.txt`（人看的）、`run_log.jsonl`（逐轮轨迹，含模型名与耗时）、`session_summary.json`（结构化摘要）。
- 自检报告落在 `logs/自检报告_selfcheck.txt`。
- 坐标的唯一来源是 `scripts/gazetteer.py`；把它连同 `memory/` 一起复制走，地图就是完全可复现的。
