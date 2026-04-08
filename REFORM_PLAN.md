# KimiFiction 小说生成系统改造规划

## 📅 日期：2026-03-30

---

## 一、现状分析

### 当前架构
```
novel-writer.skill (压缩包)
└── SKILL.md          # 4阶段写作流程
└── references/        # 各阶段指南
    ├── phase1-guide.md  (5.8KB)
    ├── phase2-guide.md  (5.9KB)
    ├── phase3-guide.md  (5.5KB)
    └── phase4-guide.md  (5.6KB)
└── scripts/
    ├── merge_chapters.py  (章节合并)
    └── word_count.py       (字数统计)

backend/app/
├── workflows/
│   └── novel_workflow.py  # LangGraph工作流（部分实现）
├── agents/
│   ├── analyzer.py          # 类型分析Agent
│   ├── character_designer.py # 角色设计Agent
│   ├── outline_generator.py  # 大纲生成Agent
│   ├── writer.py            # 章节撰写Agent
│   ├── memory_manager.py     # 记忆管理Agent
│   ├── consistency_checker.py # 一致性检查Agent
│   ├── discussor.py         # 剧情讨论Agent
│   └── base.py              # Agent基类
├── services/
│   ├── llm_service.py        # LLM调用服务
│   ├── memory_service.py     # 记忆存储服务
│   ├── workflow_service.py   # 工作流服务
│   └── ...                   # 其他服务
└── core/
    ├── vector_store.py       # Qdrant向量存储
    ├── redis_client.py       # Redis客户端
    └── task_queue.py         # 任务队列
```

### 当前问题
| 问题 | 描述 | 优先级 |
|------|------|--------|
| 缺乏统一的工作流编排 | 各Agent独立工作，无法串联 | 🔴 高 |
| 上下文管理薄弱 | 无RAG、上下文压缩 | 🔴 高 |
| 状态管理不完善 | Redis状态可能丢失，无持久化 | 🔴 高 |
| 错误恢复缺失 | 无重试机制 | 🔴 高 |
| 文件存取不结构化 | 无统一文件管理 | 🟡 中 |
| 反馈修改困难 | 无法基于反馈调整章节/框架 | 🔴 高 |
| Skill与后端脱节 | Skill是独立的，未集成 | 🔴 高 |

---

## 二、改造目标

### 核心需求
1. **多Agent协作**：任务分解、工作流编排
2. **RAG + 上下文压缩**：前文、伏笔、剧情等背景信息输入
3. **状态管理与错误恢复**：完整的工作流状态持久化、自动重试
4. **结构化文件存取**：统一的小说项目文件管理
5. **渐进式工作流**：
   - 需求分析 → 世界观/核心故事线/角色/冲突/伏笔
   - 剧情大纲 → 细纲 → 具体章节
6. **反馈驱动的迭代**：重写章节、调整框架/伏笔/文风

---

## 三、改造方案

### 阶段一：基础设施重构 (Foundation)

#### 1.1 工作流引擎 (workflow_engine.py)
```
核心组件：
- WorkflowState: 统一状态定义
- WorkflowEngine: 状态机 + 任务调度
- StateManager: 持久化 + 恢复
- ErrorHandler: 错误分类 + 重试策略
```

#### 1.2 上下文管理器 (context_manager.py)
```
核心组件：
- RAGRetriever: 向量检索相关上下文
- ContextCompressor: 上下文压缩
- ChapterContext: 单章上下文构建
```

#### 1.3 文件管理器 (file_manager.py)
```
核心组件：
- NovelFileManager: 小说项目文件操作
- 文件结构规范
- 版本管理
```

### 阶段二：Agent增强 (Agent Enhancement)

#### 2.1 核心Agent职责
| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| AnalyzerAgent | 需求分析 | 用户原始需求 | 类型/风格/核心卖点 |
| WorldBuilderAgent | 世界观构建 | 类型 + 需求 | 世界观设定 |
| PlotDesignerAgent | 故事线设计 | 世界观 + 角色 | 核心故事线 + 冲突 + 伏笔 |
| CharacterDesignerAgent | 角色设计 | 故事线 | 角色卡 |
| OutlineAgent | 大纲生成 | 故事线 + 角色 | 分卷大纲 + 细纲 |
| WriterAgent | 章节撰写 | 细纲 + 上下文 | 正文 |
| ReviewerAgent | 审核修改 | 章节 + 反馈 | 修改建议 |

#### 2.2 WriterAgent增强
- 内置RAG调用
- 上下文压缩
- 自动扩写

### 阶段三：Skill重新设计 (Skill Redesign)

#### 3.1 Skill结构
```
novel-writer/
├── SKILL.md              # 主技能定义
├── scripts/
│   ├── write_file.py     # 文本写入（编码处理）
│   ├── novel_manager.py  # 小说项目管理
│   ├── rag_pipeline.py   # RAG流程
│   └── workflow_runner.py # 工作流运行器
└── templates/
    ├── world_template.md
    ├── character_template.md
    ├── outline_template.md
    └── chapter_template.md
```

#### 3.2 工作流状态机
```
需求分析 → 世界观构建 → 角色设计 → 冲突伏笔设计
    ↓            ↓            ↓            ↓
  [确认]      [确认]       [确认]       [确认]
    ↓            ↓            ↓            ↓
剧情大纲 → 细纲撰写 → 章节写作 → 审核修改
    ↓            ↓            ↓            ↓
  [确认]      [确认]       [反馈]       [确认/重写]
                              ↓            ↓
                          重写章节    调整框架
                              ↓            ↓
                          [完成]    迭代修改
```

### 阶段四：集成与测试 (Integration)

#### 4.1 Skill与后端集成
- Skill调用后端API
- 后端Agent处理复杂生成
- WebSocket推送进度

#### 4.2 反馈系统
- 章节重写请求
- 框架调整请求
- 文风修改请求

---

## 四、文件改造清单

### 新增文件
| 文件 | 描述 |
|------|------|
| `backend/app/workflow_engine.py` | 工作流引擎核心 |
| `backend/app/context_manager.py` | 上下文管理（RAG+压缩） |
| `backend/app/file_manager.py` | 结构化文件存取 |
| `backend/app/agents/world_builder.py` | 世界观构建Agent |
| `backend/app/agents/plot_designer.py` | 冲突伏笔设计Agent |
| `backend/app/agents/reviewer.py` | 审核Agent |
| `backend/app/models/feedback.py` | 反馈数据模型 |
| `backend/app/schemas/feedback.py` | 反馈Schema |
| `backend/app/services/revision_service.py` | 修改服务 |
| `novel-writer/scripts/novel_manager.py` | Skill文件管理器 |
| `novel-writer/scripts/rag_pipeline.py` | Skill RAG流程 |
| `novel-writer/scripts/workflow_runner.py` | Skill工作流运行 |

### 修改文件
| 文件 | 修改内容 |
|------|----------|
| `backend/app/workflows/novel_workflow.py` | 重构为统一工作流 |
| `backend/app/agents/writer.py` | 增强RAG+上下文压缩 |
| `backend/app/services/workflow_service.py` | 集成新工作流引擎 |
| `backend/app/core/redis_client.py` | 增强状态管理 |
| `novel-writer/SKILL.md` | 完全重写 |
| `novel-writer.skill` | 重新打包 |

---

## 五、实施计划

### 第1周：基础设施
- [ ] 创建 `workflow_engine.py`
- [ ] 创建 `context_manager.py`
- [ ] 创建 `file_manager.py`
- [ ] 完善 `redis_client.py` 状态管理
- [ ] 更新数据模型和Schema

### 第2周：Agent开发
- [ ] 实现 `world_builder.py`
- [ ] 实现 `plot_designer.py`
- [ ] 实现 `reviewer.py`
- [ ] 增强 `writer.py` (RAG+压缩)
- [ ] 更新 `base.py`

### 第3周：Skill重构
- [ ] 重写 `novel-writer/SKILL.md`
- [ ] 实现 `novel_manager.py`
- [ ] 实现 `rag_pipeline.py`
- [ ] 实现 `workflow_runner.py`
- [ ] 创建模板文件

### 第4周：集成与测试
- [ ] Skill与后端API集成
- [ ] 反馈系统实现
- [ ] WebSocket进度推送
- [ ] 端到端测试
- [ ] 文档完善

---

## 六、技术细节

### 上下文压缩策略
```python
# 当上下文超过阈值时，启用压缩
MAX_CONTEXT_TOKENS = 8000
COMPRESSION_STRATEGIES = {
    "recent": "保留最近N章",
    "important": "保留高重要性事件",
    "mystery": "保留未解伏笔",
    "character": "保留角色状态变化"
}
```

### 错误恢复策略
```python
ERROR_RECOVERY = {
    "rate_limit": {"retry": True, "backoff": "exponential", "max_retries": 3},
    "timeout": {"retry": True, "backoff": "linear", "max_retries": 2},
    "invalid_json": {"retry": True, "fallback": "extract_content"},
    "consistency_error": {"retry": False, "flag": "needs_review"}
}
```

### 文件结构规范
```markdown
novels/{project_id}/
├── metadata.json           # 项目元信息
├── 00_作品设定.json        # 类型/风格/卖点
├── 01_世界观设定.json      # 世界观
├── 02_角色设定.json         # 角色卡
├── 03_故事线.json          # 冲突/伏笔
├── 04_分卷大纲/
│   └── 第X卷.json
├── 05_章节细纲/
│   └── 第X卷/
│       └── 第XXX章.json
├── 06_正文/
│   └── 第X卷/
│       └── 第XXX章.md
└── .novel_history/        # 版本历史
    └── revisions/
```

---

## 七、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| LLM调用不稳定 | 生成失败 | 指数退避重试 + 降级策略 |
| 上下文丢失 | 工作流中断 | Redis持久化 + 定期保存 |
| JSON解析失败 | 数据损坏 | 备用提取 + 数据校验 |
| 循环依赖 | 系统死锁 | 状态机验证 + 循环检测 |

---

**最后更新**: 2026-03-30 12:21 GMT+8
**状态**: 🚧 改造中
