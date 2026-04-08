# Chat2Api Service 集成使用说明

## 概述

NovelGen 现在支持两种 LLM 调用方式：

1. **OpenAI API 模式** - 直接调用 OpenAI API 或兼容 API
2. **Chat2Api Service 模式** - 调用本地 chat2api_service 服务（支持 Kimi、DeepSeek、腾讯元宝）

## 配置方法

### 方法一：OpenAI API 模式（默认）

```bash
# backend/.env
LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4-turbo-preview
```

### 方法二：Chat2Api Service 模式

1. 首先启动 chat2api_service（在另一个终端）

```bash
cd chat2api_service
pip install -r requirements.txt
python main.py
```

2. 在浏览器中访问 http://localhost:8000 完成登录

3. 配置 NovelGen 使用 chat2api

```bash
# backend/.env
# 可选值: kimi, deepseek, yuanbao
LLM_PROVIDER=kimi
CHAT2API_BASE_URL=http://localhost:8000
```

## 支持的提供商

| 提供商 | 说明 | 特殊功能 |
|--------|------|----------|
| `openai` | OpenAI API | 标准OpenAI接口 |
| `kimi` | 月之暗面 Kimi | 支持模型选择 (k2.5/k2.5-reasoning) |
| `deepseek` | DeepSeek | 支持深度思考、联网搜索 |
| `yuanbao` | 腾讯元宝 | 支持深度思考、联网搜索 |

## 切换提供商

### 方式一：环境变量（全局配置）

修改 `backend/.env` 文件中的 `LLM_PROVIDER`

### 方式二：代码中动态切换

```python
from app.services.llm_service import LLMService, LLMProvider

# 创建特定提供商的服务实例
llm_service = LLMService(
    provider=LLMProvider.KIMI,
    model="k2.5-reasoning"
)

# 使用服务发送消息
messages = [
    {"role": "system", "content": "你是一个小说作家"},
    {"role": "user", "content": "写一个玄幻小说的开头"}
]
response = await llm_service.chat(messages)
```

## 智能体中使用

所有智能体现在都支持通过配置切换 LLM 提供商：

```python
from app.agents.analyzer import GenreAnalyzerAgent
from app.services.llm_service import LLMProvider

# 使用默认配置（从环境变量读取）
agent = GenreAnalyzerAgent()

# 或者指定提供商
agent = GenreAnalyzerAgent(
    provider=LLMProvider.KIMI
)

# 调用智能体
result = await agent.process({
    "user_input": "我想写一个修仙小说"
})
```

## 健康检查

检查 LLM 服务状态：

```python
from app.services.llm_service import get_llm_service

llm_service = get_llm_service()
status = await llm_service.health_check()
print(status)
# 输出示例:
# {
#     "status": "ok",
#     "provider": "kimi",
#     "chat2api_status": {
#         "available": True,
#         "mode": "chat2api",
#         "message": "已登录"
#     }
# }
```

## 故障排除

### Chat2Api 未登录

如果看到错误信息：`chat2api未登录，请先登录kimi`

解决方法：
1. 访问 http://localhost:8000
2. 选择对应的 AI 提供商
3. 点击"打开登录页面"
4. 在浏览器中完成登录
5. 点击"确认已登录"

### 连接失败

如果看到错误信息：`chat2api调用失败`

检查：
1. chat2api_service 是否已启动
2. `CHAT2API_BASE_URL` 配置是否正确
3. 端口 8000 是否被占用

### 超时问题

如果 LLM 响应超时，可以调整超时时间：

```python
response = await llm_service.chat(
    messages,
    timeout=180  # 增加到180秒
)
```

## 混合使用示例

可以在不同智能体中使用不同的提供商：

```python
from app.agents.analyzer import GenreAnalyzerAgent
from app.agents.writer import ChapterWriterAgent
from app.services.llm_service import LLMProvider

# 类型分析使用 Kimi
analyzer = GenreAnalyzerAgent(provider=LLMProvider.KIMI)

# 章节撰写使用 DeepSeek
writer = ChapterWriterAgent(provider=LLMProvider.DEEPSEEK)

# 或者都使用 OpenAI
analyzer = GenreAnalyzerAgent(provider=LLMProvider.OPENAI)
writer = ChapterWriterAgent(provider=LLMProvider.OPENAI)
```

## 性能对比

| 模式 | 响应速度 | 稳定性 | 成本 | 适用场景 |
|------|----------|--------|------|----------|
| OpenAI API | 快 | 高 | 按token计费 | 生产环境 |
| Kimi | 中等 | 高 | 免费（需账号） | 国内用户 |
| DeepSeek | 中等 | 高 | 免费（需账号） | 深度思考 |
| 腾讯元宝 | 中等 | 高 | 免费（需账号） | 联网搜索 |

## 注意事项

1. **chat2api_service 需要单独启动**，NovelGen 不会自动启动它
2. **chat2api_service 需要登录**，登录状态会保存在 cookies 文件中
3. **chat2api_service 使用浏览器自动化**，需要安装 Playwright 和浏览器
4. **建议生产环境使用 OpenAI API**，本地开发可以使用 chat2api

## 相关文件

- `backend/app/services/llm_service.py` - LLM 服务客户端
- `backend/app/agents/base.py` - 智能体基类
- `backend/app/core/config.py` - 配置管理
- `chat2api_service/` - Chat2Api 服务目录
