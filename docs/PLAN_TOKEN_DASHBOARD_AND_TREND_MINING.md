# KimiFiction 功能方案：用量看板（按模型）+ 热点/文风采集

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0（含可行性测试结论与演示，待评审） |
| 日期 | 2026-11-06 |
| 状态 | **待审核** —— 评审通过后进入实施 |
| 关联 | `docs/LAUNCH_MVP.md`（M3 可观测性）、`docs/NOVEL_QUALITY_UPGRADE_PLAN.md` §5（文风） |

---

## 0. 背景与目标

1. **用量看板（按模型）**：`llm_usage_logs` 已逐调用记录 `model`/`provider`/`tokens`/`retries`，但缺**按模型聚合接口**与**前端可视化**。目标：作者能一眼看到"开书花了多少 token、每章平均多少、按模型分布、各阶段重试几次"。
2. **热点/文风采集**：系统目前的"文风"只有硬编码 prompt 与用户手动提供的 `style_profile` 样本。目标：探索用 opencli（驱动真实 Chrome）自动翻阅**番茄小说/起点中文网**，抓取**热榜**（热点选题）与**正文样段**（文风学习），落库供场景管线使用。

---

## 1. 可行性测试结论（实测证据）

### 1.1 按模型 token 聚合 —— ✅ 可行

对真实 `llm_usage_logs` 直接跑 GROUP BY：

```
model=deepseek-flash provider=deepseek status=success
  12 次调用 | 输入 20,882 | 输出 53,495 token | 11 次重试 | 0 失败
```

- 后端加 `by_model` 拆分没有技术障碍（SQL 现成）。
- 前端 `frontend/package.json` **已有 recharts ^2.10.3**，无需新依赖。

### 1.2 opencli 驱动浏览器与网络可达性 —— ✅ 工具可用；✅ 目标站 API 现在就能访问（关键修正）

- `opencli v1.8.7` 已安装；浏览器桥接正常（Chrome profile `6dd2x4ad`）。opencli 能开页、读 DOM、截屏（百度验证通过）。
- **初版结论"番茄/起点被网络拦截"是工具层面的**，实测修正：
  - `curl`（Windows schannel）与 Chrome 直连 → `ERR_CONNECTION_RESET`（被拦）；
  - **Python OpenSSL（urllib / httpx）直连成功**：`fanqienovel.com/api/config/list` → 200，`www.qidian.com` → 202（反爬挑战页），`baidu` → 200；
  - 用户提供的代理 `127.0.0.1:7897` 的 TLS 隧道实测损坏（CONNECT 200 后立即 EOF），且 **Python 直连根本不需要代理**。
- **用户参考技能 `fanqie-rank`（.workbuddy/skills/fanqie-rank）已在本机跑通**：`selftest` 三通道全 PASS，真实返回番茄 37 品类 × 阅读/新书双榜数据（含 PUA 字体混淆解码）。演示见 `docs/demo/fanqie_rank_demo.json`（东方仙侠·阅读榜 top5 真实数据）。

**结论修正**：番茄**榜单热点现在就能自动采集**（复用 fanqie-rank 的 Python 直连链路）；番茄**章节正文不在公开接口**（该技能红线：仅榜单与书籍详情，不抓正文）；起点返回 202 挑战页，正文采集需浏览器/进一步处理，列为 P2。

---

## 2. 功能一：按模型 token 统计 + 可视化

### 2.1 后端改动

| 变更 | 说明 |
|---|---|
| `llm_usage_service.py` | `novel_summary` / `global_summary` 各增 `by_model`（`{model: {calls, tokens_in, tokens_out, retries, errors}}`） |
| `usage.py` 接口 | 新增 `GET /usage/models`（全局按模型聚合，最近 N 条）；`/usage/novel/{id}` 与 `/usage/summary` 响应兼容追加 `by_model` |
| 不改表结构 | `llm_usage_logs.model/provider` 已存在 |

### 2.2 前端改动

新增 `frontend/src/pages/Usage.tsx` + 路由 + 侧边栏入口（仅登录后可见）：

- **KPI 卡**：总调用 / 总 token（输入/输出）/ 重试 / 失败
- **按模型**：饼图（token 占比）+ 列表（每次调用的 model、retries、errors）
- **按阶段**：横向柱图（chapter_writing → writer/reader/review）
- **按章节**（选中某本书后）：柱图（token + 重试叠加）
- 图表库：**recharts**（已装）；数据源：`GET /usage/novel/{id}`、`GET /usage/models`

### 2.3 演示（已产出，见 `docs/demo/`）

- `usage_dashboard_demo.html`：自包含看板 mock，**真实落库数据**（variant A = novel 9），含 by_model 环形图 / by_agent / by_chapter / by_phase（后两者为实测，阶段结构为新代码预期）
- `usage_dashboard_demo.png`：上述页面截图（Chrome 渲染）

---

## 3. 功能二：热点/文风采集（opencli）

### 3.1 架构

```
【热点/榜单】番茄 —— 复用用户技能 fanqie-rank（Python urllib 直连，本机已跑通）
   scripts/fanqie_rank.py collect/rank
     37 品类 × 阅读/新书双榜 → 字体混淆解码 → SQLite 快照库 → 跨期分析 → HTML 报告
     项目侧：新增 hot_topics 表 + 同步任务，把榜单/品类趋势接成「选题提示」输入 writer
【文风样章】番茄正文不在公开接口（红线：仅榜单与书籍详情）→ 半自动（用户粘贴样章，
   LLM 设置页入口，P0 已定）+ 书籍简介作风格锚点；起点正文 202 挑战页 → P2 浏览器方案
【通用采集器】scripts/collect_web_style.py：Python HTTP 直连优先（现在就能用），
   需要真实浏览器渲染的页面（起点挑战页等）走 opencli browser，支持 --proxy
```

### 3.2 分阶段实施（网络障碍已解除，时间线提前）

| 阶段 | 内容 | 状态 |
|---|---|---|
| P0 | 半自动样章入库（LLM 设置页入口，清洗 → style_profile.samples） | 待实施 |
| P1 | 番茄热榜自动采集接入：`hot_topics` 表 + 同步任务 + 选题提示（复用 fanqie-rank） | **现在可做**（本机已通） |
| P2 | 起点正文/文风样段（浏览器方案 / 挑战页处理）；可选接入评测闭环验证文风相似度 | 待定 |

### 3.3 合规红线

- 番茄公开接口仅**榜单与书籍详情**；不抓章节正文（沿用 fanqie-rank 技能红线）；
- 遵守合理频率（复用 RPM/并发限制）；采集内容仅用于风格/选题特征学习，不直接复制正文入库；
- 不抓盗版聚合站。

### 3.4 演示（已产出）

- `scripts/collect_web_style.py`（Python 直连优先 + opencli 兜底 + `--proxy`）：
  - `--url https://fanqienovel.com/api/config/list` → Python 直连成功（真实 JSON）
  - `--url https://www.qidian.com` → 返回反爬挑战页（202，供 P2 浏览器方案处理）
  - `--url https://www.baidu.com` → 正常抽取页面文本（14812 字符）
- 番茄榜单实时数据演示：`docs/demo/fanqie_rank_demo.json`（东方仙侠·阅读榜 top5，与本机 fanqie-rank 技能实测一致）。

---

## 4. 实施步骤与验收

### 功能一（用量看板）
1. `usage_service` 加 `by_model` + 新接口 `/usage/models`；单测覆盖聚合正确性
2. `Usage.tsx` 页面 + 路由/导航（**全部登录用户可见**）；`npm run build`（tsc）通过
3. 验收：真实生成一本书后，看板展示按模型/阶段/章节的 token 与重试，数值与 DB 一致

### 功能二（热点/文风采集）
1. P0：半自动样章入库（**LLM 设置页入口**，清洗 → `style_profile.samples`）
2. P1：番茄热榜自动采集接入 —— 项目内新增 `hot_topics` 表 + 定时同步任务（复用 fanqie-rank 的 Python 直连链路，本机已通），榜单/品类趋势接成选题提示输入 writer
3. P2（可选）：起点正文样段（浏览器/挑战页方案）
4. 验收：P1 热榜表出现 ≥1 个真实榜单条目（演示已产出）；P0 样章入库后新章节能体现样本文风

---

## 5. 演示物清单

| 文件 | 内容 |
|---|---|
| `docs/demo/usage_dashboard_demo.html` | 用量看板静态演示（真实数据） |
| `docs/demo/usage_dashboard_demo.png` | 看板渲染截图 |
| `docs/demo/fanqie_rank_demo.json` | **番茄真实榜单数据**（东方仙侠·阅读榜 top5，含解码结果） |
| `docs/demo/collector_baidu_demo.txt` | 采集器成功路径抽取样本 |
| `scripts/collect_web_style.py` | 通用采集器骨架（Python 直连优先 + opencli 兜底 + `--proxy`） |

## 6. 已确认项与待确认项

**已确认（用户）**：
1. 用量看板 → **全部登录用户可见**
2. P0 半自动样章入口 → **LLM 设置页**
3. 网络 → **Python 直连实测可用（番茄榜单可自动采集）**，代理 127.0.0.1:7897 TLS 隧道损坏不可用但无需使用

**待确认**：
1. P2 起点正文样段是否推进（需浏览器处理 202 挑战页，涉及风控风险与投入）
2. 番茄热榜同步任务的频率与范围（每日全量 37 品类 vs 按需单品类）
3. 选题提示进入 writer 的方式（写进章节细纲 prompt / 仅生成前提示）

---

## 7. 落地状态（已实现并联调验证）

**P0 用量看板 + 番茄榜单页已上网页（2026-11-06）**

| 项 | 后端 | 前端 | 验证 |
|---|---|---|---|
| 用量按模型聚合 | `GET /api/v1/usage/models`（`llm_usage_service.models_summary`） | `frontend/src/pages/Usage.tsx`（KPI + 模型饼图 + 章节/阶段柱图） | 浏览器实测：小说9 → 12 调用 / 74,377 tokens / deepseek-flash 饼图 / 第3-5章分布 |
| 番茄榜单 | `GET /api/v1/rank/genres`（37品类）+ `GET /api/v1/rank/fanqie`（快照缓存/refresh） | `frontend/src/pages/Rank.tsx`（男/女频、品类、阅读/新书、Top N、实时刷新） | 浏览器实测：西方奇幻阅读榜 20 行真实解码数据（书名/作者/字数/读数/连载状态/位次变化） |

配套：
- `hot_topics` 表新增 `rank_change` 列（需 ALTER，create_all 不迁移旧表 —— 已手动执行）。
- 榜单名 PUA 混淆逐请求轮换 → 后端恒回查 `/api/book/info`（明文）保证书名/作者准确（`decode_ok`）。
- 导航：`番茄榜单`（Flame）/ `用量看板`（Gauge）已加入 Layout；路由 `App.tsx` 已挂 `/rank`、`/usage`。
- 单元测试：`backend/tests/test_rank.py` 新增 9 个（decode / fetch_rank 字段变换与回落 / categories 分组 / by_model 聚合），不触网全过。
- `test_entity_e2e.py` 增加 `trust_env=False`：本机系统代理（127.0.0.1:7897）会令 httpx 把 localhost 请求导向代理返回 502，显式禁用后 e2e 34 过。

**P1 创作链路修复 + 模型管理（2026-11-06）**

1. **创作路径不再硬卡**：`/workflow/chapter/{id}` 遇到缺细纲时，后台自动补全本章细纲再写（`workflow_helpers.auto_complete_chapter_outline`），不再 400；LLM 不可用时优雅失败并给明确提示。实测：无细纲小说直接返回任务 ID，日志「本章缺少细纲，自动补全中...」。
2. **实体/地图自动维护**：确认引擎 `workflow_engine.write_chapter` 成功后已自动抽取实体/关系并写入实体库（小说地图/图谱自动反映）。之前「有章节无实体」的是 A/B 脚本直写的数据，走的是绕过管道的路径。
3. **单书模型三级回落**：novels 表新增 `model_provider/model_name/model_base_url`；解析优先级 **小说覆盖 > 用户 BYOK > 全局**（`novel_model_service` + `LLMConfigManager.get_config`）。新增 `GET /novels/{id}/llm-config` 展示实际生效配置；小说详情页新增「本书模型」卡片配置。实测：novel9 覆盖 deepseek-chat 后生效配置变为 `deepseek / deepseek-chat / api.deepseek.com`（novel_override=true）。
4. **API 配置页重做（参考 WeKnora ModelSettings）**：卡片式提供商网格（图标徽章/模型/BaseURL/已配置标签/悬浮操作）+「当前生效模型」条（来源徽章 我的Key/全局默认）+ 测试日志终端。
5. **「创作走不通」根因**：全局默认模型 `DeepSeek-V4-Flash`（ai-infra 网关）当前**无可用渠道**（`model_not_found` 503）→ 所有生成失败。修复路径：在 API 配置页配个人可用 Key，或在「本书模型」给单本覆盖到可用模型。

新增测试：`tests/test_novel_model.py`（覆盖构建/三级回落）。

**写作质量改进（P0+P1，2026-11-06）—— 蒸馏 human-writing / deai-promax / novel-generator**

1. **writer 语言·去AI味铁律**：套词黑名单（不由得/霎时间/殊不知/良久/眼底闪过一丝波澜/喉结滚动/心中五味杂陈等）+ 情绪用动作写 + 对话在做事 + 句长错落 + 逻辑暗线 + 细节跟视角 + 每场戏改变一项 + 世界规则/金手指不得违背。
2. **语言质检门禁**（`language_quality_gate.py`，确定性不触网）：套词/破折号/翻案句/模型路标 → 硬禁令；句长标准差/情绪直陈/逻辑连词/段落同构 → AI味评分(0-100)。集成 write_chapter：命中硬禁令 → 定向重写 ≤1 轮（`language_rewrite`）→ 仍不过标 flagged 待人工；结果存 generation_params.language_gate。
3. **细纲爽点节奏标注**：outline_generator 章节细纲加 `smile_point`（type: 装/打脸/人前显圣/升级/收获; intensity: 小/中/大），writer 输出上下文引用爽点与章末钩子强度。
4. **hard_gate 番茄红线规则7**：低俗/种马后宫高置信词表（种马/后宫/三妻四妾/床笫之欢/翘臀/胸脯等），命中即失败触发重写。

参考来源：`~/.workbuddy/skills/human-writing`（活人感+检查脚本）、`deai-promax`（朱雀五维+网文套词表）、`novel-generator`（爽点节奏公式）。新增测试 `tests/test_language_gate.py` 5 例。
