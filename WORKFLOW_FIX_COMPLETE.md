# 工作流功能完善修复

## 问题概述与修复状态

| # | 问题 | 修复状态 | 说明 |
|---|------|----------|------|
| 1 | 输入为空时应阻止执行 | ✅ 已修复 | 添加输入验证，空输入时提示用户 |
| 2 | 上一阶段结果传入下一阶段 | ✅ 已修复 | 后端自动合并上一阶段数据 |
| 3 | 进入下一阶段不自动执行 | ✅ 已修复 | 分离阶段切换和执行逻辑 |
| 4 | 章节写作添加章节号输入 | ✅ 已修复 | 添加章节号输入框 |
| 5 | 章节写作调用真正的LLM | ✅ 已修复 | writer.py 已实现LLM调用 |
| 6 | 章节写作添加更多参数 | ✅ 已修复 | 添加文风、环境描写、对话占比等 |
| 7 | 阶段结果保存到数据库 | ✅ 已修复 | 保存到 Character、Outline 等表 |

---

## 修改的文件清单

### 后端文件

| 文件 | 修改内容 |
|------|----------|
| `backend/app/workflow_engine.py` | - 添加 `_get_previous_phase_data()` 方法获取已完成阶段的数据<br>- 修改 `run_phase()` 方法，自动合并上一阶段数据到 input_data<br>- 修改 `_save_phase_data()` 保存角色、大纲等到数据库 |
| `backend/app/agents/writer.py` | - 完全重写，实现真正的 LLM 章节生成<br>- 添加写作参数：target_words, writing_style, env_description_level, dialogue_ratio, notes<br>- 添加人物上下文、大纲上下文、前文摘要 |
| `backend/app/api/endpoints/workflow.py` | - 修改 `write_chapter` 接口接受更多参数 |

### 前端文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/pages/WorkflowPage.tsx` | - 添加 `pendingNextPhase` 状态跟踪下一阶段<br>- 修改 `handleExecuteCurrentPhase()` 添加空输入验证<br>- 修改 `handleNextPhase()` 只切换阶段不执行<br>- 添加章节号、写作风格、环境描写级别、对话占比、注意事项等输入控件<br>- 添加 `handleWriteChapter()` 处理章节写作<br>- 添加 `WRITING_STYLE_OPTIONS` 等常量 |

---

## 详细修改说明

### 1. 空输入验证
```typescript
// handleExecuteCurrentPhase 中添加
if (!inputMessage.trim() && !isCurrentPhaseCompleted && !currentPhase.allowEmptyExecute) {
  setChatMessages(prev => [...prev, { 
    role: 'system', 
    content: '请先在上方输入框中输入内容，再执行当前阶段', 
    timestamp: new Date() 
  }])
  return
}
```

### 2. 上一阶段数据自动传入
```python
# workflow_engine.py 的 run_phase 方法
prev_data = await self._get_previous_phase_data(phase)
if prev_data:
    input_data = input_data or {}
    input_data["previous_phase_result"] = prev_data
    # 展开关键数据
    for key, value in prev_data.items():
        if key not in input_data:
            input_data[key] = value
```

### 3. 章节写作参数
```typescript
// 章节写作输入参数
- chapterNumber: 章节号（必填）
- writingStyle: 写作风格（预设选项）
- envLevel: 环境描写级别（minimal/normal/rich）
- dialogueRatio: 对话占比（0.1-0.5）
- chapterNotes: 注意事项（可选）
```

### 4. 数据库保存逻辑
```python
# 角色设计结果 -> Character 表
# 冲突伏笔 -> novels.style_prompt (JSON)
# 剧情大纲 -> Outline 表
```

---

## 使用流程（修复后的）

1. **需求分析阶段**
   - 在输入框输入创作需求
   - 点击「执行需求分析」
   - （空输入会被阻止）

2. **世界观阶段**
   - 点击「进入下一阶段」
   - （阶段切换，不执行）
   - 在输入框描述世界观要求
   - 点击「执行世界观」
   - （自动接收上一阶段的需求分析结果）

3. **角色设计阶段**
   - 点击「进入下一阶段」
   - 在输入框描述角色要求
   - 点击「执行角色设计」
   - （自动接收需求分析+世界观）

4. **...后续阶段同理...**

5. **章节写作阶段**
   - 输入章节号
   - 选择写作风格
   - 选择环境描写级别
   - 调整对话占比
   - （可选）输入注意事项
   - 点击「撰写章节」

---

## 验证步骤

1. **测试空输入阻止**
   - 不输入任何内容
   - 点击「执行需求分析」
   - 应该看到提示消息

2. **测试阶段数据传递**
   - 执行需求分析生成结果
   - 进入世界观阶段
   - 检查执行日志是否包含需求分析结果

3. **测试章节写作**
   - 进入章节写作阶段
   - 输入章节号（如 1）
   - 选择写作风格
   - 点击「撰写章节」
   - 检查是否生成真正的章节内容

4. **测试数据保存**
   - 执行角色设计
   - 前往角色管理页面
   - 检查是否显示生成的角色

---

**修复日期**: 2026-03-31
**修复状态**: ✅ 全部完成
