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

### 1.2 opencli 驱动浏览器 —— ✅ 工具可用，❌ 目标站被网络拦截

- `opencli v1.8.7` 已安装；`opencli doctor` 显示浏览器桥接正常（Chrome profile `6dd2x4ad` 已连接）。
- 实测 opencli 能打开页面、读取 DOM、截屏（用百度验证通过）。
- **番茄小说（fanqienovel.com）与起点中文网（qidian.com / m.qidian.com / fanqie.net）在公司网络下全部不可达**：
  - `curl` → `schannel: failed to receive handshake`（000）
  - Chrome（opencli 驱动）→ `chrome-error://chromewebdata/`，`ERR_CONNECTION_RESET`
  - 对照：`baidu.com` 可达（200 / 302），说明是**域名级防火墙重置**，不是工具或 TLS 指纹问题。

**结论**：采集器本身可行（opencli 管线已跑通），但当前企业网络禁止直连这两个小说站。采集必须运行在**能访问目标站的网络**（部署服务器 / 用户个人网络），或降级为**半自动**（用户粘贴样本）。方案按此分阶段设计，见 §3.2。

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
opencli browser（真实 Chrome 驱动，绕过纯 curl 的 TLS/反爬限制）
   → scripts/collect_web_style.py（已建骨架）
        ├── rank 模式：抓热榜标题/链接 → 热点关键词表 hot_topics（新表）
        └── prose 模式：抓正文样段   → 清洗 → style_profile.samples / 文风样本表
   → 供 writer/scene_pipeline 使用（热点做选题提示，样段做风格锚点）
```

`collect_web_style.py` 已实现：会话自动探测、目标页打开、`chrome-error` 识别与**网络拦截诊断**（不静默失败）、文本抽取与落盘。

### 3.2 分阶段实施（受网络条件制约）

| 阶段 | 内容 | 前置条件 |
|---|---|---|
| P0（当前可做） | 采集器骨架 + 热榜/样段清洗入库逻辑；**半自动模式**：用户提供样章文本 → 清洗入库（不依赖外网） | 无 |
| P1 | 在**可访问目标站的网络**跑通 rank/prose 采集 → 热点关键词表 → 选题建议 | 部署网络放开小说站 |
| P2 | 文风样段自动进 `style_profile`，场景管线按样本模仿（可选接入评测闭环验证文风相似度） | P1 数据量 ≥ 阈值 |

### 3.3 合规红线

- 只采集**公开榜单与公开样章**，遵守目标站 robots/ToS 与合理频率（已有 RPM/并发限制可复用）；
- **不抓盗版聚合站**；采集内容仅用于风格特征学习，不直接复制正文入库。

### 3.4 演示（已产出）

- `scripts/collect_web_style.py`：
  - `--url https://www.qidian.com` → 输出"网络策略拦截（ERR_CONNECTION_RESET）"诊断
  - `--url https://www.baidu.com` → 正常抽取页面文本（14812 字符，见 `docs/demo/collector_baidu_demo.txt`）
- 说明：百度仅为证明**管线可用**；番茄/起点需换网络后即可切换目标。

---

## 4. 实施步骤与验收

### 功能一（用量看板）
1. `usage_service` 加 `by_model` + 新接口 `/usage/models`；单测覆盖聚合正确性
2. `Usage.tsx` 页面 + 路由/导航；`npm run build`（tsc）通过
3. 验收：真实生成一本书后，看板展示按模型/阶段/章节的 token 与重试，数值与 DB 一致

### 功能二（采集）
1. P0：`hot_topics` 表 + 半自动样章清洗入库（本网络可做）
2. P1/P2：换网络后实测番茄/起点热榜与样段采集，落库并接入 writer 提示
3. 验收：P1 热榜表出现 ≥1 个真实榜单条目；P2 新生成章节能体现样本文风

---

## 5. 演示物清单

| 文件 | 内容 |
|---|---|
| `docs/demo/usage_dashboard_demo.html` | 用量看板静态演示（真实数据） |
| `docs/demo/usage_dashboard_demo.png` | 看板渲染截图 |
| `docs/demo/collector_baidu_demo.txt` | 采集器成功路径抽取样本 |
| `scripts/collect_web_style.py` | 采集器骨架（含网络拦截诊断） |

## 6. 待确认项

1. 用量看板页面是否加入 MVP 导航（还是仅 Pro 可见）？
2. 采集 P0 的半自动样章入口放哪（LLM 设置页 / 小说详情）？
3. 部署网络是否能放开小说站（决定 P1/P2 能否推进）？
