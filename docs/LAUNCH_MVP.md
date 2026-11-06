# KimiFiction 快速上线方案（BYOK 作者工具）

| 项 | 内容 |
|---|---|
| 文档版本 | v0.3（M1/M2 已落地，M3 A/B 执行完成 + 可观测性落地） |
| 日期 | 2026-11-06 |
| 产品形态 | **作者工具**（用户用 AI 生成并管理自己的小说），非阅读平台 |
| 计费模型 | **Bring Your Own Key（BYOK）**：两种 tier 的 token 成本都由用户自己的 API Key 承担；平台只卖"编排产能" |
| 决策记录 | 关联 `docs/NOVEL_QUALITY_UPGRADE_PLAN.md` §0 D1–D5 |

---

## 执行记录

| 阶段 | 落地情况 | 验证 |
|---|---|---|
| M1 BYOK | 用户级 LLM 配置表（Fernet 加密）、中间件/任务队列/后台任务注入上下文、LLM 解析优先级=用户→全局→环境变量；设置页改"我的 Key"表单 | 14 单测 + 113 全量 |
| M1 额度墙 | users tier/quota 字段、novels user_id（存量回填）、quota_service、建书/生成 402 前置检查、`GET /quota/status`、`POST /quota/tier`（管理员） | 同上 |
| M2 Pro 解锁 | 批量管线 `run_novel_pipeline.py` 增加 `--user` 归属 + Pro tier 门槛；`WORKER_CONCURRENCY`/`PRO_BATCH_ENABLED` 配置（批量开关接入 `/quota/status` 供管线读取）；revise 计入每月章节额度；隐藏非 MVP 导航（规则优化/Agent协作/图谱入口） | 5 单测 + tsc |
| M3（部分） | 按用户生成并发限制 `gen_limiter.py`（free 同刻 1 个、Pro=`PRO_CONCURRENCY`）；盲读 A/B 脚本 `scripts/blind_ab_test.py`（5 固定细纲 + protocol.md 打分表，A/B 各启一个 V2 开关不同的后端实例） | 21 单测 |
| M3 A/B 执行 | 盲读 A/B 生成完成（variant A=novel 9、variant B=novel 8，各 5 章入库），`--finalize` 已出 `blind_ab/评审包/01~10.md` + `答案对照.txt` + `评分表.md`（seed 20261105 打乱） | 10 章文件 |
| M3 可观测性 | `llm_usage_logs` 用量表 + `GET /usage/novel/{id}`、`/usage/summary`（流式 `stream_options.include_usage` 取精确 token）；全局 RPM 滑动窗口限速 `LLM_RPM_LIMIT=40`；盲读脚本 `--parallel N` 多章并发；阶段/Agent 归属（chapter_writing 细分 writer/reader/review） | 实测 A 书 74,377 token |

**部署前提**：`backend/.env` 必须设置 `APP_KEY_ENCRYPT_SECRET`（未设置时用户无法保存 Key）。
**遗留**：真支付接入、邀请码发放、小说列表按用户隔离（D5 暂公开）、免费层参数管理 UI；
盲读评审包已生成，待人工盲读打分（§8.2 通过标准：B 自然度中位数 ≥3.5 且被判"AI写"比例 ≤50%）。
**操作注意**：联影网关（ai-infra）资源池实测只能承受**单路并发生成**——`--parallel 2` 会持续 503「资源池已满」；
A/B 均须 `--parallel 1` 顺序跑（RPM 限速防的是请求速率，防不了并发流饱和），等网关扩容后再放开并行。


## 1. 商业模型一句话

> 用户自带 LLM Key，自己付 token 钱；免费层限**1 本书 + 每月固定章数**，Pro 层**不限章数**
> （上限即用户自己的 Key 预算），我们只控制**并发 / 批量管线**等平台产能额度。

平台价值 = 写作编排（大纲→章节→门禁→评测）+ 质量看板，**不是**卖 token。因此：
- 免费层限额是**编排产能体验**（1 本书、每月 N 章），不是 token 限额；
- Pro 订阅费 = 平台产能费（无限章节、并发、批量管线），token 仍走用户自己的 Key。

---

## 2. 上线范围收束（MVP）

### 保留（核心闭环）

```
登录 → 小说管理 → 大纲生成 → 章节生成(writer_reader_loop) → 章节编辑
     → 自己读(ChapterReader) → 评测看板 → 快照/回滚 → 导出
     → LLM 设置页（改造为 BYOK 密钥管理）
```

### 隐藏 / 延后（入口收起，代码保留）

| 模块 | 处理 | 理由 |
|---|---|---|
| 规则优化器 `/evaluation/optimizer` | 前端隐藏入口 | 深度工具，普通作者不需要 |
| IterativeOptimizer | 隐藏 | 同上 |
| 实体图谱 / 小说地图 / 知识库 | 隐藏导航 | 非阅读体验必需 |
| 个人语料上传（我的语料） | 可留可隐藏 | 单作者场景价值低；代码已就绪，隐藏只需收导航 |
| `WRITING_PIPELINE_V2` 分场景 | 保持默认关 | 未盲读验收 |
| WorkflowChat / AgentWorkflow 图 | 隐藏 | 调试界面 |

> 隐藏 = 只动前端路由/导航与入口按钮，不动后端代码，避免删除回滚成本。

---

## 3. 双 Tier 定义

| 维度 | Free | Pro |
|---|---|---|
| LLM Key | 用户自带（BYOK） | 用户自带（BYOK） |
| 小说数 | 1 本 | 不限 |
| 章节生成 | 每月固定章数（建议 20 章/月） | 不限（受用户自己 Key 预算约束） |
| 并发 | 全局默认池（现 worker=2），单线程生成 | 可调并发 / 优先队列 |
| 批量管线 `run_novel_pipeline.py` | 不可用（403） | 可用（`full --watch --webhook`） |
| 评测 | 可用 | 可用 |
| 置 Pro 方式 | 注册默认 | 管理员后台置位 / 邀请码（真支付后置） |

---

## 4. 核心机制设计

### 4.1 BYOK 密钥管理

**现状**：`app/core/llm_config_manager.py::get_config()` 优先级 = 前端全局配置(`_global_config`，内存) > 环境变量 > 默认值。**无用户级配置**，LLM 设置页(`/llm`)改的是全局面板。

**改造**：新增用户级配置，解析优先级改为：

```
当前用户的 BYOK 配置(DB) → 全局配置(内存) → 环境变量 → 默认值
```

- **存储**：新表 `user_llm_configs`（`user_id` PK/FK、`provider`、`api_key_enc`、`base_url`、`model`、`updated_at`）。
  密文加密：`cryptography.Fernet`，密钥来自环境变量 `APP_KEY_ENCRYPT_SECRET`（必须显式设置才允许存 Key；
  未设置时禁止保存并提示，避免明文落库）。
- **API**：改造 `app/api/endpoints/llm_config.py` —— `GET/PUT /llm` 变更为按当前用户读写（`Depends(require_auth)`）；
  前端 `LLMSettings.tsx` 增加"我的 API Key / Base URL / 模型"表单，全局配置区仅超管可见。
- **生效范围（横切改造，分两步）**：
  1. 先覆盖**关键入口**：章节生成（`workflow_engine.py` 内 Writer/Reader/Reviewer 的 LLM 调用）、
     评测（`evaluation.py::_get_llm_client`）、批量管线。用户级 Key 未配置时自动回落到全局/环境变量。
  2. 用户上下文传递：新增 `app/core/user_context.py`（`ContextVar`），由 FastAPI 中间件/依赖在请求入口
     从 JWT 解出 `user_id` 写入；LLM 层读取。CLI（`run_novel_pipeline.py`）以 `--user <username>` 显式指定并登录。

### 4.2 额度墙（Quota）

- **数据模型**（`app/models/user.py` 增列 + `app/services/quota_service.py`）：
  - `tier: 'free' | 'pro'`
  - `quota_month: str`（如 `2026-11`）+ `monthly_chapters_used: int`（惰性重置：月变化即归零）
  - `novel_quota: int`（free=1，pro=-1 表不限）
  - `monthly_chapter_quota: int`（free=20，pro=-1）
- **计费点**：`workflow_engine.py::write_chapter`（1319）与 `revise_chapter`（1883）**落库成功后** `+1`；
  批量管线每写一章同计。评测（`run-sampled`）不计入章节额度（token 是用户自己的），只做轻量调用频控防滥用。
- **检查点（前置 403/402）**：
  - `POST /workflow/start`、`POST /novels`：校验小说数 ≤ `novel_quota`
  - `POST /workflow/chapter/{novel_id}`：校验月章数 < `monthly_chapter_quota`（free 且超额 → 402 返回带升级提示）
  - 批量管线启动：free → 403
- **重置**：读 quota 时按 `quota_month` 惰性归零，无需定时任务。

### 4.3 并发 / 批量管线额度

- **现状**：`app/core/task_queue.py::start_worker(concurrency=2)` 全局一个信号量，无用户区分。
- **快速落法（不改队列结构）**：
  - 批量管线入口前校验 tier（free → 403）；管线本身维持串行逐章。
  - Pro 解锁项只做"放行 + 参数放开"：`config.py` 增加 `PRO_CONCURRENCY`（如 4）与
    `PRO_BATCH_ENABLED`，管线/任务队列读取。
  - 更精细的按用户并发调度（每用户信号量/优先队列）列为 M3，不阻塞上线。

---

## 5. 实施顺序

### M1 — BYOK 基础 + 免费额度墙（核心，先做）

1. `user_llm_configs` 表 + 加密工具（Fernet）+ `user_context.py` ContextVar + 中间件
2. `llm_config.py` 改造为用户级读写；`LLMSettings.tsx` 改造成"我的 Key"表单
3. LLM 层关键入口接入用户配置解析（workflow 生成 / 评测 / 管线）
4. `users` 表加 tier/quota 字段 + `quota_service.py` + write/revise 计费点 + 前置检查点
5. 前端：免费超限 402 提示、"升级 Pro"占位按钮

**验收**：免费用户 1 本书 + 月 20 章闭环可跑；超额被 402 拦截；换自己的 Key 后评测与生成都走该 Key。

### M2 — Pro 解锁

1. 管理员置 Pro（`/llm` 同权或新增 `/admin/users/{id}/tier`）
2. 批量管线 tier 校验 + Pro 放行
3. 并发参数按 tier 放开
4. 隐藏非 MVP 导航入口（§2）

**验收**：Pro 用户可用 `full --watch --webhook` 批量写满；免费用户调用管线返回 403。

### M3 — 后置（上线稳定后）

- 真支付接入（Pro 订阅/微信支付/发票），只换充值入口，不改业务逻辑
- 按用户并发调度 / 优先队列
- 邀请码发放

---

## 6. 风险与权衡

| 风险 | 影响 | 缓解 |
|---|---|---|
| BYOK Key 泄露/明文落库 | 用户密钥泄露 | Fernet 加密 + `APP_KEY_ENCRYPT_SECRET` 未设则禁存；设置页不回显明文（仅"已配置"） |
| 用户 Key 质量参差（限流/失效） | 生成失败率上升 | 失败时给出明确错误"检查你的 Key/额度"，回落全局 Key 只对超管开放 |
| 免费层 20 章/月定太低 | 流失 | 参数化到配置项，上线后按留存调 |
| 全局 Key 与用户 Key 混用混乱 | 费用归属不清 | 日志记录每次 LLM 调用所用 Key 的归属（user_id 或 global） |
| CLI 管线以固定测试账号运行 | BYOK 后费用算错人 | 管线改为 `--user` 指定并登录，归属到人 |

---

## 7. 上线判据（DoD）

- [ ] 免费用户：开书 → 20 章 → 评测 → 导出，全程用自己的 Key，无平台收费
- [ ] 免费用户第 21 章 / 第 2 本书被 402 拦截，提示升级
- [ ] Pro 用户：无限章节 + 批量管线 `full --watch` 可用
- [ ] 用户 Key 加密落库，设置页不回显明文
- [ ] 非 MVP 导航入口已隐藏，代码保留可回切
