# 统一Agent工作流修复总结

## 修复的问题

### 问题1：上一阶段输出丢失 ✅ 已修复

**问题描述**：上一阶段的输出不知道去哪了，没有任何文件、显示

**修复方案**：
- 优化 `_get_previous_phase_data` 方法，正确提取所有已完成阶段的数据
- 在 `run_phase` 中将上一阶段数据展开到 `input_data` 中
- 统一Agent通过 `extract_previous_results` 方法提取数据

### 问题2：用户输入没有正确放入提示词 ✅ 已修复

**问题描述**：到了下一阶段，并没有把用户输入放到提示词的对应位置

**修复方案**：
- 创建 `PromptBuilder` 统一提示词构建器
- 使用LLM智能融合：用户输入 + 上一阶段结果 + 预设模板
- 生成结构化的融合提示词，包含：
  - `fused_prompt`: 融合后的完整提示词
  - `key_requirements`: 关键需求列表
  - `context_summary`: 上下文摘要
  - `template_adaptations`: 对模板的调整说明

### 问题3：Agent接口不统一 ✅ 已修复

**问题描述**：每个阶段的Agent应该有相似的函数

**修复方案**：
- 创建 `UnifiedAgent` 基类，所有Agent使用相同的接口：
  - `get_template()`: 获取预设模板
  - `parse_result()`: 解析LLM响应
  - `process()`: 统一处理流程
- 实现统一的Agent：
  - `UnifiedWorldBuilderAgent`
  - `UnifiedCharacterDesignerAgent`
  - `UnifiedPlotDesignerAgent`
  - `UnifiedOutlineGeneratorAgent`

## 新增功能

### 1. 提示词构建信息查看
- 后端API：`/workflow/phase-prompt/{novel_id}/{phase}`
- 前端界面：阶段卡片上添加"查看提示词"按钮
- 显示内容：
  - 用户输入
  - 上下文摘要
  - 关键需求
  - 模板调整

### 2. 统一的工作流程
所有Agent现在遵循相同的工作流程：
1. 提取用户输入和上一阶段结果
2. 使用PromptBuilder融合提示词
3. 调用LLM生成结果
4. 解析并返回结构化数据
5. 保存提示词构建信息

## 修改的文件

### 新增文件
1. `backend/app/agents/prompt_builder.py` - 统一提示词构建器
2. `backend/app/agents/unified_agent.py` - 统一Agent基类和实现

### 修改文件
1. `backend/app/workflow_engine.py`
   - 添加 unified_agent 导入
   - 使用新的统一Agent

2. `backend/app/api/endpoints/workflow.py`
   - 添加 `/phase-prompt/{novel_id}/{phase}` API端点

3. `frontend/src/services/api.ts`
   - 添加 `getPhasePromptInfo` API方法

4. `frontend/src/pages/WorkflowPage.tsx`
   - 添加查看提示词功能

## 测试步骤

1. 重启后端服务以加载新代码
2. 刷新前端页面
3. 执行某个阶段，输入用户要求
4. 阶段完成后，点击"查看提示词"按钮
5. 验证：
   - 能看到用户输入被正确融合
   - 能看到上一阶段的结果被引用
   - 能看到模板调整说明

## 设计优势

1. **透明性**：用户可以查看融合后的提示词，了解AI是如何理解需求的
2. **一致性**：所有Agent使用相同的接口和流程
3. **可追溯性**：保存了提示词构建的中间信息
4. **灵活性**：通过LLM智能融合，比简单的字符串拼接更智能
