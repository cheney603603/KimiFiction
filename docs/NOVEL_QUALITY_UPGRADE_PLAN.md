# 小说生产管线升级方案（合订版）

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 日期 | 2026-11-03 |
| 范围 | 写作链路质量、去 AI 味工程、自动化产能 |
| 状态 | **已执行（P0 / P1 / P2 主体落地，待盲读验收）** |
| 关联文档 | `PROGRESS.md`、`docs/LLM_CALL_CHAIN.md`、`docs/INTEGRATION_PLAN.md` |

---

## 执行记录（2026-11-03）

| 阶段 | 落地情况 | 验证 |
|---|---|---|
| RL-0 | `WritingAction` 迁移至 `app/models/writing_action.py` | ✅ |
| P0-1/2 | `max_tokens` 默认 8192 可配置；DeepSeek `json_mode` 探测+降级 | ✅ 单测 |
| P0-3/4 | `temperature` 全 provider 生效；`BaseAgent.call_llm_text()` 纯文本调用 | ✅ 单测 |
| P0-5 | `writer.py` 正文脱离 ReAct 信封 | ✅ |
| P0-6/7/8 | 字数惩罚符号 / Reader 上下文 / `reader_feedback` 断链修复 | ✅ 单测 |
| P0-9 | 硬门禁 `app/services/hard_gate.py` + `flagged` 状态落库 | ✅ 单测 |
| P0-10 | 文风去硬编码 `app/services/style_profile.py` | ✅ 单测 |
| RL 移除 | 循环重构为 `writer_reader_loop.py`；删 `training/` 算法文件、`rl_training/`、训练 API、前端训练页/路由/导航 | ✅ 导入+tsc |
| P1 | `scene_pipeline.py`（场景规划/逐场景生成/缝合/盲评）、`writing_diagnostics.py`（三尺度）、章节类型池、风格锚点，置于 `WRITING_PIPELINE_V2` 开关后 | ✅ 单测 |
| P2 | 伏笔台账、设定预检、成本熔断、`run_novel_pipeline.py full --watch --webhook` | ✅ 单测 |
| 2026-11-04 评测工具链 | 个人语料上传（按用户隔离）/我的语料接口；评测页「我的小说」模式（章节勾选批量评测、成本估算、按意见改写→`/workflow/revise`）；优化器「从我的小说自动采集样本」；规则 CSV 备份/回滚 | ✅ curl+tsc+133 单测 |
| 2026-11-04 修复 | `rag_system` HybridRetriever 误用 `self.retriever` 导致 RAG 召回恒失败（被 writer 静默吞掉）；`test_rag_system.py` 乱码损坏无法采集（重写）；e2e 端口 8000→8080 | ✅ 单测 |

**遗留**：盲读 A/B 验收（§8）待人工执行；`WRITING_PIPELINE_V2` 默认关闭，验收通过后置 `true`。
**决策遗留**：实体接口 `/entities/*` 保持匿名公开（2026-11-04 确认，见 D5）；若后续加鉴权需同步改造实体 e2e 测试。
**环境备注**：本机 conda 环境的 fastapi(0.115)/starlette(1.10) 不兼容导致 `APIRouter()` 启动报错（与本次改动无关），建议 `pip install "starlette<0.41"` 后运行服务。

---

## 0. 决策记录

本节记录 2026-11-03 与项目负责人确认的目标基线。后续所有取舍以此为准，如需变更须回写本节。

| # | 决策项 | 结论 | 对方案的约束 |
|---|---|---|---|
| D1 | 目标取向 | **两者并重**：先修缺陷保底，质量与产能交替迭代 | P0 必须先落地；P1（质量）与 P2（产能）交替推进，不并行开工 |
| D2 | 章节规格 | **3000 字/章，日更 1 章** | 单章切分为 **3 个场景 × 约 1000 字**，每场景独立生成 |
| D3 | 去 AI 味验收 | **人工盲读通过** | 验收以盲读协议为主判据，客观指标为辅证 |
| D4 | RL 体系处置 | **彻底移除** | 见 §6 精确移除清单；八维评测与数据采集**不属于** RL，予以保留 |
| D5 | 实体接口鉴权 | **保持匿名公开**（2026-11-04 确认） | 与全站匿名设计一致；唯一受保护的是硬删除与个人语料上传。如后续加鉴权须同步改造实体 e2e 测试 |

---

## 1. 现状诊断

以下 10 项均为代码实测结论，非推测。按影响面排序。

### 1.1 确定性缺陷（bug 级，非设计取舍）

| ID | 缺陷 | 位置 | 后果 |
|---|---|---|---|
| B1 | `max_tokens` 默认 4000 且全项目无覆盖 | `services/llm_service.py:49-50`、`:606` | 3000 字目标对应约 3900–4500 token，叠加 prompt 与结构化开销后**每章在句中断裂**。这是"结尾突兀"的主因 |
| B2 | DeepSeek 通道忽略 `json_mode` | `services/llm_service.py:269-278`（payload 无 `response_format`） | 全部 Agent 的 JSON 输出依赖模型自觉；解析失败后静默降级为中性分，**质量信号失真** |
| B3 | 正文经 ReAct JSON 信封输出 | `agents/writer.py:296-302` | 正文须塞入 `final_answer` 字符串，转义易损坏；输出预算被 thought 占用；模型在结构化语境下写作导致**句长趋同、节奏扁平** |
| B4 | `temperature` 对 DeepSeek 分支无效 | `agents/base.py:100-110`（仅 OPENAI 分支生效） | 多温度采样、候选多样性全部空转；TPO 三个候选实际为同一文本 |
| B5 | 字数惩罚符号错误 | `writer_reader_rl.py:126-136` | 字数不足时惩罚值为正数直接相加，**越短得分越高**，系统性压低章节厚度 |
| B6 | 质量门禁不存在 | `writer_reader_rl.py:434` | `passed=False` 仍取 `best_state` 落库，门禁形同虚设 |
| B7 | Reader 评审缺上下文 | `writer_reader_rl.py:540-546` | 仅传 draft + outline，无前文、无角色卡，"连贯性"评分无依据 |
| B8 | `loop_history` 缺 `reader_feedback` 键 | `writer_reader_rl.py:414-424` ↔ `workflow_engine.py:1424` | 下游恒取空字典，**Reader 反馈到 Reviewer 的链路是断的** |

### 1.2 结构性缺陷（设计问题）

| ID | 缺陷 | 位置 | 后果 |
|---|---|---|---|
| B9 | GRPO 闭环为空实现 | `writer_reader_rl.py:359-371`（`Episode` 构造后未使用，注释"这里简化处理"） | 所谓 RL 训练不存在，策略采样为随机占位 |
| B10 | 文风指令硬编码为空话 | `novel_workflow.py:311`（`writing_style="叙事流畅，情节紧凑"`） | 模型无任何可模仿的具体语感 |

### 1.3 其他已核实但非致命项

- `novel_workflow.py:314` 将 RAG 融合结果赋给 `entity_context`，类型为 `List[str]` 不会崩溃，但被 `writer.py:220` 标注为"实体状态追踪"，属**标签错位**（P2 顺带修正）。

---

## 2. 方案自审与修正记录

初版方案存在 3 处实质性错误，记录于此以防后续重蹈。

| 编号 | 初版主张 | 问题 | 最终修正 |
|---|---|---|---|
| R1 | 去 AI 味检测器"作为惩罚项进入 Reward" | **违反 Goodhart 定律**：指标一旦成为优化目标即失效。模型会写长句凑方差、绕开禁用词换同义词、拆碎段落凑熵。绝对阈值还会误杀合法风格（古龙全短句、海明威极简） | 检测器**只做诊断与告警**，结果写入章节元数据供人查看，**不参与任何打分与门禁加权**。文风引导改由「风格锚点 few-shot」承担——让模型模仿具体文本，而非追逐数字 |
| R2 | P0 仅抬高 `max_tokens` 到 `target_words×2` | **治标**。3000 汉字约 3900–4500 token，抬到 8192 仅勉强够；且单次生成越长，后段质量衰减越明显（重复、失焦） | 改为**分场景生成**（3 场景 × 1000 字），从根上规避上限，同时获得节奏变化。原 P2 的分场景动作**提前至 P1** |
| R3 | 门禁以 Reader 分为判据 | Reader 系自评，存在系统性偏差且方差大。用噪声控制流程，重写成本翻倍且可能越改越差 | 门禁分两层：**硬门禁用确定性规则**（见 §5.2）；**软信号用 LLM 分**，仅允许触发 1 次定向重写且设成本上限 |
| R4 | "冻结 RL/TPO 体系" | 表述过激。`training/` 内 LoRA 训练器、数据采集、`llm_judge` 是有价值资产 | 按 D4 决策改为**彻底移除算法与策略层**，但保留八维评测与数据采集（§6） |
| R5 | 未量化成本影响 | 缺 ROI 论据 | 改造后单章大调用从约 6–12 次降至 4–6 次，**成本下降**（§7） |
| R6 | 以"跑一章对比"作验收 | 不构成可复现验收 | 改为固定 5 细纲 A/B + 盲读协议 + 客观指标（§8） |

---

## 3. 目标架构

### 3.1 改造后写作链路

```
章节细纲
   │
   ├─[1] 场景节拍规划        1 次 JSON 调用 → 3 个 scene 的 beat 表
   │      产出: 每场景的视角/目标/冲突/收束/字数
   │
   ├─[2] 逐场景生成          3 次纯文本调用（各约 1000 字）
   │      上下文分层: 全局设定(一次) + 场景局部(必要部分)
   │
   ├─[3] 场景缝合            0 次 LLM，规则化处理过渡与语气衔接
   │
   ├─[4] 硬门禁              确定性规则，不通过则定向重写
   │      最多 1 次重写，仍不过 → flagged 待人工
   │
   ├─[5] 软评分              1 次异构 Reviewer 调用（盲评）
   │
   └─[6] 落库 + 诊断指标      三尺度指标写入元数据（仅供人看）
```

### 3.2 与原链路的关键差异

| 维度 | 原链路 | 新链路 |
|---|---|---|
| 生成粒度 | 整章单次 | 3 场景分次 |
| 规划载体 | ReAct JSON 信封包裹正文 | 规划一次 JSON，正文纯文本 |
| 上下文 | 一次性全量注入 | 全局/局部两层，按场景裁剪 |
| 门禁 | 无 | 确定性硬门禁 + 单次定向重写 |
| 评审 | 同模型自评 | 异构盲评（换模型或换 persona） |
| 质量信号 | 单一标量 reward | 硬规则通过 + 软分 + 诊断指标三者分离 |

---

## 4. P0：保底修复（预计 1 天）

目标：消除截断与信号失真，让现有产物达到"完整可读"。**不含**任何架构改动。

| 任务 | 文件 | 具体动作 | 验收判据 |
|---|---|---|---|
| P0-1 | `services/llm_service.py` | `max_tokens` 改为可配置，默认 8192；`get_llm_service` 透传该值 | 单次生成不再出现截断 |
| P0-2 | `services/llm_service.py:269-278` | payload 支持 `response_format={"type":"json_object"}`；先用探测请求确认网关支持，不支持则降级为 prompt 约束 | 探测通过则启用，失败则记录降级 |
| P0-3 | `agents/base.py:100-110` | `temperature` 透传至所有 provider 分支 | 同一 prompt 在不同温度下产出可区分文本 |
| P0-4 | `agents/base.py` | 新增 `call_llm_text()`：单轮纯文本，不经 ReAct 信封 | 正文输出不含 JSON 骨架 |
| P0-5 | `agents/writer.py:296-302` | 正文改写走 `call_llm_text`，ReAct 仅用于规划类 Agent | 同上 |
| P0-6 | `writer_reader_rl.py:126-136` | 修正字数惩罚符号（不足时应为负贡献） | 字数偏离目标的章节 reward 下降 |
| P0-7 | `writer_reader_rl.py:540-546` | `_reader_evaluate` 补入前文摘要、角色卡、未回收伏笔 | Reader 输出的 `confusing_points` 可引用前文 |
| P0-8 | `writer_reader_rl.py:414-424` | `loop_history` 元素补 `reader_feedback` 字段 | `workflow_engine.py:1424` 取到非空反馈 |
| P0-9 | `workflow_engine.py:1515` 附近 | 接入硬门禁（§5.2），未通过则定向重写 ≤1 次，仍不过则标记 `flagged` 并写库 | 存在 `flagged` 状态的章节记录 |
| P0-10 | `novel_workflow.py:311` | 移除硬编码 `writing_style`，改从小说资产读取 | 不同小说可产出不同文风 |

**P0 完成标准**：连续生成 3 章，均满足 §8.2 的客观指标；`flagged` 机制可用；调用日志无 JSON 解析降级。

---

## 5. P1：去 AI 味工程（预计 1 周）

### 5.1 三个机制（缺一不可）

**① 风格锚点**

- 小说级资产 `style_profile`，包含：3–5 段目标作者真实样本（各 300–500 字）、禁用词表、句法偏好说明。
- 每场景生成时注入，作为"模仿对象"而非"规则约束"。
- 关键：样本必须是**具体文本**。规则化的"要写得自然"对模型无效。
- 需人工提供首批样本；无样本时降级为不注入（不虚构）。

**② 反模板化**

- 章节类型池：冲突章 / 过渡章 / 情绪章 / 信息章 / 群像章。
- 按卷级节拍表分配，**禁止连续 3 章同类型**。
- 现状问题：`writer.py:30-39` 的"番茄铁律"要求每章必须有爽点，这是**强化同构的模板**。真人作者会写过渡章、情绪章。该铁律需按章节类型分化为 5 套子模板。

**③ 异构盲评**

- Writer 出稿后，Reviewer **不被告知稿件来源与版本**，且更换模型或 persona 评分。
- 目的：打破"同一模型自己给自己打分"的闭环——这是"越优化越像 AI"的根本机制。

### 5.2 硬门禁（确定性规则，不使用 LLM 分）

按顺序判定，任一不通过即触发定向重写（≤1 次）：

1. 字数达成率 ≥ 85%（相对 3000 字）
2. 结尾句已终止（不以逗号、顿号、"……"截断，无未闭合引号）
3. 场景数 = 3，且各场景字数偏差 ≤ 30%
4. 出场角色名全部命中角色卡（防臆造人物）
5. 冲突硬规则：境界/力量等级引用与世界观设定表一致
6. 伏笔台账无超期未回收项（P2 上线后启用）

### 5.3 三尺度诊断指标（仅诊断，不入 reward）

| 尺度 | 指标 | 计算方式 | 用途 |
|---|---|---|---|
| 微观 | 句长方差 burstiness | 相邻句长标准差 / 均值 | 告警：低于 0.45 标记"机器节奏" |
| 微观 | AI 高频词句命中率 | 黑名单正则，每千字命中数 | 告警 |
| 中观 | 段落长度分布熵 | 段长直方图熵值 | 告警：熵过低标记"段落过匀" |
| 中观 | 总结句密度 | 段末"这意味着/从今往后"类收束句占比 | 告警 |
| 宏观 | 跨章开头相似度 | 本章首 200 字与近 5 章的 n-gram 重合率 | 告警：>0.3 标记"章间同构" |
| 宏观 | 情绪曲线形状相关 | 相邻章情绪起伏曲线相关系数 | 告警：过高标记"曲线雷同" |

**强制约束**：这 6 项一律不进 reward、不进硬门禁。它们的作用是让人看见问题，不是让模型追逐数字（见 R1）。

---

## 6. RL 体系移除清单（D4）

### 6.1 移除范围

| 类型 | 路径（实测文件名） | 处理 |
|---|---|---|
| 算法 | `app/training/grpo_trainer.py` | 删除 |
| 算法 | `app/training/tpo_service.py` | 删除 |
| 算法 | `app/training/imitation_learning.py` | 删除 |
| 算法 | `app/training/enhanced_imitation.py` | 删除 |
| 算法 | `app/training/lora_trainer.py` | 删除 |
| 算法 | `app/training/hardware_config.py` | 删除 |
| 编排 | `app/training/training_pipeline.py` | 删除 |
| 导出 | `app/training/__init__.py` | 清理被删模块的导出 |
| 兼容层 | `app/rl_training/`（`__init__.py` `config.py` `lora_utils.py` `models.py` `train.py`） | 整目录删除 |
| 演示 | `backend/demo_rl_training.py` | 删除 |
| API | `app/api/endpoints/training.py`、`app/api/endpoints/training_pipeline.py` | 删除 |
| 循环内引用 | `app/writer_reader_rl.py` 的 GRPO/TPO/Episode 分支 | 移除，文件重命名为 `writer_reader_loop.py` |
| 前端 | `frontend/src/pages/RLVisualization.tsx`、`TrainingDashboard.tsx` 及其路由与 API 调用 | 删除，并清理导航菜单 |

### 6.2 明确保留（不属于 RL，勿误删）

| 保留项 | 路径 | 理由 |
|---|---|---|
| 八维 Rubric 评测 | `services/rubric_evaluation_service.py`、`models/rubric.py` | 质量度量基础设施，P1 依赖 |
| 程序化评分器 | `agents/reader.py` 的 `ProgrammaticRubricEvaluator` | 诊断指标的现成基础 |
| LLM-as-Judge | `training/llm_judge.py` | 盲评工具，P1 的异构评审要用 |
| 数据质量审计 | `training/data_quality_audit.py` | 数据侧工具，与 RL 算法无关 |
| 训练数据采集 | `services/training_data_collector.py` | 降级为"章节-评分"诊断日志，供人工复盘 |
| 前端评测页 | `Evaluation.tsx`、`EvaluationOptimizer.tsx` | 评测体系，非 RL |

### 6.3 前置重构（必须先做，否则删除即崩溃）

`writer_reader_rl.py:30-36` 从 `app.training` 导入 `WritingAction`、`Episode`、`GRPOTrainer`、`GRPOConfig`、`TPOService`，而 `WritingAction`（`GENERATE/REVISE/DELETE/KEEP`）是写作循环的**动作枚举，实际在被使用**，其定义位于 `rl_training/models.py`。

因此删除顺序必须为：

1. 将 `WritingAction` 枚举**迁移**到写作循环模块内（或新建 `app/models/writing_action.py`），改掉导入来源。
2. 移除 `writer_reader_rl.py` 中 GRPO 策略采样、`Episode` 构造、TPO 优化三段逻辑（`use_grpo`/`use_tpo` 参数一并删除）。
3. 文件重命名为 `writer_reader_loop.py`，更新 `workflow_engine.py`、`novel_workflow.py` 的导入。
4. 此时才可删除 `training/` 与 `rl_training/`。
5. 最后清理 API 与前端页面。

若跳过第 1 步，写作主链路会因 ImportError 直接不可用。

### 6.4 执行注意

- `writer_reader_rl.py` **不可整删**：它承载实际写作循环（Writer→Reader→Gate）。须重构而非删除。
- 移除后需全仓搜索残留 import：`grep -rn "rl_training\|GRPOTrainer\|TPOService\|WritingAction" backend/ frontend/src/`
- 前端删除训练页面后，需同步清理导航菜单与路由表，避免死链。

---

## 7. 成本影响

| 阶段 | 单章大模型调用次数 | 说明 |
|---|---|---|
| 现状 | 6–12 次 | Writer ReAct 1–3 轮 × 对抗 3 轮 + Reader 3 次 + Reviewer 1 次 |
| P0 后 | 3–5 次 | 正文脱离 ReAct，去掉多余轮次 |
| P1 后 | 5–6 次 | 场景规划 1 + 场景生成 3 + 盲评 1 + 定向重写 ≤1 |
| 预估 | 单章成本约下降 30–50% | 以实际 token 计费核算，需 P1 后实测校准 |

**关键判断**：改造在提升质量的同时**降低成本**，因为消除了 ReAct 多轮与无效对抗轮次。这是本次方案在经济性上的主要优势。

---

## 8. 验收协议（D3）

### 8.1 盲读协议（主判据）

1. 固定 5 个章节细纲（覆盖冲突/过渡/情绪/信息/群像各一）。
2. 同细纲、同模型，生成 A（改造前）与 B（改造后）两组稿件。
3. 稿件去除一切来源标记，随机编号后交人工阅读。
4. 每位评审独立回答：① 哪篇更像人写；② 自然度、细节感、可读性各打 1–5 分。
5. **通过标准**：B 的自然度中位数 ≥ 3.5，且 B 被判为"AI 写"的比例 ≤ 50%。
6. 评审人数 ≥ 2，意见分歧超过 1 分时增加第三人。

### 8.2 客观指标（辅证，自动校验）

| 指标 | 目标值 |
|---|---|
| 字数达成率 | ≥ 95%（2850–3150 字） |
| 截断率 | 0（无句中断裂、无未闭合引号） |
| 场景数 | = 3，各场景字数偏差 ≤ 30% |
| 跨章开头相似度 | ≤ 0.3 |
| 硬门禁通过率 | ≥ 80%（首轮通过，不含重写） |
| 单章调用次数 | ≤ 6 |

---

## 9. 风险与回滚

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 分场景导致"片段感"，场景间断裂 | 可读性下降 | 场景缝合层（规则化过渡 + 统一语气收尾）；P1 验收含"场景衔接自然度"抽检 |
| 风格锚点样本缺失 | 机制空转 | 无样本时明确降级为不注入，不虚构样本 |
| 分场景削弱全局伏笔控制 | 伏笔漏埋 | 场景 beat 表强制包含"本章伏笔动作"字段 |
| 移除 RL 误伤残留依赖 | 启动失败 | 移除前先全仓 grep 依赖；分批提交，每批后跑 `comprehensive_test.py` |
| 网关不支持 `response_format` | JSON 仍靠 prompt | 探测失败则降级并记录，不阻塞 P0 |
| 硬门禁过严导致重写率过高 | 成本上升 | 门禁阈值首版放宽（85%），按实测重写率调整 |

**回滚策略**：P0 按任务粒度独立提交，任一任务引入回归即单独 revert；P1 全部改动置于 `WRITING_PIPELINE_V2` 配置开关之后，默认关闭，验收通过后开启。

---

## 10. 执行顺序

```
P0（1天，保底）
 ├─ P0-1 输出长度      ┐
 ├─ P0-2 json_mode     │ 可并行
 ├─ P0-3 temperature   │
 ├─ P0-4/5 脱离ReAct   ┘
 ├─ P0-6 字数惩罚符号
 ├─ P0-7 Reader上下文
 ├─ P0-8 反馈断链
 ├─ P0-9 硬门禁
 ├─ P0-10 文风去硬编码
 └─ RL-0 WritingAction 迁移（§6.3 第1步，须最先做）
        ↓
   3 章连续验证 + 盲读基线采集（改造前 A 组）
        ↓
RL 移除（0.5天，与 P1 并行）
    重命名写作循环 → 删 training/ 与 rl_training/ → 清 API 与前端页面
        ↓
P1（1周，质量）  分场景 → 风格锚点 → 反模板化 → 异构盲评 → 诊断指标
        ↓
   盲读 A/B 对比，达标则进入 P2
        ↓
P2（1周，产能）  设定预检 → 伏笔台账 → 失败三态 → 成本熔断 → pipeline 原生化
        ↓
P3（可选）      卷级节拍规划 → 人工精修案例库（few-shot 回流，非 RL）
```

**依赖说明**：`RL-0` 是纯代码迁移，无行为变更，置于 P0 首位执行可消除后续删除的阻塞点。RL 移除本身与质量改造无耦合，与 P1 并行推进即可，但必须在 P2 之前完成，以免产能改造叠在待删代码上。

**RL 移除（§6）与 P0 同期执行**，因为它减少的是死代码，与质量改造无耦合，越早清理越少干扰。
