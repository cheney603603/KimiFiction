# 工作流Chat2API连接问题修复指南

## 问题描述

在API配置页面已验证可连接的Chat2API服务（端口8088），但在访问 http://localhost:5173/novel/1/workflow/new 页面执行需求分析工作流时无法调用，且服务端未收到请求。

## 根本原因分析

1. **端口配置不一致**
   - 前端LLMSettings默认配置使用 `http://localhost:8000`
   - Chat2API服务实际运行在端口 `8088`
   - 导致前端测试时配置了错误的URL

2. **Docker网络隔离问题**
   - 后端如果运行在Docker容器内，无法访问 `localhost:8088`
   - 需要使用 `host.docker.internal:8088` 或主机网络模式

3. **配置未同步**
   - 前端保存的LLM配置只存储在localStorage
   - 后端LLMConfigManager需要前端主动调用 `/api/v1/llm/config` API同步
   - WorkflowPage加载时没有自动同步配置

4. **LLMService实例缓存问题**
   - `get_llm_service()` 使用缓存机制
   - 配置更新后缓存不会自动刷新
   - 需要依赖配置hash检测变化

## 已实施的修复方案

### 1. 修正前端默认端口配置

**文件**: `frontend/src/pages/LLMSettings.tsx`

```typescript
// 修改前
kimi: {
  provider: 'kimi',
  apiKey: '',
  baseUrl: 'http://localhost:8000',  // 错误的端口
  model: 'kimi',
},

// 修改后
kimi: {
  provider: 'kimi',
  apiKey: '',
  baseUrl: 'http://localhost:8088',  // 正确的端口
  model: 'kimi',
},
```

### 2. 自动同步配置到后端

**文件**: `frontend/src/pages/WorkflowPage.tsx`

在WorkflowPage组件加载时，自动从localStorage读取LLM配置并同步到后端：

```typescript
// 自动同步LLM配置到后端
useEffect(() => {
  const syncConfig = async () => {
    try {
      const savedConfig = localStorage.getItem('llm_config')
      if (savedConfig) {
        const config = JSON.parse(savedConfig)
        console.log('[WorkflowPage] 自动同步LLM配置到后端:', config)
        await llmConfigApi.saveConfig({
          provider: config.provider,
          apiKey: config.apiKey,
          baseUrl: config.baseUrl,
          model: config.model,
          responseTime: config.responseTime,
        })
        console.log('[WorkflowPage] LLM配置同步成功')
      }
    } catch (error) {
      console.warn('[WorkflowPage] 同步LLM配置失败:', error)
    }
  }

  syncConfig()
}, [id])
```

### 3. 增强日志输出

**文件**: `backend/app/services/llm_service.py`

在chat2api调用中添加详细日志：

```python
async def _chat_chat2api(self, ...):
    logger.info(f"[LLM] 调用chat2api: {self.provider.value} @ {url}")
    logger.debug(f"[LLM] 请求参数: timeout={payload.get('timeout')}")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=300) as response:
            if response.status == 200:
                result = await response.json()
                if result.get("success"):
                    logger.info(f"[LLM] 调用成功: {self.provider.value}")
                    return result.get("data", "")
                else:
                    raise ValueError(f"chat2api调用失败: {result.get('message')}")
            # ... 其他错误处理
```

### 4. 优化配置读取逻辑

**文件**: `backend/app/core/llm_config_manager.py`

`get_base_url()` 方法现在优先使用用户配置的baseUrl：

```python
@staticmethod
def get_base_url() -> str:
    config = LLMConfigManager.get_config()
    provider = config.get("provider", "openai")

    if provider == "openai":
        return config.get("base_url", "https://api.openai.com/v1")
    else:
        # chat2api 服务 - 优先使用用户配置的baseUrl
        user_base_url = config.get("base_url")
        if user_base_url:
            logger.info(f"[LLMConfig] 使用用户配置的base_url: {user_base_url}")
            return user_base_url
        # 回退到环境变量
        env_base_url = os.getenv("CHAT2API_BASE_URL", "http://localhost:8088")
        logger.info(f"[LLMConfig] 使用环境变量的CHAT2API_BASE_URL: {env_base_url}")
        return env_base_url
```

### 5. 修正后端环境变量（Docker环境）

**文件**: `backend/.env`

```bash
# 如果后端运行在Docker容器内
CHAT2API_BASE_URL=http://host.docker.internal:8088

# 如果后端运行在宿主机（当前环境）
CHAT2API_BASE_URL=http://localhost:8088
```

## 使用步骤

### 方案A：前端测试连接 + 工作流调用（推荐）

1. **启动Chat2API服务**
   ```bash
   cd chat2api_service
   python main.py
   ```

2. **访问Chat2API登录页面**
   - 打开浏览器访问: http://localhost:8088
   - 点击对应AI提供商的"打开登录页面"
   - 完成登录
   - 点击"确认已登录"

3. **前端配置LLM**
   - 访问 http://localhost:5173/settings/llm
   - 选择提供商（如 Kimi）
   - Base URL 应自动显示 `http://localhost:8088`
   - 点击"测试连接"验证
   - 测试成功后点击"保存配置"

4. **进入工作流页面**
   - 访问 http://localhost:5173/novel/1/workflow/new
   - WorkflowPage会自动同步LLM配置到后端
   - 点击"执行需求分析"
   - 查看执行日志，确认LLM调用成功

### 方案B：后端直接测试

1. **运行测试脚本**
   ```bash
   python test_llm_config.py
   ```

2. **查看输出**
   ```
   === 测试1: 读取配置 ===
   Provider: kimi
   Base URL: http://localhost:8088
   Model: kimi

   === 测试2: LLM服务初始化 ===
   LLMService初始化: chat2api模式, provider=kimi, base_url=http://localhost:8088

   === 测试3: 健康检查 ===
   Status: {'available': True, 'mode': 'chat2api', 'provider': 'kimi', 'message': '已登录'}
   ```

## 故障排查

### 问题1: 工作流执行时提示"服务端未收到请求"

**可能原因**:
- 前端没有正确配置LLM
- 配置没有同步到后端
- Agent初始化使用了错误的配置

**排查步骤**:
1. 打开浏览器控制台（F12）
2. 查看是否有 `[WorkflowPage] LLM配置同步成功` 日志
3. 查看Network标签，确认 `/api/v1/llm/config` 调用成功
4. 查看后端日志，确认 `[LLMConfig] 使用用户配置的base_url: http://localhost:8088`

### 问题2: Agent调用失败，提示"未登录"

**可能原因**:
- Chat2API服务未登录
- Chat2API服务未启动

**排查步骤**:
1. 访问 http://localhost:8088
2. 检查登录状态
3. 如果未登录，完成登录流程
4. 重新测试连接

### 问题3: Docker环境下后端无法访问Chat2API

**可能原因**:
- Docker容器无法访问宿主机的 `localhost:8088`

**解决方案**:
- 修改 `backend/.env`:
  ```bash
  CHAT2API_BASE_URL=http://host.docker.internal:8088
  ```
- 或者使用主机网络模式运行后端容器

### 问题4: 配置更新后Agent仍使用旧配置

**可能原因**:
- `get_llm_service()` 缓存未刷新

**解决方案**:
- LLMService内部使用配置hash检测变化
- 配置变化时自动清除缓存
- 如需强制刷新，重启后端服务

## 验证清单

- [ ] Chat2API服务正常运行在端口8088
- [ ] Chat2API已登录
- [ ] 前端LLMSettings页面可以成功测试连接
- [ ] 前端LLMSettings页面保存配置成功
- [ ] 访问WorkflowPage时，控制台显示"LLM配置同步成功"
- [ ] 后端日志显示正确的base_url
- [ ] 执行工作流时，后端日志显示"[LLM] 调用chat2api"
- [ ] Agent成功返回结果

## 技术细节

### 配置流转

```
用户操作 (LLMSettings页面)
  ↓
保存到 localStorage
  ↓
调用 /api/v1/llm/config POST
  ↓
LLMConfigManager.set_config()
  ↓
设置环境变量 (兼容旧代码)
  ↓
Agent调用 get_llm_service()
  ↓
LLMService.__init__() 读取 LLMConfigManager.get_config()
  ↓
调用 chat2api
```

### 关键API

1. **设置LLM配置**: `POST /api/v1/llm/config`
   ```json
   {
     "provider": "kimi",
     "baseUrl": "http://localhost:8088",
     "model": "kimi",
     "responseTime": 10
   }
   ```

2. **获取超时时间**: `GET /api/v1/llm/config/timeout`
   ```json
   {
     "timeout": 300,
     "response_time": 10
   }
   ```

3. **Chat2API**: `POST http://localhost:8088/api/kimi/chat`
   ```json
   {
     "message": "你好",
     "timeout": 120
   }
   ```

## 总结

通过以下修复，工作流现在可以正确使用Chat2API服务：

1. ✅ 修正前端默认端口为8088
2. ✅ WorkflowPage自动同步配置到后端
3. ✅ 增强日志便于调试
4. ✅ 优化配置读取逻辑
5. ✅ 支持Docker环境的host.docker.internal

确保按照上述步骤操作，Chat2API配置会在工作流中正常工作。
