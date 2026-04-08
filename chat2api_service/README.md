# AI Chat API 服务

通过浏览器自动化技术，将多个 AI 的网页聊天功能统一封装成 API 服务。

支持的 AI 提供商：
- 🤖 **Kimi** (https://www.kimi.com/) - 月之暗面出品的大模型助手
- 🔍 **DeepSeek** (https://chat.deepseek.com/) - 深度求索出品的大模型助手
- 💎 **腾讯元宝** (https://yuanbao.tencent.com/chat) - 腾讯出品的 AI 助手

## 功能特性

- 🔐 支持各平台手机号验证码登录
- 💬 提供统一的 HTTP API 进行聊天
- 🌐 提供 Web 界面进行操作，支持 Markdown 格式显示
- 🍪 自动保存和恢复登录状态
- 🔄 支持浏览器重启
- 🎯 支持切换不同的 AI 提供商
- 📊 支持多 AI 对比模式
- ⚙️ **支持功能开关控制**（联网搜索、深度思考、模型选择等）

## 项目结构

```
ai_chat_service/
├── config.py              # 配置文件
├── base_browser.py        # 浏览器自动化基类
├── kimi_browser.py        # Kimi 浏览器模块
├── deepseek_browser.py    # DeepSeek 浏览器模块
├── yuanbao_browser.py     # 腾讯元宝浏览器模块
├── main.py                # FastAPI 服务主程序
├── client_example.py      # Python 客户端示例
├── start.bat              # Windows 启动脚本
├── requirements.txt       # 依赖列表
├── static/
│   └── index.html         # Web 前端页面
└── README.md              # 说明文档
```

## 安装依赖

```bash
# 在 quant 环境中安装依赖
conda activate quant
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

## 使用方法

### 1. 启动服务

**Windows:**
```bash
start.bat
```

**或直接运行:**
```bash
conda activate quant
python main.py
```

服务启动后:
- Web 界面: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 2. 登录

1. 打开 http://localhost:8000
2. 从顶部选择要使用的 **AI 助手**（Kimi / DeepSeek / 腾讯元宝）
3. 点击"打开登录页面"按钮
4. 在弹出的浏览器窗口中，使用手机号和验证码完成登录
5. 点击"确认已登录"按钮

登录状态会自动保存，下次启动时无需重新登录（除非 Cookie 过期）。

### 3. 功能开关设置

在 Web 界面中，选择 AI 提供商后，聊天区域上方会显示该 AI 支持的功能开关：

| AI 提供商 | 支持功能 |
|-----------|----------|
| **腾讯元宝** | 联网搜索、深度思考 |
| **Kimi** | 模型选择（K2.5 快速 / K2.5 思考） |
| **DeepSeek** | 深度思考（R1）、智能搜索 |

在 API 调用中，可以通过参数启用这些功能。

### 4. 聊天

#### 方式一：Web 界面
1. 在网页中选择 AI 提供商
2. 完成登录
3. **设置功能开关**（如联网搜索、深度思考等）
4. 在下方的输入框中输入消息，点击发送
5. 回复将以 Markdown 格式显示（支持代码高亮、表格等）

#### 方式二：Python API
```python
import requests

# ========== 基础用法 ==========

# 发送消息到 Kimi
response = requests.post("http://localhost:8000/api/kimi/chat",
    json={"message": "你好！", "timeout": 120})
print(response.json())

# ========== 带功能开关的用法 ==========

# 腾讯元宝 - 开启联网搜索和深度思考
response = requests.post("http://localhost:8000/api/yuanbao/chat",
    json={
        "message": "今天的天气怎么样？",
        "enable_web_search": True,    # 联网搜索
        "enable_deep_think": True     # 深度思考
    })

# Kimi - 选择K2.5思考模型
response = requests.post("http://localhost:8000/api/kimi/chat",
    json={
        "message": "解释量子力学",
        "model": "k2.5-reasoning"    # 或 "k2.5"
    })

# DeepSeek - 开启深度思考(R1)和智能搜索
response = requests.post("http://localhost:8000/api/deepseek/chat",
    json={
        "message": "分析这个算法",
        "enable_deep_think": True,    # 深度思考
        "enable_web_search": True     # 智能搜索
    })

# ========== 获取支持的功能列表 ==========

# 获取指定 AI 支持的功能
features = requests.get("http://localhost:8000/api/yuanbao/features")
print(features.json())

# 获取所有 AI 的功能列表
all_features = requests.get("http://localhost:8000/api/features")
print(all_features.json())
```

#### 方式三：客户端程序
```bash
python client_example.py
```

客户端提供以下功能：
- 查看支持的 AI 提供商
- 查看所有 AI 登录状态
- 与单个 AI 聊天
- 多 AI 对比模式（同时向多个 AI 发送相同消息进行对比）

## API 接口

### 获取支持的 AI 提供商
```http
GET /api/providers
```

### 检查指定 AI 状态
```http
GET /api/status/{provider}
```
- `provider`: `kimi`, `deepseek`, `yuanbao`

### 检查所有 AI 状态
```http
GET /api/status
```

### 开始登录
```http
POST /api/{provider}/login/start
```

### 确认登录
```http
POST /api/{provider}/login/confirm
```

### 获取支持的功能列表
```http
GET /api/{provider}/features
```

### 发送消息（基础）
```http
POST /api/{provider}/chat
Content-Type: application/json

{
    "message": "你好",
    "timeout": 120
}
```

### 发送消息（带功能开关）

**腾讯元宝 - 联网搜索 + 深度思考:**
```http
POST /api/yuanbao/chat
Content-Type: application/json

{
    "message": "你好",
    "timeout": 120,
    "enable_web_search": true,
    "enable_deep_think": true
}
```

**Kimi - 选择模型:**
```http
POST /api/kimi/chat
Content-Type: application/json

{
    "message": "你好",
    "timeout": 120,
    "model": "k2.5-reasoning"
}
```

**DeepSeek - 深度思考 + 智能搜索:**
```http
POST /api/deepseek/chat
Content-Type: application/json

{
    "message": "你好",
    "timeout": 120,
    "enable_deep_think": true,
    "enable_web_search": true
}
```

### 清空对话
```http
POST /api/{provider}/clear
```

### 重启浏览器
```http
POST /api/{provider}/browser/restart
```

## 配置文件 (config.py)

```python
# AI 网站配置
KIMI_URL = "https://www.kimi.com/"
DEEPSEEK_URL = "https://chat.deepseek.com/"
YUANBAO_URL = "https://yuanbao.tencent.com/chat"

# Playwright 配置
HEADLESS = False  # 是否无头模式
SLOW_MO = 100     # 操作延迟（毫秒）

# API 配置
API_HOST = "0.0.0.0"
API_PORT = 8000

# 默认 AI 提供商
DEFAULT_AI_PROVIDER = "kimi"
```

## 注意事项

1. **登录状态**：登录状态保存在各自的 cookies 文件中（`kimi_cookies.json`, `deepseek_cookies.json`, `yuanbao_cookies.json` 等），如需重新登录请删除对应文件
2. **浏览器窗口**：默认使用有界面模式（方便调试），如需无头模式请修改 `config.py` 中的 `HEADLESS = True`
3. **网络环境**：确保网络可以正常访问各 AI 网站
4. **验证码**：需要在浏览器窗口中手动输入验证码
5. **并发**：每个 AI 使用独立的浏览器实例，可以同时与多个 AI 聊天

## 常见问题

**Q: 如何切换不同的 AI？**  
A: 在 Web 界面顶部点击选择对应的 AI 选项卡，或在 API 中更换 `{provider}` 参数

**Q: 可以同时使用多个 AI 吗？**  
A: 可以！每个 AI 使用独立的浏览器实例，可以同时登录并与多个 AI 聊天

**Q: 服务启动后无法访问 AI 网站？**  
A: 请检查网络连接，确保可以正常访问对应的 AI 网站

**Q: 登录状态丢失？**  
A: Cookie 可能已过期，删除对应的 cookies 文件后重新登录

**Q: 如何调试？**  
A: 设置 `HEADLESS = False`（默认）可以看到浏览器操作过程

**Q: 回复显示格式不正确？**  
A: 前端使用 Markdown 解析器渲染回复，支持代码高亮、表格、列表等格式

## 技术栈

- **后端**: FastAPI + Uvicorn
- **浏览器自动化**: Playwright
- **前端**: HTML + CSS + JavaScript (支持 Markdown 渲染)

## 扩展更多 AI

如需添加更多 AI 支持，请按照以下步骤：

1. 在 `config.py` 中添加新的 AI URL 和配置
2. 创建新的浏览器模块（参考 `deepseek_browser.py`）
3. 继承 `BaseAIBrowser` 基类，实现抽象方法
4. 在 `main.py` 中导入并注册新的浏览器模块
5. 在 `AI_PROVIDERS` 配置中添加新 AI 的信息
6. **实现功能开关**（可选）：在浏览器类中实现 `get_available_features()` 和 `set_feature()` 方法
