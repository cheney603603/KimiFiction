# KimiFiction 快速开始

5 分钟内启动系统并创作你的第一本小说。

## 一、环境准备

- Docker（提供 MySQL / Redis / Qdrant）
- Python 3.10+、Node.js 18+

```bash
# 启动基础设施（MySQL/Redis/Qdrant）
docker-compose up -d
```

## 二、配置 LLM（推荐 DeepSeek 直连）

```bash
# 复制配置
cp backend/.env.example backend/.env

# 编辑 backend/.env，填入你的 Key
DEEPSEEK_API_KEY=sk-your-deepseek-key
```

> 使用 OpenAI / chat2api(Kimi/元宝) / 本地模型的方式见 [README 配置说明](README.md#-配置说明)。

## 三、启动前后端

```bash
# 后端（端口 8080）
cd backend
pip install -r requirements.txt
python main.py          # 或 uvicorn main:app --reload --port 8080

# 前端（新终端，端口 5173）
cd ../frontend
npm install
npm run dev
```

Windows 也可双击 `start.bat`。

## 四、创建你的第一本小说

1. **访问系统** → http://localhost:5173 ，注册账号并登录
2. **创建小说** → 「工作台」→「新建小说」，输入标题，例如《我的修仙传》
3. **分阶段创作** → 在小说详情页进入工作流，依次完成需求分析、世界观构建、角色设计、剧情设计、大纲草案、大纲细化
4. **自动撰写** → 「开始自动撰写」，AI 批量生成章节；在「阅读」中查看内容
5. **查看世界** → 「实体图谱」「小说地图」「知识库」查看世界观设定与实体关系

## 五、全流程脚本（批处理/无人值守）

设计阶段一键跑通（约十几分钟，含 6 个阶段）：

```bash
python scripts/run_novel_pipeline.py design --title "我的修仙传" --genre "都市修真" --idea "主角..."
```

批量写章节：

```bash
python scripts/run_novel_pipeline.py chapters --novel <id> --from 1 --count 5
# 或写到指定章: --until 100
```

查看进度 / 断点续跑：

```bash
python scripts/run_novel_pipeline.py status --novel <id>
python scripts/run_novel_pipeline.py design --novel <id> --from-phase world_building
```

脚本内置失败自动重试与退避（连续失败休息缓解网关压力），产出物在 `logs/` 下。

灌入演示世界观数据（可视化验收用）：

```bash
python scripts/seed_demo_world.py <novel_id> e2e_test_user Test123
```

> 脚本默认使用测试账号 `e2e_test_user / Test123`，可在脚本头部修改。

## 常用操作

### 导出小说

进入小说详情页 → 右上角「导出」→ 选择 TXT / Markdown / JSON / 角色设定 / 大纲。

### 评测章节质量

「评测」页 → 选择小说或上传文本 → 查看八维评分（情节一致性/风格匹配/逻辑/角色/世界观/叙事流畅度等）。

### 管理实体与世界观

- 「实体管理」：五类实体（角色/势力/功法/物品/地点）的增删改查与批量删除
- 「知识库」：记忆节点与设定的统一检索
- 「实体图谱」：实体关系图，可拖动、点击查看详情

### 章节质量保障

- 「评测」页可对章节做八维 LLM 评测
- 章节写入自动过确定性硬门禁（字数/结尾/场景/角色名等），未过则定向重写 ≤1 次，仍不过标记 `flagged`
- 写作管线 V2（分场景生成）在 `backend/.env` 设 `WRITING_PIPELINE_V2=true` 后启用

## 停止服务

```bash
docker-compose down
# 查看日志
docker-compose logs -f
```

## 需要帮助？

- **详细文档**: [USER_GUIDE.md](USER_GUIDE.md)
- **Chat2Api 说明**: [CHAT2API_USAGE.md](CHAT2API_USAGE.md)
- **API 文档**: http://localhost:8080/docs
