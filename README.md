# NovelGen - 多智能体小说生成系统

基于多智能体协作的网络小说大模型生成系统，能够分析用户期望的小说类型，与用户商讨剧情走向和人物设计，生成剧情大纲，并自动撰写章节，支持100~1000章的长篇小说创作而不会遗忘剧本。

## ✨ 核心特性

- 🤖 **7个AI智能体协作** - 类型分析、剧情讨论、角色设计、大纲生成、章节撰写、一致性检查、记忆管理
- 🧠 **长文本记忆** - 分层摘要 + 向量检索，1000章不遗忘
- 💬 **实时交互** - WebSocket实时推送生成进度
- 🚀 **后台任务队列** - 异步处理章节生成
- 👤 **用户认证** - JWT安全认证系统
- 📤 **数据导出** - 支持TXT、Markdown、JSON格式
- 🔌 **双模式LLM** - 支持OpenAI API或本地Chat2Api Service

## 🚀 快速开始

### 方式一：使用 OpenAI API（5分钟）

```bash
# 1. 克隆项目
git clone <repository-url>
cd KimiFiction

# 2. 配置API Key
# 编辑 backend/.env，设置 OPENAI_API_KEY=sk-your-key

# 3. 启动
chmod +x start.sh && ./start.sh  # Linux/Mac
# 或
start.bat  # Windows

# 4. 访问 http://localhost:5173
```

### 方式二：使用免费AI（Kimi/DeepSeek）

```bash
# 1. 启动 Chat2Api Service
cd chat2api_service
pip install -r requirements.txt
playwright install
python main.py

# 2. 在浏览器中访问 http://localhost:8000 完成登录

# 3. 启动 NovelGen
cd .. && ./start.sh  # 选择选项 2
```

详细文档：[QUICKSTART.md](QUICKSTART.md) | [USER_GUIDE.md](USER_GUIDE.md)

## 📖 使用流程

1. **创建小说** - 输入标题，点击创建
2. **与AI讨论** - 描述你的想法，AI分析类型和风格
3. **生成角色** - AI自动创建主角、反派、配角
4. **生成大纲** - AI创建三卷大纲，每卷100章
5. **自动撰写** - AI开始生成章节，实时查看进度
6. **导出阅读** - 导出TXT/Markdown，在任意设备阅读

## 🏗️ 系统架构

```
前端(React) → 后端(FastAPI) → 智能体(LangGraph) → 数据库(MySQL/Redis/Qdrant)
                                                    ↓
                                              LLM(OpenAI/Chat2Api)
```

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, TypeScript, Tailwind CSS, Vite |
| 后端 | FastAPI, SQLAlchemy, Pydantic |
| 智能体 | LangGraph, 自定义Agent框架 |
| 数据库 | MySQL 8.0, Redis 7, Qdrant |
| LLM | OpenAI API / Kimi / DeepSeek / 腾讯元宝 |
| 部署 | Docker Compose |

## 📁 项目结构

```
KimiFiction/
├── backend/              # FastAPI后端
│   ├── app/
│   │   ├── agents/      # AI智能体
│   │   ├── api/         # API路由
│   │   ├── core/        # 核心配置
│   │   ├── models/      # 数据库模型
│   │   ├── services/    # 业务逻辑
│   │   └── workflows/   # LangGraph工作流
│   └── main.py
├── frontend/             # React前端
│   └── src/
│       ├── pages/       # 页面组件
│       └── services/    # API服务
├── chat2api_service/     # 本地AI服务（可选）
└── docker-compose.yml
```

## 📚 文档

- [快速开始](QUICKSTART.md) - 5分钟启动指南
- [用户指南](USER_GUIDE.md) - 完整使用说明
- [Chat2Api使用](CHAT2API_USAGE.md) - 本地AI配置
- [API文档](http://localhost:8000/docs) - 启动后访问

## ⚙️ 配置说明

### 环境变量

```bash
# backend/.env

# LLM配置（二选一）
LLM_PROVIDER=openai                    # 或 kimi/deepseek/yuanbao
OPENAI_API_KEY=sk-your-key             # OpenAI模式需要
CHAT2API_BASE_URL=http://localhost:8000 # Chat2Api模式需要

# 数据库配置
MYSQL_HOST=localhost
MYSQL_USER=novel_user
MYSQL_PASSWORD=novel_password

# 其他配置
MAX_CHAPTERS=1000
DEFAULT_CHAPTER_WORDS=3000
```

## 🎯 功能演示

### 工作台
![工作台](docs/images/dashboard.png)

### AI对话创作
![AI对话](docs/images/chat.png)

### 章节阅读器
![阅读器](docs/images/reader.png)

## 📝 开发计划

- [x] 基础框架搭建
- [x] 多智能体协作系统
- [x] 长文本记忆管理
- [x] WebSocket实时通信
- [x] 任务队列系统
- [x] 用户认证系统
- [x] 数据导出功能
- [x] Chat2Api集成
- [ ] 角色关系图谱可视化
- [ ] EPUB格式导出
- [ ] 细粒度人工干预

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph) - 智能体编排框架
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能Web框架
- [React](https://react.dev/) - 前端框架

---

开始创作你的小说吧！🚀
