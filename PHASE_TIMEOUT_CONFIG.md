# 阶段超时配置功能实现

## 修改概述

为每个工作流阶段添加了独立的LLM请求超时配置功能，允许用户在Web界面上为每个阶段单独设置超时时间。

## 修改内容

### 1. 后端修改

#### 1.1 Schema修改 (`backend/app/schemas/workflow.py`)
- 在`WorkflowPhaseRequest`模型中添加了可选的`timeout`字段
  ```python
  timeout: Optional[int] = Field(None, ge=30, le=3600, description="阶段超时时间（秒），不填则使用默认值")
  ```

#### 1.2 工作流引擎修改 (`backend/app/workflow_engine.py`)
- 修改`run_phase`方法签名，添加`timeout`参数
- 将`timeout`参数添加到`input_data`中，供Agent使用
- 记录超时日志

#### 1.3 UnifiedAgent修改 (`backend/app/agents/unified_agent.py`)
- 修改`process`方法，从`context`中提取`timeout`参数
- 将`timeout`传递给`call_llm`方法

#### 1.4 Workflow API修改 (`backend/app/api/endpoints/workflow.py`)
- 修改`execute_workflow_phase`端点，传递`request.timeout`参数
- 修改`_execute_phase_with_progress`函数，接收`timeout`参数
- 优先使用用户设置的timeout，否则根据阶段自动计算

### 2. 前端修改

#### 2.1 API服务修改 (`frontend/src/services/api.ts`)
- 修改`executePhase`函数类型定义，添加可选的`timeout`参数

#### 2.2 WorkflowPage修改 (`frontend/src/pages/WorkflowPage.tsx`)
- 添加`phaseTimeouts`状态，存储每个阶段的超时配置
- 添加`showTimeoutConfig`状态，控制超时配置面板的显示/隐藏
- 添加`handlePhaseTimeoutChange`函数，处理超时配置变更
- 修改`executePhaseMutation`，支持传递`timeout`参数
- 修改`handleExecuteCurrentPhase`和`handleSendMessage`，传递当前阶段的超时配置
- 添加超时配置UI组件：
  - 可折叠的超时设置面板
  - 超时时间输入框（30-3600秒范围）
  - 显示当前配置状态
  - 清除自定义超时的按钮

## 使用方式

### 前端操作
1. 进入工作流创作页面
2. 在左侧面板中找到"超时设置"按钮
3. 点击展开超时配置面板
4. 输入想要设置的超时时间（秒）
5. 执行阶段时，会使用设置的超时时间
6. 留空则使用系统自动计算的超时时间

### 默认超时计算规则
如果未手动设置超时，系统会根据阶段自动计算：
- 需求分析：基础超时时间
- 世界观构建：基础超时时间 × 1.2
- 角色设计：基础超时时间 × 1.5
- 冲突伏笔：基础超时时间 × 1.5
- 剧情大纲：基础超时时间 × 2.0
- 章节细纲：基础超时时间 × 2.5
- 章节写作：基础超时时间 × 3.0

基础超时时间由`LLMConfigManager.get_timeout()`获取，优先级：
1. 手动设置的timeout参数（最高优先级）
2. 根据测试的返回时长计算
3. 默认300秒

## 技术细节

### 数据流转
1. 前端用户输入超时时间 → 保存到localStorage
2. 执行阶段时从localStorage读取 → 传递给API
3. API接收timeout → 传递给`_execute_phase_with_progress`
4. `_execute_phase_with_progress` → 传递给`engine.run_phase`
5. `run_phase` → 添加到input_data
6. UnifiedAgent.process → 提取timeout
7. UnifiedAgent.process → 传递给`call_llm`
8. `call_llm` → 传递给`llm_service.chat`
9. `llm_service._chat_chat2api` → 使用timeout参数

### 存储位置
- 前端：localStorage `phase_timeouts`
- 后端：不持久化（每次请求传递）

## 日志输出
执行阶段时，日志会显示：
```
设置超时时间: 300秒
[Workflow] 阶段 demand_analysis 设置超时: 300秒
[LLM] 请求参数: timeout=300
```

## 优势
1. 灵活性：每个阶段可以设置不同的超时时间
2. 易用性：直观的UI界面，实时保存到localStorage
3. 智能默认：未设置时使用自动计算的超时时间
4. 透明度：UI显示当前配置状态
5. 日志清晰：执行日志显示实际使用的超时时间

## 兼容性
- 完全向后兼容，未设置timeout时使用原有逻辑
- 前端使用localStorage存储，不依赖后端持久化
- API接口向后兼容，timeout为可选参数
