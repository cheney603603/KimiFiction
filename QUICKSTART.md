# NovelGen 快速开始

## 5分钟快速启动

### 方式一：使用 OpenAI API（最简单）

```bash
# 1. 克隆项目
git clone <repository-url>
cd KimiFiction

# 2. 配置API Key
# 编辑 backend/.env，设置你的 OpenAI API Key
# OPENAI_API_KEY=sk-your-key-here

# 3. 启动（Linux/Mac）
chmod +x start.sh
./start.sh
# 选择选项 1

# 3. 启动（Windows）
start.bat
# 选择选项 1
```

### 方式二：使用免费AI（Kimi/DeepSeek）

```bash
# 1. 启动 Chat2Api Service（另一个终端）
cd chat2api_service
pip install -r requirements.txt
playwright install
python main.py

# 2. 在浏览器中登录
# 访问 http://localhost:8000
# 选择AI -> 打开登录页面 -> 完成登录 -> 确认已登录

# 3. 启动 NovelGen（另一个终端）
cd ..
./start.sh  # Linux/Mac
# 或
start.bat    # Windows
# 选择选项 2
```

## 创建你的第一本小说

1. **访问系统**
   - 打开 http://localhost:5173
   - 注册账号并登录

2. **创建小说**
   - 点击"新建小说"
   - 输入标题："我的修仙传"
   - 点击创建

3. **与AI讨论剧情**
   - 点击"继续创作"
   - 输入你的想法：
     ```
     我想写一个修仙小说，主角是一个废柴少年，
     被未婚妻退婚，然后获得了一个神秘的金手指，
     开始逆袭之路。要有热血、升级流的风格。
     ```
   - AI会分析类型并推荐风格
   - 继续讨论直到满意

4. **生成角色**
   - 点击"生成角色设计"
   - 查看AI创建的角色
   - 可以编辑修改

5. **生成大纲**
   - 点击"生成剧情大纲"
   - 查看三卷大纲结构

6. **开始写作**
   - 点击"开始自动撰写"
   - AI开始自动生成章节
   - 在"阅读小说"中查看生成的内容

## 常用操作

### 导出小说

1. 进入小说详情页
2. 点击右上角"导出"
3. 选择格式（TXT/Markdown/JSON）

### 查看生成进度

- 在"继续创作"页面查看实时状态
- 或使用API查看任务状态

### 管理角色

- 进入"角色管理"
- 查看、编辑角色信息
- 查看角色时间线

## 停止服务

```bash
# 停止所有服务
docker-compose down

# 查看日志
docker-compose logs -f
```

## 需要帮助？

- **详细文档**: 查看 [USER_GUIDE.md](USER_GUIDE.md)
- **Chat2Api说明**: 查看 [CHAT2API_USAGE.md](CHAT2API_USAGE.md)
- **API文档**: http://localhost:8000/docs

## 系统架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   前端      │────▶│   后端API   │────▶│   MySQL     │
│  (React)    │     │  (FastAPI)  │     │  (数据)     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      ┌─────────┐    ┌─────────┐    ┌──────────┐
      │  Redis  │    │ Qdrant  │    │   LLM    │
      │ (缓存)  │    │(向量库) │    │(OpenAI/  │
      └─────────┘    └─────────┘    │ Chat2Api)│
                                    └──────────┘
```

## 功能特性

- ✅ 多智能体协作（7个AI智能体）
- ✅ 长文本记忆（支持1000章）
- ✅ 实时WebSocket通信
- ✅ 后台任务队列
- ✅ 用户认证系统
- ✅ 数据导出功能
- ✅ 双模式LLM支持（OpenAI/本地AI）

开始创作吧！🚀
