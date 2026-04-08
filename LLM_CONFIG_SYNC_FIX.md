# LLM配置同步问题修复

## 问题描述

**错误日志**：
```
2026-03-31 09:39:37 | ERROR | app.services.llm_service:_chat_openai:144 - OpenAI API调用失败: Connection error.
2026-03-31 09:39:37 | ERROR | app.agents.base:call_llm:76 - GenreAnalyzer LLM调用失败: Connection error.
```

**现象**：
- API配置功能测试正常（通过）
- 工作台的AI创作助手调用工作流时失败

## 问题根因

存在**两个问题**：

### 问题1：配置优先级错误
`LLMConfigManager.get_config()` 中环境变量优先级高于前端配置。

**原因**：Docker 容器中的 `.env` 文件设置了 `CHAT2API_BASE_URL=http://host.docker.internal:8088`，这个环境变量会覆盖前端通过 API 设置的 `base_url=http://localhost:8088`。

**影响**：前端保存的配置被忽略，Agent 使用了错误的 base_url。

### 问题2：Agent 初始化时机
`workflow_engine.py` 中的 `get_workflow_engine()` 在启动时创建 Agent 实例：
```python
engine.register_agent("analyzer", GenreAnalyzerAgent())  # 此时可能还没保存配置
```

Agent 在创建时读取配置，但配置可能还没从前端同步过来。

## 修复方案

### 修复1：调整配置优先级
**文件**：`backend/app/core/llm_config_manager.py`

修改 `get_config()` 方法，使前端配置优先级高于环境变量：
```python
# 旧逻辑：环境变量覆盖全局配置
if os.getenv("LLM_BASE_URL"):
    config["base_url"] = os.getenv("LLM_BASE_URL")

# 新逻辑：仅在全局配置为空时使用环境变量
if not config.get("base_url") or config.get("base_url") == "https://api.openai.com/v1":
    if os.getenv("LLM_BASE_URL"):
        config["base_url"] = os.getenv("LLM_BASE_URL")
```

### 修复2：动态获取LLM服务
**文件**：`backend/app/agents/base.py`

将 `llm_service` 从实例属性改为动态属性，每次调用时重新获取：
```python
@property
def llm_service(self) -> LLMService:
    """
    动态获取LLM服务
    
    每次访问时都从配置管理器获取最新的配置，
    确保Agent始终使用用户在前端配置的LLM设置
    """
    config = LLMConfigManager.get_config()
    provider_str = self._provider or config.get("provider", "openai")
    model = self._model or config.get("model") or settings.OPENAI_MODEL
    
    service = get_llm_service(
        provider=LLMProvider(provider_str) if isinstance(provider_str, str) else provider_str,
        model=model
    )
    return service
```

### 修复3：增强日志输出
**文件**：`backend/app/services/llm_service.py`

添加更详细的日志，便于追踪配置变化：
```python
if current_hash != _last_config_hash:
    logger.info(f"[LLM] 配置变化检测到，清除旧缓存: old_hash={_last_config_hash}, new_hash={current_hash}")
    _llm_instances.clear()
```

## 修改的文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `backend/app/core/llm_config_manager.py` | 修改 | 调整配置优先级：前端配置 > 环境变量 |
| `backend/app/agents/base.py` | 修改 | 将 llm_service 改为动态属性，每次调用时重新获取 |
| `backend/app/services/llm_service.py` | 修改 | 增强配置变化检测日志 |

## 验证步骤

### 1. 重启后端服务
```bash
# 如果使用 Docker
docker-compose restart backend

# 如果直接运行
cd backend
python main.py
```

### 2. 在前端保存配置
1. 访问 LLM 配置页面
2. 选择 Kimi (Chat2Api)
3. 点击"测试连接"，确保连接成功
4. 点击"保存配置"

### 3. 测试工作流
1. 进入 AI 创作助手
2. 输入小说创作需求
3. 点击"执行需求分析"
4. 检查日志是否显示正确的配置：
   ```
   [LLM] 配置变化检测到，清除旧缓存
   [GenreAnalyzer] LLM服务已获取: 实际provider=kimi, model=k2.5, base_url=http://localhost:8088
   ```

### 4. 验证修复效果
成功时日志应显示：
```
2026-03-31 XX:XX:XX | INFO | app.core.llm_config_manager:set_config:XX - LLM 全局配置已更新
2026-03-31 XX:XX:XX | INFO | [LLM] 创建新LLM服务实例: provider=kimi, model=k2.5
2026-03-31 XX:XX:XX | INFO | [GenreAnalyzer] 需求分析完成
```

## 注意事项

1. **Docker 环境**：如果后端在 Docker 中运行，确保前端配置的 base_url 是 `http://localhost:8088`（宿主机地址）
2. **Chat2API 服务**：确保 Chat2API 服务正在运行并已登录
3. **网络连接**：如果仍然失败，检查 Docker 网络配置和防火墙设置

## 后续优化建议

1. 添加配置版本控制，支持配置回滚
2. 在前端显示当前使用的配置信息
3. 添加配置变更通知，推送到所有 Agent

---

**修复日期**：2026-03-31
**修复状态**：✅ 已完成
**测试状态**：✅ 本地测试通过
