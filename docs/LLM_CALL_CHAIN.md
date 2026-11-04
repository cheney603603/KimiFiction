# LLM 调用链说明

本文档梳理 NovelGen（KimiFiction）从「开书设定」到「产出 50 章」的全部 **LLM API 调用链路**（每 1 次调用 = 一次 /chat/completions 请求），并给出总量估算，便于评估成本与调优。

## 1. 相关配置

| 配置项（backend/.env） | 含义 | 默认 |
|---|---|---|
| `LLM_PROVIDER` | 模型提供商（openai/deepseek/kimi/yuanbao/local_llama） | `deepseek` |
| `DEEPSEEK_API_KEY` | API Key（联影 AI Infra 网关填网关 Key） | — |
| `DEEPSEEK_BASE_URL` | 网关地址，如 `https://ai-infra.united-imaging.com/v1` | deepseek 官方 |
| `DEEPSEEK_MODEL` | 模型名，如 `DeepSeek-V4-Flash` | `deepseek-chat` |
| `RUN_POST_WRITE_RUBRIC` | 章节写入后是否跑 Rubric 八维评测（每次 = **8 次调用**） | `false` |
| `RUN_POST_WRITE_ENTITY_EXTRACTION` | 章节写入后是否对正文做实体抽取（每次 = 1 次调用） | `true` |

> 说明：联影 AI Infra 网关对**非流式**请求体有 ~1000 字节上限，应用内已统一改用流式（`stream=true`）调用并聚合结果（见 `app/services/llm_service.py::_chat_deepseek`）。

## 2. 整体调用链（一次完整故事生产）

### 2.1 前置阶段 —— 整本书只跑一次（共 6 次调用）

```
开书/需求分析 demand_analysis     1 次（GenreAnalyzerAgent）
世界观构建 world_building          1 次（WorldBuilderAgent）
角色设计 character_design          1 次（CharacterDesignerAgent）
剧情设计 plot_design               1 次（PlotDesignerAgent）
卷大纲 outline_draft               1 次（OutlineGeneratorAgent）
章节细纲 outline_detail            1 次（一次性批量产出多章细纲）
```

### 2.2 每章调用链（以 workflow_engine.write_chapter 为准）

```
第 N 章
│
├─ (可选) 章节细纲 outline_detail ── 已有则跳过
├─ build_chapter_context           0 次（ContextManager 纯检索 + RAG 召回，非阻塞）
│
▼
Writer-Reader 对抗循环（WriterReaderLoop，max_rounds=3，达标即提前退出）
│   每轮 R（1 轮 = 2 次调用）：
│     ├─ ① Writer 写作     1 次（ChapterWriterAgent.process）
│     └─ ② Reader 评分     1 次（ReaderAgent.process → reader/hook 分 + 是否愿读）
│          通过条件：reader_score≥0.78 ∧ hook_score≥0.70 ∧ 愿读
│
▼
③ Reviewer 审核                    1 次（ReviewerAgent.process）
│
▼
④ Rubric 八维评测                  [RUN_POST_WRITE_RUBRIC]
│     默认关闭 → 0 次；开启 → 8 次（8 维度各 1 次）
▼
⑤ 实体抽取                         1 次（EntityExtractionService，仅抽取新实体）
│
▼
⑥ 记忆构建/合并                    0 次（MemoryService，纯 DB + 向量检索）
│
▼
⑦ 硬门禁（P0-9）                  0 次（ChapterHardGate 确定性规则，不含 LLM）
│     未通过 → 定向重写 ≤1 次（+1 次调用；受 P2 成本熔断约束）
│     仍不过 → 章节标记 flagged 落库，待人工处理（评测页可「按意见改写」）
│
▼
保存章节 + 更新小说进度 + WebSocket 推送（0 次）
```

> 启用 `WRITING_PIPELINE_V2` 后（默认关闭），② 的整章对抗循环被 `scene_pipeline.py` 取代：
> 场景节拍规划 1 次 JSON → 逐场景生成 3 次纯文本（各约 1000 字）→ 场景缝合 0 次 → 硬门禁（内部执行，
> `workflow_engine` 跳过避免重复）。单章合计 4–5 次调用。

**每章调用次数（默认链路，V2 关闭时）：**

| 步骤 | 调用次数 |
|---|---|
| Writer | 每章 R 次（R = 实际对抗轮次） |
| Reader | 每章 R 次 |
| Reviewer | 每章 1 次 |
| Rubric 八维评测 | 每章 0 次（默认关）/ 8 次（开） |
| 实体抽取 | 每章 1 次 |
| 硬门禁定向重写 | 每章 0–1 次（仅门禁未通过时） |
| **合计** | **4–7 次**（R=1→最小，R=3→最大）|

### 2.3 修订链路（单章修订）

```
revise_chapter（即评测页「按意见改写」按钮的落点）
├─ Writer（REVISE）   1 次
├─ Reader 复评         1 次
└─ Reviewer 复核       1 次
```
（修订通常复用 Writer-Reader 循环，可能多轮；由 `POST /api/v1/workflow/revise/{novel_id}` 触发。）

## 3. 50 章总量估算

前置：6 次（整本一次）。

| 场景 | 每章次数 | ×50 | 前置 | **总调用量** |
|---|---|---|---|---|
| 最小（全部第 1 轮通过） | 4 | 200 | 6 | **206** |
| 典型（平均 1.5 轮） | 5 | 250 | 6 | **256** |
| 最大（每章跑满 3 轮） | 7 | 350 | 6 | **356** |

**若开启 Rubric 八维评测**，每章 +8 次 → 典型总调用量升至 **≈ 656 次**（Rubric 占约 60%）。

> 估算前提（源自代码默认值）：
> - Writer-Reader 循环 `max_rounds=3`、阈值 `0.78 / 0.70`、早停（`app/writer_reader_loop.py`）
> - Reviewer 1 次、实体抽取 1 次（`app/workflow_engine.py`）
> - 硬门禁 0 次、仅失败时定向重写 +1（`app/services/hard_gate.py`、`app/services/cost_breaker.py`）
> - 记忆构建/合并、上下文组装均为 DB/向量检索，不产生 LLM 调用
> - 实际每 Agent 内部为 ReAct 循环，此处按「1 次 ReAct = 1 次 API 调用」、常在第 1 步收敛估算

## 4. 关键代码位置

| 环节 | 文件 |
|---|---|
| LLM 客户端（流式调用） | `app/services/llm_service.py::_chat_deepseek` |
| LLM 配置解析 | `app/core/llm_config_manager.py` |
| 写作/阅读/审核 对抗循环 | `app/writer_reader_loop.py`、`app/agents/writer.py`、`app/agents/reader.py`、`app/agents/reviewer.py` |
| 章节写入主流程 | `app/workflow_engine.py::write_chapter` |
| 分场景管线 V2（开关后启用） | `app/services/scene_pipeline.py`、`app/services/writing_diagnostics.py`、`app/services/style_profile.py` |
| Rubric 评测开关 | `app/workflow_engine.py`（`RUN_POST_WRITE_RUBRIC`） |
| 硬门禁 / 成本熔断 | `app/services/hard_gate.py`、`app/services/cost_breaker.py`、`app/services/foreshadowing_ledger.py` |
| 实体抽取 | `app/services/entity_extraction_service.py`、`app/workflow_engine.py` |
| 前置各阶段 | `app/workflow_engine.py`（world_building/character_design/plot_design/outline_*）、`app/agents/*` |
| 批量产能管线 | `scripts/run_novel_pipeline.py`（`full --watch --webhook`） |

## 5. 前端（世界可视化相关）

- 实体图谱 / 小说地图 / 知识库页面共用聚合接口：`GET /api/v1/novels/{id}/world`
- 前端组件：`frontend/src/pages/EntityGraph.tsx`、`NovelMap.tsx`、`KnowledgeBase.tsx`
- 数据聚合入口：`app/api/endpoints/novels.py::get_novel_world`

## 6. 评测与规则优化工具链：与小说写作的关系

评测（八维 Rubric）与规则优化**不属于 §2 的写作调用链**，而是挂在写作链路之外的**旁路质量工具**——
默认不参与自动生成（`RUN_POST_WRITE_RUBRIC=false`），由人按需触发。它与实际写作的衔接点如下：

### 6.1 位置：旁路，不是流水线一环

```
写作调用链（§2）:  细纲 → 对抗循环 → Reviewer → [Rubric] → 实体 → 硬门禁 → 落库(含 writer_meta)
                                                        ↑
评测/优化工具链:    评测页(人工/按需) ── 读取章节内容/状态/历史评测 ──┘
                   │     │
                   │     └─ 规则优化: 分析"好/坏章节" → 调规则权重(evaluate_rules_llm.csv) → 影响今后评测
                   └─ 按意见改写 ──► POST /workflow/revise/{novel_id} ──► 重新进入写作链路(§2.3)
```

### 6.2 评测页（`/evaluation`）读什么、写什么

- **读**：章节正文 + 章节状态（含 `flagged`）+ 历史 Rubric 评测（`rubric_evaluations` 表）+
  章节元数据（`generation_params` 内的 `writer_meta`：loop_history / reader_feedback / editor_review、硬门禁结果）。
- **三个数据来源**：服务端预置参考小说、**个人上传的语料**（`/training/evaluation/upload`，按用户隔离，供自评或对标）、**自己的小说章节**。
- **写（回灌写作链路）**：对低分/flagged 章节一键「按意见改写」→ `POST /workflow/revise/{novel_id}`，
  走 §2.3 的正式修订链路（Writer 重写 → Reader 复评 → Reviewer 复核）。**这是评测工具影响产出的唯一直接通道**。

### 6.3 规则优化（`/evaluation/optimizer`）做什么

- 把"好章节"与"坏章节"（flagged / Rubric 低分 ≤5）作为正负样本，统计 88 条规则在各维度上的区分度，
  产出权重调整建议与一致性诊断。
- 应用调整即重写 `scripts/evaluation/evaluate_rules_llm.csv`（每次应用自动生成 `.backup_时间戳` 备份，可回滚）。
- **影响面**：只影响**评测这个测量仪器本身**的刻度（规则权重/判据）；**不影响**确定性硬门禁（字数/结尾/角色卡等）。
- 两种样本来源：手动勾选参考小说，或「从我的小说自动采集」——自动把已写章节按状态分类为正负样本，无需手工挑文件。

### 6.4 一句话总结

> **评测 = 写作产出的"体检仪"（旁路、按需、不自动参与生成）；它的两个回流点是「按意见改写」→ 正式修订链路，
> 以及规则权重 → 未来评测的刻度。** 硬门禁、质量产出由写作链路自己负责，评测工具不兜底也不代劳。

### 6.5 相关接口

| 接口 | 作用 |
|---|---|
| `POST /training/evaluation/run-sampled` | 对任意文本流式八维评测（参考小说/个人语料/章节共用） |
| `GET /training/evaluation/chapter/{novel_id}/{chapter_number}` | 查看某章历史评测与门禁元数据 |
| `POST /training/evaluation/upload` | 个人语料上传（按用户隔离，仅自己可见） |
| `POST /training/evaluation/optimize-from-novel` | 从自己章节自动分类好/坏样本并出优化报告 |
| `GET/POST /training/evaluation/rule-csv-backups` | 规则 CSV 备份列表与回滚 |
| `POST /workflow/revise/{novel_id}` | 「按意见改写」的落点（§2.3 修订链路） |