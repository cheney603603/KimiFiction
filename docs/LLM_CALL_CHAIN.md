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
├─ build_chapter_context           0 次（ContextManager 纯检索）
│
▼
write_chapter → Writer-Reader RL 对抗循环（max_rounds=3，达标即提前退出）
│   每轮 R（1 轮 = 2 次调用）：
│     ├─ ① Writer 写作     1 次（ChapterWriterAgent.process）
│     └─ ② Reader 评分     1 次（ReaderAgent.process → reader/hook 分 + 是否愿读）
│          通过条件：reader_score≥0.78 ∧ hook_score≥0.70 ∧ 愿读
│
│ 循环结束取最佳 draft（best_reward）
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
保存章节 + 更新小说进度 + WebSocket 推送（0 次）
```

**每章调用次数：**

| 步骤 | 调用次数 |
|---|---|
| Writer | 每章 R 次（R = 实际对抗轮次） |
| Reader | 每章 R 次 |
| Reviewer | 每章 1 次 |
| Rubric 八维评测 | 每章 0 次（默认关）/ 8 次（开） |
| 实体抽取 | 每章 1 次 |
| **合计** | **4–7 次**（R=1→最小，R=3→最大）|

### 2.3 修订链路（单章修订）

```
revise_chapter
├─ Writer（REVISE）   1 次
├─ Reader 复评         1 次
└─ Reviewer 复核       1 次
```
（修订通常复用 Writer-Reader 循环，可能多轮。）

## 3. 50 章总量估算

前置：6 次（整本一次）。

| 场景 | 每章次数 | ×50 | 前置 | **总调用量** |
|---|---|---|---|---|
| 最小（全部第 1 轮通过） | 4 | 200 | 6 | **206** |
| 典型（平均 1.5 轮） | 5 | 250 | 6 | **256** |
| 最大（每章跑满 3 轮） | 7 | 350 | 6 | **356** |

**若开启 Rubric 八维评测**，每章 +8 次 → 典型总调用量升至 **≈ 656 次**（Rubric 占约 60%）。

> 估算前提（源自代码默认值）：
> - Writer-Reader 循环 `max_rounds=3`、阈值 `0.78 / 0.70`、早停（`app/writer_reader_rl.py`）
> - Reviewer 1 次、实体抽取 1 次（`app/workflow_engine.py`）
> - 记忆构建/合并、上下文组装均为 DB/向量检索，不产生 LLM 调用
> - 实际每 Agent 内部为 ReAct 循环，此处按「1 次 ReAct = 1 次 API 调用」、常在第 1 步收敛估算

## 4. 关键代码位置

| 环节 | 文件 |
|---|---|
| LLM 客户端（流式调用） | `app/services/llm_service.py::_chat_deepseek` |
| LLM 配置解析 | `app/core/llm_config_manager.py` |
| 写作/阅读/审核 对抗循环 | `app/writer_reader_rl.py`、`app/agents/writer.py`、`app/agents/reader.py`、`app/agents/reviewer.py` |
| 章节写入主流程 | `app/workflow_engine.py::write_chapter` |
| Rubric 评测开关 | `app/workflow_engine.py`（`RUN_POST_WRITE_RUBRIC`） |
| 实体抽取 | `app/services/entity_extraction_service.py`、`app/workflow_engine.py` |
| 前置各阶段 | `app/workflow_engine.py`（world_building/character_design/plot_design/outline_*）、`app/agents/*` |

## 5. 前端（世界可视化相关）

- 实体图谱 / 小说地图 / 知识库页面共用聚合接口：`GET /api/v1/novels/{id}/world`
- 前端组件：`frontend/src/pages/EntityGraph.tsx`、`NovelMap.tsx`、`KnowledgeBase.tsx`
- 数据聚合入口：`app/api/endpoints/novels.py::get_novel_world`