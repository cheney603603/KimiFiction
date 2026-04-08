# NovelGen 使用指南

## 目录
1. [系统部署](#系统部署)
2. [初始配置](#初始配置)
3. [日常使用](#日常使用)
4. [故障排除](#故障排除)

---

## 系统部署

### 方法一：Docker Compose 部署（推荐）

#### 1. 环境准备

确保已安装：
- Docker (20.10+)
- Docker Compose (2.0+)
- Git

#### 2. 克隆项目

```bash
git clone <repository-url>
cd KimiFiction
```

#### 3. 配置环境变量

```bash
# 复制配置文件
cp backend/.env.example backend/.env

# 编辑配置
nano backend/.env  # 或使用你喜欢的编辑器
```

#### 4. 选择 LLM 模式并配置

**方案 A：使用 OpenAI API（推荐用于生产环境）**

```bash
# backend/.env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4-turbo-preview
```

**方案 B：使用 Chat2Api Service（推荐用于开发/测试）**

```bash
# backend/.env
LLM_PROVIDER=kimi  # 可选: kimi, deepseek, yuanbao
CHAT2API_BASE_URL=http://host.docker.internal:8000
```

#### 5. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 等待数据库初始化完成（约30秒）
```

#### 6. 访问系统

- **前端界面**: http://localhost:5173
- **API文档**: http://localhost:8000/docs
- **后端API**: http://localhost:8000

---

### 方法二：手动部署

#### 1. 启动基础设施

```bash
# 启动 MySQL
docker run -d \
  --name novel_mysql \
  -e MYSQL_ROOT_PASSWORD=root_password \
  -e MYSQL_DATABASE=novel_system \
  -e MYSQL_USER=novel_user \
  -e MYSQL_PASSWORD=novel_password \
  -p 3306:3306 \
  mysql:8.0

# 启动 Redis
docker run -d \
  --name novel_redis \
  -p 6379:6379 \
  redis:7-alpine

# 启动 Qdrant
docker run -d \
  --name novel_qdrant \
  -p 6333:6333 \
  qdrant/qdrant:latest
```

#### 2. 启动后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（编辑 .env 文件）
cp .env.example .env

# 启动服务
python main.py
# 或使用 uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

---

### 方法三：使用 Chat2Api Service（本地AI）

如果你不想使用 OpenAI API，可以使用本地 Chat2Api Service。

#### 1. 启动 Chat2Api Service

```bash
cd chat2api_service

# 安装依赖
pip install -r requirements.txt
playwright install

# 启动服务
python main.py
```

#### 2. 完成登录

1. 访问 http://localhost:8000
2. 选择要使用的 AI（Kimi/DeepSeek/腾讯元宝）
3. 点击"打开登录页面"
4. 在浏览器中完成登录
5. 点击"确认已登录"

#### 3. 配置 NovelGen 使用 Chat2Api

```bash
# backend/.env
LLM_PROVIDER=kimi  # 根据你登录的AI选择
CHAT2API_BASE_URL=http://localhost:8000
OPENAI_API_KEY=not-needed-for-chat2api
```

#### 4. 启动 NovelGen

```bash
docker-compose up -d
```

---

## 初始配置

### 1. 注册管理员账号

1. 访问 http://localhost:5173
2. 点击"立即注册"
3. 填写用户名、邮箱、密码
4. 完成注册

### 2. 登录系统

1. 访问 http://localhost:5173/login
2. 输入用户名和密码
3. 点击登录

---

## 日常使用

### 创建新小说

1. **进入工作台**
   - 登录后自动进入工作台
   - 或点击顶部导航"工作台"

2. **创建小说**
   - 点击"新建小说"按钮
   - 输入小说标题
   - 点击"创建"

3. **与AI协商剧情**
   - 点击"继续创作"
   - 在聊天界面描述你的想法：
     - "我想写一个玄幻修仙小说"
     - "主角是一个废柴少年"
     - "要有退婚流、金手指元素"
   
4. **确认类型**
   - AI会分析你的需求并推荐类型
   - 确认或修改类型建议

5. **讨论剧情**
   - 与AI讨论主线剧情
   - 确定世界观设定
   - 讨论关键转折点

6. **生成角色**
   - 点击"生成角色设计"
   - AI会自动创建主角、反派、配角
   - 查看和编辑角色人设

7. **生成大纲**
   - 点击"生成剧情大纲"
   - AI会创建三卷大纲
   - 查看分卷结构和剧情弧

8. **开始写作**
   - 点击"开始自动撰写"
   - 选择自动模式或手动模式
   - AI开始生成章节

### 查看和管理小说

#### 阅读小说

1. 进入小说详情页
2. 点击"阅读小说"
3. 在章节列表中选择章节
4. 使用阅读器功能：
   - 调整字体大小
   - 切换夜间模式
   - 查看目录
   - 上一章/下一章

#### 管理角色

1. 进入"角色管理"
2. 查看所有角色卡片
3. 点击角色查看详情
4. 编辑角色信息
5. 查看角色时间线

#### 编辑大纲

1. 进入"大纲编辑"
2. 查看分卷结构
3. 展开剧情弧查看详情
4. 手动调整大纲（如果需要）

### 导出小说

1. 进入小说详情页
2. 点击右上角"导出"按钮
3. 选择导出格式：
   - **TXT**: 纯文本，适合阅读
   - **Markdown**: 带目录结构
   - **JSON**: 完整数据备份
   - **角色设定**: 导出所有角色
   - **大纲**: 导出剧情大纲

### 监控生成进度

1. 在"继续创作"页面查看实时状态
2. WebSocket会推送生成进度
3. 查看任务队列状态（API）

---

## 高级功能

### 手动触发章节生成

```bash
# 使用API直接生成章节
curl -X POST http://localhost:8000/api/v1/chapters/generate \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "novel_id": 1,
    "chapter_number": 10,
    "outline_guidance": "这一章主角要突破境界"
  }'
```

### 整理记忆（长文本优化）

当章节数超过50章时，建议整理记忆：

```bash
curl -X POST http://localhost:8000/api/v1/memory/consolidate/1 \
  -H "Authorization: Bearer your-token" \
  -d '{
    "chapter_threshold": 50
  }'
```

### 搜索记忆

```bash
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "Authorization: Bearer your-token" \
  -d '{
    "novel_id": 1,
    "query": "主角的武器",
    "top_k": 5
  }'
```

---

## 故障排除

### 问题1：无法连接到数据库

**症状**: 后端启动失败，报错"Can't connect to MySQL"

**解决**:
```bash
# 检查MySQL容器状态
docker ps | grep mysql

# 如果没有运行，启动它
docker start novel_mysql

# 或重新创建
docker-compose up -d mysql
```

### 问题2：LLM调用失败

**症状**: 生成章节时报错

**OpenAI模式**:
```bash
# 检查API Key
echo $OPENAI_API_KEY

# 测试API
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer your-api-key"
```

**Chat2Api模式**:
```bash
# 检查chat2api_service是否运行
curl http://localhost:8000/api/status

# 检查登录状态
curl http://localhost:8000/api/status/kimi
```

### 问题3：前端无法连接后端

**症状**: 页面加载但数据为空

**解决**:
1. 检查后端是否运行: `curl http://localhost:8000/health`
2. 检查CORS配置
3. 检查前端代理配置 `frontend/vite.config.ts`

### 问题4：章节生成卡住

**症状**: 任务状态一直是"pending"

**解决**:
```bash
# 检查Redis连接
docker exec novel_redis redis-cli ping

# 查看任务队列
docker logs novel_backend | grep "任务队列"

# 重启后端
docker-compose restart backend
```

### 问题5：内存不足（生成长小说时）

**解决**:
```bash
# 增加Docker内存限制
docker-compose down

# 编辑 docker-compose.yml，增加内存限制
# 然后重新启动
docker-compose up -d
```

---

## 最佳实践

### 1. 定期备份

```bash
# 备份数据库
docker exec novel_mysql mysqldump -u novel_user -p novel_system > backup.sql

# 备份小说数据（导出JSON）
curl http://localhost:8000/api/v1/export/novel/1/json \
  -H "Authorization: Bearer your-token" \
  > novel_backup.json
```

### 2. 监控资源使用

```bash
# 查看容器资源使用
docker stats

# 查看日志
docker-compose logs -f --tail=100
```

### 3. 优化生成速度

- 使用更快的LLM（如GPT-3.5-turbo代替GPT-4）
- 减少每章目标字数
- 使用本地Chat2Api Service避免网络延迟

### 4. 保持剧情连贯

- 每生成50章整理一次记忆
- 定期检查角色状态是否一致
- 使用"一致性检查"功能

---

## 常用命令速查

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 查看日志
docker-compose logs -f

# 重启后端
docker-compose restart backend

# 进入数据库
docker exec -it novel_mysql mysql -u novel_user -p novel_system

# 进入Redis
docker exec -it novel_redis redis-cli

# 更新代码后重建
docker-compose up -d --build
```

---

## 获取帮助

- **API文档**: http://localhost:8000/docs
- **项目文档**: 查看 README.md
- **Chat2Api文档**: 查看 CHAT2API_USAGE.md
- **提交Issue**: 在GitHub仓库提交问题
