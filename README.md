# KimiFiction - 多智能体小说生成系统

基于多智能体协作的网络小说大模型生成系统，能够分析用户期望的小说类型，与用户商讨剧情走向和人物设计，生成世界观设定与剧情大纲，并自动撰写章节。支持 100~1000 章的长篇小说创作而不遗忘设定，并配套完整的**世界观可视化**、**实体管理**与 **RL 训练 / LLM 评测**闭环。

## ✨ 核心特性

- 🤖 **多智能体协作** - 类型分析、世界观构建、角色设计、剧情设计、大纲生成、章节撰写、一致性检查、记忆管理等 12+ Agent，按 6 阶段工作流推进
- 🧠 **长文本记忆** - RAG 向量检索(Qdrant) + 分层摘要，1000 章不遗忘
- 🗺️ **世界观可视化** - 实体图谱、小说地图、知识库三页联动，世界观设定可看可查
- 📦 **实体管理** - 角色/势力/功法/物品/地点五类实体 + 关系边，支持批量管理
- 🏆 **写作质量管线** - 分场景生成(3×~1000字) + 确定性硬门禁 + 定向重写 + 异构盲评 + 三尺度诊断指标；LLM-as-Judge 八维评测 + 评测规则优化
- 💬 **实时交互** - WebSocket 实时推送生成进度
- 🚀 **后台任务队列** - 异步处理阶段与章节生成，失败自动重试
- 📤 **数据导出** - 支持 TXT、Markdown、JSON、角色设定、大纲
- 🔌 **多模型接入** - DeepSeek 直连(默认)/ OpenAI / chat2api(Kimi/元宝)/ 本地 Ollama / 本地 GGUF(Qwen)
- ⚙️ **全流程驱动脚本** - `run_novel_pipeline.py` 支持 design/full/status 与断点续跑、`--watch` 守护

## 🚀 快速开始

### 环境依赖

- Docker(MySQL / Redis / Qdrant)
- Python 3.10+、Node.js 18+

### 1. 启动基础设施

```bash
docker-compose up -d
```

| 服务 | 端口 | 用途 | 必需 |
|------|------|------|------|
| MySQL | 3306 | 数据库存储 | ✅ |
| Redis | 6379 | 状态缓存/任务队列 | ✅ |
| Qdrant | 6333/6334 | 向量数据库(RAG) | ⚠️ 可选，缺省时用关键词检索兜底 |

### 2. 配置 LLM

```bash
# 复制并编辑 backend/.env（默认就是 DeepSeek 直连）
cp backend/.env.example backend/.env
# 填入 DEEPSEEK_API_KEY=sk-xxx
```

也可切换为 OpenAI / chat2api / 本地模型，见下方[配置说明](#-配置说明)。

### 3. 启动前后端

```bash
# 后端（端口 8080）
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

# 前端（端口 5173，已代理到 8080）
cd ../frontend
npm install
npm run dev
```

Windows 也可直接运行 `start.bat`。

### 4. 访问

- **前端界面**: http://localhost:5173
- **API 文档**: http://localhost:8080/docs

注册账号后，在「工作台」创建小说即可开始；或使用**全流程脚本**一键跑通设计阶段：

```bash
python scripts/run_novel_pipeline.py design --title "我的小说" --genre "都市修真" --idea "主角是..."
```

详细见 [QUICKSTART.md](QUICKSTART.md) 与 [USER_GUIDE.md](USER_GUIDE.md)。

## 📖 创作流程

1. **创建小说** - 输入标题与初始想法，AI 分析类型风格
2. **分阶段创作** - 需求分析 → 世界观构建 → 角色设计 → 剧情设计 → 大纲草案 → 大纲细化
3. **自动撰写** - 批量生成章节，实时查看进度，失败自动重试
4. **可视化世界** - 在实体图谱 / 小说地图 / 知识库中查看与修正世界观设定
5. **质量保障** - 章节写入经确定性硬门禁(字数/结尾/场景均衡/角色名白名单等)，未过则定向重写 ≤1 次，仍不过标记 flagged；LLM 盲评打分与三尺度诊断指标写入元数据
6. **评测** - 用 LLM-as-Judge 八维评测章节质量，评测规则可迭代优化
7. **导出阅读** - 导出 TXT/Markdown/JSON，在任意设备阅读

## 🏗️ 系统架构

```
前端(React 5173) → 后端(FastAPI 8080) → 智能体工作流(LangGraph) → MySQL / Redis / Qdrant
                                                          ↓
                                      LLM(DeepSeek / OpenAI / chat2api / 本地Qwen)
```

多智能体按 6 阶段顺序执行，章节写入后自动做实体抽取(可配)与可选 Rubric 评测，评测结果进入训练数据闭环。

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, TypeScript, Tailwind CSS, Vite, ReactFlow |
| 后端 | FastAPI, SQLAlchemy, Pydantic, Redis 任务队列 |
| 智能体 | LangGraph, 自定义 Agent 框架(12+ Agent) |
| 数据库 | MySQL 8.0, Redis 7, Qdrant |
| LLM | DeepSeek / OpenAI / Kimi / 腾讯元宝 / Ollama / 本地 Qwen GGUF |
| 质量 | 硬门禁(确定性规则), 分场景生成, LLM-as-Judge 盲评, 三尺度诊断 |
| 部署 | Docker Compose |

## 📁 项目结构

```
KimiFiction/
├── backend/                 # FastAPI 后端（端口 8080）
│   ├── main.py             # 应用入口
│   └── app/
│       ├── agents/         # 12+ 智能体（world_builder/writer/reviewer/...）
│       ├── api/endpoints/  # 15 组 REST API（auth/novels/entities/training/...）
│       ├── core/           # 配置、数据库、Redis、向量库、任务队列
│       ├── models/         # 数据模型（含 entity/rubric/feedback）
│       ├── schemas/        # Pydantic 模型
│       ├── services/       # 业务逻辑（实体抽取/检索/评测/记忆/训练数据收集）
│       ├── training/       # RL 训练（grpo/imitation/llm_judge/tpo/lora/audit）
│       ├── rl_training/    # 兼容层（重导出）
│       └── workflows/      # LangGraph 工作流
├── frontend/               # React 前端（端口 5173）
│   └── src/
│       ├── pages/          # 24 个页面（实体图谱/小说地图/知识库/评测/训练...）
│       ├── components/     # 通用组件
│       └── services/       # API 服务
├── scripts/                # 驱动脚本（全流程管线/种子数据/验证截图/评测）
├── chat2api_service/       # 本地 chat2api 服务（可选，Kimi/元宝等）
└── docs/                   # 专项文档（调用链/集成计划/测试报告等）
```

## 📚 文档

- [快速开始](QUICKSTART.md) - 5 分钟启动与第一本小说
- [用户指南](USER_GUIDE.md) - 完整使用说明（含世界观可视化/评测/训练）
- [LLM 调用链说明](docs/LLM_CALL_CHAIN.md) - 全链路调用次数与成本估算
- [评测系统集成计划](docs/INTEGRATION_PLAN.md) - 评测系统演进记录
- [Chat2Api 使用](CHAT2API_USAGE.md) - 本地 chat2api 配置（Kimi/元宝）
- [API 文档](http://localhost:8080/docs) - 启动后访问

## ⚙️ 配置说明

### LLM 提供方（backend/.env）

| Provider | 说明 |
|----------|------|
| `deepseek`（默认） | 直连 DeepSeek API，高性价比；可指向联影网关并使用 `DeepSeek-V4-Flash` |
| `openai` | 标准 OpenAI API |
| `kimi` / `yuanbao` | 经本地 `chat2api_service`（端口 8000）代理 |
| `local_llama` | Ollama 本地模型 |
| `local_qwen` | 直接加载 GGUF 模型（qwen-2b / qwen-35b），用于训练 |

### 关键环境变量

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

MYSQL_HOST=localhost          # MySQL 配置
REDIS_HOST=localhost          # Redis 配置
QDRANT_HOST=localhost         # Qdrant 配置（可选）
EMBEDDING_MODEL=bge-large-zh  # 向量模型，维度 1024

PORT=8080                     # 后端端口
MAX_CHAPTERS=1000
DEFAULT_CHAPTER_WORDS=3000

RUN_POST_WRITE_RUBRIC=false   # 每章写入后是否跑八维评测（8 次 LLM 调用，默认关）
RUN_POST_WRITE_ENTITY_EXTRACTION=true  # 每章写入后自动抽取实体
```

## 🎯 功能一览

### 创作工作台
- 新建小说、多阶段工作流、章节撰写/阅读、大纲编辑、角色管理、导出
- 章节写入后自动实体抽取，新实体/关系回流到知识库

### 世界观可视化（三页）
- **实体图谱** - 实体与关系力导向图，节点点击看详情，支持自定义节点
- **小说地图** - 地点实体与剧情路线可视化
- **知识库** - 记忆节点、设定、大纲的统一检索视图

### 写作质量保障（V2 管线，开关 `WRITING_PIPELINE_V2`）
- **分场景生成** - 场景节拍规划(1×JSON) → 3 场景逐段生成(~1000字/段) → 规则化缝合
- **确定性硬门禁** - 字数达成率/结尾终止/场景均衡/角色名白名单/力量等级白名单/伏笔台账；未过则定向重写 ≤1 次，仍不过标记 `flagged` 待人工
- **反模板化** - 章节类型池(冲突/过渡/情绪/信息/群像)，禁止连续 3 章同型
- **风格锚点** - 小说级 `style_profile` few-shot 样本注入（无样本则降级不注入）
- **异构盲评** - 匿名审稿人视角打分（换 persona + 温度），打破"自产自评"
- **三尺度诊断** - 句长方差 / AI 高频词命中 / 段落熵 / 总结句密度 / 跨章开头相似度 / 情绪曲线相关（仅诊断，不入 reward）
- **成本熔断** - 单章 LLM 调用预算，超限跳过重写直接标记

### 评测系统
- **LLM-as-Judge 八维评测**（情节/风格/逻辑/角色/世界观/叙事等，权重可配）
- **评测规则优化器** - 根据历史评测迭代评判规则
- **伏笔台账** - 伏笔埋设/回收/超期检测，防止设定遗忘

### 运维能力
- WebSocket 实时进度、任务队列、状态快照、失败自动重试与退避
- `scripts/run_novel_pipeline.py` 全流程批处理，支持 `--from-phase` 断点续跑
- `scripts/seed_demo_world.py <novel_id>` 灌入演示世界观便于可视化验收

## 📝 开发计划

- [x] 基础框架搭建（前后端/Docker）
- [x] 多智能体协作系统（12+ Agent / 6 阶段工作流）
- [x] 长文本记忆管理（RAG + 分层摘要）
- [x] WebSocket 实时通信与任务队列
- [x] 用户认证系统（JWT）
- [x] 数据导出功能（TXT/Markdown/JSON/角色/大纲）
- [x] Chat2Api 与多模型接入（DeepSeek/OpenAI/Kimi/元宝/本地）
- [x] 本地模型支持（Qwen GGUF）与硬件配置自适应
- [x] 角色关系图谱可视化（实体图谱）
- [x] EPUB 导出
- [x] RL 训练系统移除（GRPO/TPO/模仿/LoRA 已清理，评测与数据工具保留）
- [x] 世界观可视化三页（实体图谱/小说地图/知识库）与实体管理
- [x] 全流程创作脚本与世界观注入资产
- [x] 写作质量管线 V2（分场景/硬门禁/盲评/诊断指标/反模板化/风格锚点/成本熔断）
- [ ] 更多图表类型（时间线、情感曲线等）
- [ ] 集成测试覆盖与性能基准
- [ ] 细粒度人工干预
