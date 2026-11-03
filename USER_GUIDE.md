# KimiFiction 使用指南

## 目录
1. [系统部署](#系统部署)
2. [初始配置](#初始配置)
3. [日常使用](#日常使用)
4. [世界观可视化](#世界观可视化)
5. [评测与写作质量保障](#评测与写作质量保障)
6. [全流程脚本](#全流程脚本)
7. [故障排除](#故障排除)

---

## 系统部署

### 方法一：Docker Compose + 本地进程（推荐）

#### 1. 环境准备

- Docker (20.10+)、Docker Compose (2.0+)
- Python 3.10+、Node.js 18+

#### 2. 启动基础设施

```bash
docker-compose up -d
```

| 服务 | 端口 | 用途 | 必需 |
|------|------|------|------|
| MySQL | 3306 | 数据存储 | ✅ |
| Redis | 6379 | 状态缓存/任务队列 | ✅ |
| Qdrant | 6333/6334 | 向量检索(RAG) | ⚠️ 可选 |

> 不启动 Qdrant 时，记忆检索自动退化为关键词匹配。

#### 3. 配置 LLM

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，按需选择：

**方案 A：DeepSeek 直连（默认，推荐）**

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

**方案 B：OpenAI API**

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4-turbo-preview
```

**方案 C：chat2api 本地代理（Kimi / 腾讯元宝）**

```bash
# 另起终端启动 chat2api 服务
cd chat2api_service
pip install -r requirements.txt && playwright install
python main.py

# backend/.env
LLM_PROVIDER=kimi   # 或 yuanbao
CHAT2API_BASE_URL=http://localhost:8000
```

**方案 D：本地模型**

```bash
# Ollama
LLM_PROVIDER=local_llama
OLLAMA_BASE_URL=http://localhost:11434

# 直接加载 GGUF（qwen-2b / qwen-35b），用于训练
LLM_PROVIDER=local_qwen
LOCAL_MODEL_ID=qwen-35b
LOCAL_N_CTX=8192
```

#### 4. 启动前后端

```bash
# 后端（8080）
cd backend
pip install -r requirements.txt
python main.py

# 前端（5173，已代理到 8080）
cd ../frontend
npm install
npm run dev
```

#### 5. 访问系统

- **前端界面**: http://localhost:5173
- **API 文档**: http://localhost:8080/docs

---

## 初始配置

1. 访问 http://localhost:5173 ，点击「立即注册」，填写用户名/密码完成注册
2. 登录系统
3. （可选）在「设置 → LLM 配置」页核对/切换模型提供方
4. （可选）用脚本快速灌入演示世界观数据：

```bash
python scripts/seed_demo_world.py <novel_id> e2e_test_user Test123
```

---

## 日常使用

### 创建新小说

1. **进入工作台** → 登录后默认进入，或点顶部导航「工作台」
2. **创建小说** → 「新建小说」，输入标题，点击创建
3. **分阶段创作** → 进入小说详情 →「继续创作」：

   AI 依次执行 6 个阶段（可在工作流页实时查看进度）：
   - **需求分析** - 分析你的想法，推荐类型与风格
   - **世界观构建** - 生成地域、力量体系、势力等设定
   - **角色设计** - 创建主角、反派、配角人设
   - **剧情设计** - 设计主线、转折与爽点
   - **大纲草案 / 大纲细化** - 生成三卷大纲与章节级大纲

4. **自动撰写** → 点击「开始自动撰写」，选择自动/手动模式，AI 开始生成章节
5. **阅读** → 章节生成后可实时阅读，支持字号调整、夜间模式、上一章/下一章

### 查看和管理小说

- **阅读小说**：小说详情 →「阅读小说」→ 选择章节
- **管理角色**：「角色管理」→ 卡片式查看/编辑角色，查看角色时间线
- **编辑大纲**：「大纲编辑」→ 查看分卷结构、展开剧情弧、手动调整
- **导出小说**：详情页右上角「导出」→ TXT / Markdown / JSON / 角色设定 / 大纲
- **监控生成进度**：工作流页实时状态，或 `GET /api/v1/workflow/progress/{novel_id}`

### 管理实体（世界观数据）

实体共五类：`character`(角色)、`faction`(势力)、`skill`(功法)、`item`(物品)、`location`(地点)。

- **查看**：进入「实体管理」页，按类型筛选、搜索
- **新增/编辑**：填写名称、别名、类型、状态向量、叙事摘要
- **关系**：实体之间建立/编辑关系边（如「师徒」「敌对」）
- **批量删除**：勾选多个实体后批量删除
- **自动抽取**：每章写入后系统自动抽取实体与关系（`RUN_POST_WRITE_ENTITY_EXTRACTION=true`），无需手工录入

---

## 世界观可视化

三个页面共用后端聚合接口 `GET /api/v1/novels/{id}/world`（返回实体、关系、角色、记忆节点、大纲）。

### 实体图谱（`/novel/:id/graph`）

- 力导向图展示实体与关系，节点按类型着色
- 点击节点查看详情，支持自定义/新增节点
- 地图可缩放拖拽，关系边实时联动

### 小说地图（`/novel/:id/map`）

- 地点类实体（location）与剧情路线的可视化
- 查看各地点的设定与关联事件/角色

### 知识库（`/novel/:id/knowledge`）

- 记忆节点、世界观设定、大纲的统一检索视图
- 支持按类型/关键词过滤，是长文本记忆的入口

> 提示：实体图谱/地图/知识库若为空，先用 `seed_demo_world.py` 灌入演示数据，或确认已走过「世界观构建/角色设计」阶段。

---

## 评测与写作质量保障

### LLM 八维评测

「评测」页支持：

- **小说章节评测**：选小说 → 章节号 → 运行评测
- **文本评测**：粘贴任意文本
- **参考作品评测**：选择 `evaluate_rules_llm.csv` 规则集或参考文件

八维维度（权重可配）：情节一致性、风格匹配度、逻辑合理性、角色一致性、世界观一致性、叙事流畅度等，输出总分/等级/雷达图，评测历史可追溯。

**相关 API**：`POST /api/v1/training/evaluate/{novel_id}`、`/api/v1/training/evaluation/run`、`/evaluation/history`。

### 评测规则优化器（`/evaluation/optimizer`）

根据历史评测结果与失败样本，自动迭代 LLM 评判规则（`evaluate_rules_llm.csv`），减少误判，提升评测稳定性。

### 写作质量管线 V2（`WRITING_PIPELINE_V2=true` 时启用）

章节撰写走「场景节拍规划 → 逐场景生成(3×~1000字) → 规则化缝合」：

- **确定性硬门禁**：字数达成率、结尾终止、场景均衡、角色名白名单、力量等级白名单、伏笔台账；未过则定向重写 ≤1 次，仍不过标记 `flagged`（章节状态为 flagged，待人工复审）
- **反模板化**：章节类型池（冲突/过渡/情绪/信息/群像），禁止连续 3 章同型
- **风格锚点**：小说 `style_profile.samples` 中的真人样本作为 few-shot 注入（无样本则不注入）
- **异构盲评**：匿名审稿人 persona 打分（`score/naturalness/looks_ai`），打破同模型自评闭环
- **三尺度诊断**：句长方差、AI 高频词命中、段落熵、总结句密度、跨章开头相似度、情绪曲线相关 —— 写入章节元数据，仅供人工查看，不参与打分
- **成本熔断**：单章 LLM 调用预算（`llm_call_budget_per_chapter`，默认 8），超限跳过重写直接标记

### 伏笔台账

- 从剧情设定的 `unresolved_mysteries / foreshadowing` 自动埋设伏笔
- 每章写入时检查超期未回收项（默认 10 章内应回收），超期进入硬门禁告警

### 状态快照

「快照」页可对小说创作进度保存/恢复快照，便于回溯实验。

---

## 全流程脚本

`scripts/run_novel_pipeline.py` 面向无人值守批处理，默认账号 `e2e_test_user / Test123`：

```bash
# 设计阶段（6 阶段顺序执行）
python scripts/run_novel_pipeline.py design --title "修真大佬重返都市" --genre "都市修真" --idea "主角..."

# 批量写章节（每章完成后自动落库到 logs/chXXX.txt）
python scripts/run_novel_pipeline.py chapters --novel <id> --from 1 --count 5 --until 100

# 查看进度
python scripts/run_novel_pipeline.py status --novel <id>

# 断点续跑（跳过已完成阶段）
python scripts/run_novel_pipeline.py design --novel <id> --from-phase world_building
```

内置机制：阶段/章节失败自动重试（指数退避）、连续失败休息 10 分钟缓解网关压力、章节「任务态+是否入库」双判定。

其他脚本：

- `scripts/seed_demo_world.py <novel_id>` - 灌入演示世界观
- `scripts/verify_world_pages.py` / `screenshot_world_pages.py` - 可视化页面验收
- `scripts/comprehensive_test.py` / `scripts/e2e_uiai.py` - 端到端测试

---

## 故障排除

### 问题 1：无法连接到数据库

```bash
docker ps | grep mysql          # 检查容器
docker-compose up -d mysql      # 重新拉起
```

### 问题 2：LLM 调用失败

- DeepSeek：检查 `DEEPSEEK_API_KEY`；非流式请求 >1000 字节会被网关拒绝，应用已改流式调用
- chat2api：`curl http://localhost:8000/api/status/kimi` 检查登录态
- 本地模型：确认模型路径与显存配置（CPU 模式设 `LOCAL_N_GPU_LAYERS=0`）

### 问题 3：前端连不上后端

- 检查后端是否运行：`curl http://localhost:8080/health`
- 前端 5173 已代理 `/api` 到 8080；若改端口需同步修改 `frontend/vite.config.ts`
- 检查 CORS：`backend/.env` 的 `CORS_ORIGINS` 需包含 `http://localhost:5173`

### 问题 4：章节生成卡住/失败

- 检查 Redis：`docker exec kimi_redis redis-cli ping`
- 查看任务状态：`GET /api/v1/workflow/task-progress/{task_id}`
- 查看日志：`logs/app.log`，或 `docker-compose logs -f backend`
- 全流程脚本自带重试，普通界面触发失败可稍后重试

### 问题 5：实体图谱连线不显示

- 确认节点已建立关系边（实体管理页可见 relationship）
- 前端自定义节点需挂载 Handle 组件（`96f2783` 已修复默认场景）

---

## 常用命令速查

```bash
# 启动基础设施
docker-compose up -d

# 启动后端（8080）
cd backend && python main.py

# 启动前端（5173）
cd frontend && npm run dev

# 停止/查看日志
docker-compose down
docker-compose logs -f

# 进入数据库
docker exec -it kimi_mysql mysql -u novel_user -p novel_system

# 进入 Redis
docker exec -it kimi_redis redis-cli

# 全流程脚本
python scripts/run_novel_pipeline.py status --novel <id>
```

---

## 获取帮助

- **API 文档**: http://localhost:8080/docs
- **项目文档**: [README.md](README.md) / [QUICKSTART.md](QUICKSTART.md)
- **Chat2Api**: [CHAT2API_USAGE.md](CHAT2API_USAGE.md)
- **调用链与成本**: [docs/LLM_CALL_CHAIN.md](docs/LLM_CALL_CHAIN.md)
- **提交 Issue**: GitHub 仓库
