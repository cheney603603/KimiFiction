# 工作流Chat2API连接验证步骤

## 当前状态

✅ 已完成的修复：
1. 前端LLMSettings默认端口已修正为8088
2. WorkflowPage会自动同步配置到后端
3. 后端LLMService增强了日志输出
4. 后端LLMConfigManager优化了配置读取逻辑
5. 测试脚本已创建（test_llm_config.py）

## 完整验证流程

### 步骤1: 启动Chat2API服务

```bash
cd chat2api_service
python main.py
```

访问 http://localhost:8088 确认服务正常。

### 步骤2: 登录Chat2API

1. 打开 http://localhost:8088
2. 点击对应AI提供商的"打开登录页面"（如Kimi）
3. 在弹出的浏览器窗口中完成登录
4. 点击"确认已登录"按钮
5. 确认状态显示为"已登录"

### 步骤3: 前端配置LLM

1. 访问 http://localhost:5173/settings/llm
2. 选择提供商（如Kimi）
3. 确认Base URL显示为 `http://localhost:8088`
4. 点击"测试连接"
5. 查看日志：
   - `开始测试 kimi API...`
   - `Base URL: http://localhost:8088`
   - `发送测试请求到 kimi...`
   - `收到响应，耗时 XXXms`
6. 确认显示"连接成功"
7. 点击"保存配置"
8. 查看日志：
   - `✅ 后端配置已同步: kimi @ http://localhost:8088`
   - `后端配置已同步，超时时间设置为 XX 秒`

### 步骤4: 验证配置同步

**前端验证**：
1. 打开浏览器控制台（F12）
2. 访问 http://localhost:5173/novel/1/workflow/new
3. 查看Console日志：
   - `[WorkflowPage] 自动同步LLM配置到后端: {provider: "kimi", baseUrl: "http://localhost:8088", ...}`
   - `[WorkflowPage] LLM配置同步成功`

**后端验证**：
1. 查看后端控制台输出：
   - `[LLMConfig] 使用用户配置的base_url: http://localhost:8088`
   - `LLM 全局配置已更新: {'provider': 'kimi', 'base_url': 'http://localhost:8088', ...}`

### 步骤5: 执行工作流测试

1. 在WorkflowPage页面，点击"执行需求分析"按钮
2. 观察右侧执行日志：
   - `初始化工作流引擎...`
   - `准备执行阶段: demand_analysis`
   - `调用AI模型...`
3. 查看后端日志：
   - `[LLM] 调用chat2api: kimi @ http://localhost:8088/api/kimi/chat`
   - `[LLM] 请求参数: timeout=XXX`
   - `[LLM] 调用成功: kimi`
4. 确认AI返回结果
5. 查看聊天区域显示AI分析结果

### 步骤6: 验证Agent调用

使用测试脚本验证Agent是否正确调用Chat2API：

```bash
# 需要先设置环境变量以模拟前端配置
set LLM_PROVIDER=kimi
set CHAT2API_BASE_URL=http://localhost:8088

python test_llm_config.py
```

期望输出：
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

## 常见问题排查

### 问题1: 前端测试连接失败

**症状**：
- 测试日志显示 `HTTP 401: 未登录`
- 或者 `连接失败`

**解决方案**：
1. 确认Chat2API服务已启动
2. 访问 http://localhost:8088
3. 完成登录流程
4. 重新测试

### 问题2: 后端未收到配置

**症状**：
- 后端日志显示使用环境变量或默认配置
- 前端Console没有"LLM配置同步成功"日志

**解决方案**：
1. 检查浏览器Console是否有错误
2. 打开Network标签，查看 `/api/v1/llm/config` 请求
3. 确认请求成功（Status 200）
4. 查看请求Payload是否包含正确的配置

### 问题3: 工作流执行失败

**症状**：
- 执行日志显示 "执行失败"
- 错误信息提示 "chat2api调用失败"

**解决方案**：
1. 检查后端日志中的 `[LLM]` 相关输出
2. 确认使用的URL是否正确
3. 检查Chat2API服务状态
4. 确认Chat2API已登录
5. 如果使用Docker，检查网络配置

### 问题4: Docker环境问题

**症状**：
- 后端日志显示连接 localhost:8088 失败
- Chat2API在宿主机正常运行

**解决方案**：
1. 修改 `backend/.env`:
   ```bash
   CHAT2API_BASE_URL=http://host.docker.internal:8088
   ```
2. 重启后端服务
3. 或者使用主机网络模式运行后端容器

## 配置检查清单

在执行工作流前，确认以下配置：

- [ ] Chat2API服务运行在端口8088
- [ ] Chat2API已登录（访问 http://localhost:8088 确认）
- [ ] 前端LLMSettings中Base URL为 `http://localhost:8088`
- [ ] 前端测试连接成功
- [ ] 前端保存配置成功（查看日志）
- [ ] 访问WorkflowPage时，Console显示"LLM配置同步成功"
- [ ] 后端日志显示正确的base_url
- [ ] 执行工作流时，后端日志显示"[LLM] 调用chat2api"

## 日志级别设置

如需更详细的调试信息，可以在 `backend/.env` 中设置：

```bash
# 启用详细日志
DEBUG=true
```

或在代码中临时添加：

```python
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")
```

## 技术支持

如果问题仍未解决，请提供以下信息：

1. 前端Console日志（F12）
2. 前端Network请求（/api/v1/llm/config）
3. 后端完整日志（特别是 `[LLM]` 和 `[LLMConfig]` 相关）
4. Chat2API服务状态截图
5. Docker运行情况（如使用Docker）

## 成功标志

当一切正常工作时，你应该看到：

**前端**：
- 测试连接成功
- 保存配置成功
- 工作流执行成功
- 聊天区域显示AI分析结果

**后端**：
```
[LLMConfig] 使用用户配置的base_url: http://localhost:8088
[LLM] 调用chat2api: kimi @ http://localhost:8088/api/kimi/chat
[LLM] 请求参数: timeout=120
[LLM] 调用成功: kimi
```

**Chat2API**：
- 控制台显示收到请求
- 正常处理并返回响应

## 下一步

确认配置正常后，可以：
1. 尝试其他工作流阶段（世界观、角色设计等）
2. 切换不同的AI提供商
3. 调整超时时间等参数
4. 开始实际小说创作流程
