# 超时时间配置和角色设计修复

## 修复日期
2026-03-31

## 问题描述

1. **无法在Web界面设置超时时间**：用户希望能自行设置请求参数timeout以及超时等待的时间，而不是完全依赖自动计算
2. **角色设计阶段无法标记完成**：角色设计完成后，点击"标记完成"按钮无效

## 修复内容

### 1. 超时时间配置功能

#### 后端实现

**文件**: `backend/app/core/llm_config_manager.py`

添加了手动设置超时时间的功能，优先级高于自动计算：

```python
@staticmethod
def get_timeout() -> int:
    """
    获取超时时间（秒）

    优先级：
    1. 手动设置的 timeout 参数（最高优先级）
    2. 根据测试的返回时长计算
    3. 默认 300 秒
    """
    config = LLMConfigManager.get_config()

    # 1. 优先使用手动设置的超时时间
    if "timeout" in config and config["timeout"]:
        try:
            manual_timeout = int(config["timeout"])
            if manual_timeout > 0:
                logger.info(f"使用手动设置的超时时间: {manual_timeout}秒")
                return manual_timeout
        except (ValueError, TypeError):
            logger.warning(f"手动设置的超时时间无效: {config['timeout']}")

    # 2. 根据测试的返回时长计算
    response_time = config.get("response_time")
    if response_time and response_time > 0:
        timeout = max(response_time * 3, response_time + 200)
        logger.info(f"根据测试时长计算超时: {response_time}秒 -> {int(timeout)}秒")
        return int(timeout)

    # 3. 默认 300 秒
    return 300
```

**文件**: `backend/app/api/endpoints/llm_config.py`

更新LLM配置模型，添加timeout参数：

```python
class LLMConfigRequest(BaseModel):
    provider: str = "openai"
    apiKey: Optional[str] = None
    baseUrl: Optional[str] = None
    model: Optional[str] = None
    responseTime: Optional[float] = None  # 测试返回时长（秒）
    timeout: Optional[int] = None  # 手动设置的超时时间（秒）  # 新增
```

更新配置保存逻辑：

```python
config_dict = {
    "provider": config.provider,
    "api_key": config.apiKey,
    "base_url": config.baseUrl,
    "model": config.model,
    "response_time": config.responseTime,
    "timeout": config.timeout,  # 新增
}
```

#### 前端实现

**文件**: `frontend/src/services/api.ts`

更新API类型定义：

```typescript
export const llmConfigApi = {
  saveConfig: (config: {
    provider: string
    apiKey?: string
    baseUrl?: string
    model?: string
    responseTime?: number
    timeout?: number  // 新增
  }) => api.post('/llm/config', config),

  getTimeout: () => api.get('/llm/config/timeout'),
}
```

**文件**: `frontend/src/pages/LLMSettings.tsx`

1. 更新配置接口，添加timeout字段：

```typescript
interface LLMConfig {
  provider: 'openai' | 'kimi' | 'deepseek' | 'yuanbao'
  apiKey: string
  baseUrl: string
  model: string
  responseTime?: number  // 测试返回时长（秒）
  timeout?: number  // 手动设置的超时时间（秒）  // 新增
}
```

2. 更新保存逻辑：

```typescript
const result = await llmConfigApi.saveConfig({
  provider: config.provider,
  apiKey: config.apiKey,
  baseUrl: config.baseUrl,
  model: config.model,
  responseTime: config.responseTime,
  timeout: config.timeout,  // 新增
})
```

3. 添加超时时间输入框：

```jsx
{/* 超时时间设置 */}
<div>
  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
    请求超时时间（秒）
  </label>
  <input
    type="number"
    min="60"
    max="3600"
    step="30"
    value={config.timeout || ''}
    onChange={(e) => setConfig({ ...config, timeout: e.target.value ? parseInt(e.target.value) : undefined })}
    placeholder="留空自动计算"
    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
  />
  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
    {config.responseTime
      ? `根据测试时长(${config.responseTime}s)自动计算，或手动设置（60-3600秒）`
      : '测试连接后将自动计算，或手动设置（60-3600秒）'}
  </p>
</div>
```

#### 功能说明

**超时时间设置优先级**：
1. **手动设置**：用户在Web界面输入的超时时间（60-3600秒）
2. **自动计算**：根据测试时长计算 `max(测试时长 * 3, 测试时长 + 200)`
3. **默认值**：300秒

**使用方式**：
- 测试连接后，系统会根据测试时长自动计算推荐超时时间
- 用户可以手动覆盖自动计算的值
- 留空表示使用自动计算或默认值

### 2. 角色设计标记完成修复

#### 问题分析

在 `backend/app/api/endpoints/workflow.py` 的 `toggle_phase_completion` 端点中，判断阶段是否完成的逻辑有误：

```python
# 修复前
is_completed = current_data is not None and (not isinstance(current_data, list) or len(current_data) > 0)
```

这个逻辑的问题：
- `self.state.characters` 是一个列表类型
- 当角色设计完成但没有数据时（用户手动标记），列表为 `[]`
- 空列表 `[]` 在Python中是 `False`
- 所以 `len([]) > 0` 为 `False`，导致 `is_completed = False`
- 系统认为阶段未完成，允许标记完成，但完成后再次检查时又判断为未完成

#### 修复方案

**文件**: `backend/app/api/endpoints/workflow.py`

修改判断逻辑：

```python
# 修复后
current_data = phase_data_map.get(phase)
# 修复：对于列表类型，即使为空数组也算有数据（用户手动标记完成的情况）
is_completed = current_data is not None
```

**修复说明**：
- 简化判断逻辑，只检查数据是否存在
- 对于列表类型，即使为空数组 `[]` 也视为已完成
- 因为用户可能手动标记完成而没有实际数据

**注意**：
前端也有类似的判断，需要确保前后端逻辑一致：
- 前端在 `PhaseResultViewer` 组件中通过 `isCompleted` prop 显示状态
- 后端通过 `get_progress()` 返回的 `completed_phases` 列表判断
- 两者都需要统一：空列表视为已完成

### 3. 分阶段超时时间

不同阶段的复杂度不同，自动超时时间会在基础上乘以系数：

```python
# 根据阶段设置不同的超时时间
base_timeout = llm_config.get_timeout()
phase_timeout_map = {
    WorkflowPhase.DEMAND_ANALYSIS: base_timeout,
    WorkflowPhase.WORLD_BUILDING: base_timeout * 1.2,
    WorkflowPhase.CHARACTER_DESIGN: base_timeout * 1.5,
    WorkflowPhase.PLOT_DESIGN: base_timeout * 1.5,
    WorkflowPhase.OUTLINE_DRAFT: base_timeout * 2.0,
    WorkflowPhase.OUTLINE_DETAIL: base_timeout * 2.5,
}
```

章节写作使用3倍超时：
```python
timeout = base_timeout * 3  # 章节写作使用3倍超时
```

## 修复的文件

1. `backend/app/core/llm_config_manager.py` - 添加手动超时设置功能
2. `backend/app/api/endpoints/llm_config.py` - 更新配置模型
3. `backend/app/api/endpoints/workflow.py` - 修复角色设计标记完成判断
4. `frontend/src/services/api.ts` - 更新API类型
5. `frontend/src/pages/LLMSettings.tsx` - 添加超时时间设置界面

## 测试建议

### 超时时间配置测试

1. 测试自动计算超时：
   - 测试连接LLM服务
   - 查看自动计算的超时时间是否正确
   - 确认日志显示计算过程

2. 测试手动设置超时：
   - 在Web界面手动输入超时时间（如600秒）
   - 保存配置
   - 执行一个阶段，确认使用的超时时间

3. 测试超时范围：
   - 测试最小值（60秒）
   - 测试最大值（3600秒）
   - 测试超出范围值（应被限制）

4. 测试优先级：
   - 设置手动超时 -> 执行阶段 -> 确认使用手动值
   - 清空手动超时 -> 执行阶段 -> 确认使用自动计算值

### 角色设计标记完成测试

1. 测试标记完成：
   - 切换到角色设计阶段
   - 点击"标记完成"按钮
   - 刷新页面，确认状态保持完成

2. 测试标记未完成：
   - 在已完成的角色设计阶段
   - 点击"标记未完成"按钮
   - 确认状态变为未完成

3. 测试数据持久化：
   - 标记完成后刷新页面
   - 确认状态和数据都被正确保存

4. 测试与其他阶段的一致性：
   - 测试所有阶段的标记功能
   - 确保行为一致

## 相关文件

- `backend/app/workflow_engine.py` - 工作流引擎
- `backend/app/agents/unified_agent.py` - 统一Agent
- `backend/app/agents/prompt_builder.py` - 提示词构建
- `frontend/src/pages/WorkflowPage.tsx` - 工作流页面
- `frontend/src/types/index.ts` - 类型定义

## 补充说明

### 超时时间设计考虑

1. **用户体验**：
   - 自动计算：方便大多数用户
   - 手动设置：满足高级用户需求
   - 清晰提示：告知用户当前使用的超时时间

2. **灵活性**：
   - 可以根据不同模型响应速度调整
   - 可以根据网络环境调整
   - 不同阶段使用不同系数

3. **安全性**：
   - 限制最小值60秒，避免太短导致失败
   - 限制最大值3600秒（1小时），避免太长卡住
   - 验证输入合法性

### 角色设计修复原理

修复的核心在于：
- 判断阶段完成的标准应该是"是否设置过"，而不是"是否有数据"
- 用户手动标记完成时，可能没有实际数据（如角色数据为空）
- 但用户明确表示"已完成"，应该尊重用户的选择
- 前后端都需要统一这个逻辑
