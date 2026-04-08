# 工作流页面 Bug 修复

## 问题列表与修复

### 问题1：进入下一阶段后组件没有更新
**症状**：点击"进入下一阶段"后，聊天记录显示已切换，但左侧组件仍显示前一个阶段

**原因**：`handleNextPhase` 只添加了消息，没有触发进度数据刷新

**修复**：
```typescript
const handleNextPhase = () => {
  const nextIndex = currentPhaseIndex + 1
  if (nextIndex < PHASES.length) {
    const nextPhase = PHASES[nextIndex]
    setChatMessages(prev => [...prev, { 
      role: 'system', 
      content: `已切换到「${nextPhase.name}」阶段，请在下方输入您对这一阶段的指导，然后点击"执行${nextPhase.name}"开始`, 
      timestamp: new Date() 
    }])
    // 强制刷新进度数据，使 currentPhaseIndex 更新
    queryClient.invalidateQueries({ queryKey: ['workflowProgress', id] })
  }
}
```

### 问题2：阶段标签不可点击
**症状**：顶部的阶段标签（需求分析、世界观等）无法点击跳转

**修复**：
- 将 `<div>` 改为 `<button>`
- 添加 `onClick` 处理器
- 添加 hover 效果和 cursor-pointer

```typescript
<button
  onClick={() => {
    if (index !== currentPhaseIndex) {
      setChatMessages(prev => [...prev, { 
        role: 'system', 
        content: `已切换到「${phase.name}」阶段`, 
        timestamp: new Date() 
      }])
    }
  }}
  className={`...cursor-pointer...`}
>
  {/* 内容 */}
</button>
```

### 问题3：已完成阶段显示异常
**症状**：刚进入工作流页面，所有阶段都显示为已完成

**原因**：前端判断逻辑错误
```typescript
// 错误的逻辑
const isCompleted = index < currentPhaseIndex || isPhaseCompleted(phase.id, completedPhases)
```
这会导致所有在当前阶段之前的阶段都被标记为已完成，即使它们还没有执行过。

**修复**：
```typescript
// 正确的逻辑 - 只检查 completedPhases
const isCompleted = isPhaseCompleted(phase.id, completedPhases)
```

## 修改的文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/pages/WorkflowPage.tsx` | 1. 修复 `handleNextPhase` 添加进度刷新<br>2. 阶段标签改为可点击按钮<br>3. 修复已完成阶段判断逻辑 |

## 验证步骤

1. **测试进入下一阶段**
   - 执行需求分析
   - 点击"进入下一阶段"
   - 检查左侧组件是否更新为世界观

2. **测试阶段标签点击**
   - 点击顶部的任意阶段标签
   - 检查是否切换到该阶段

3. **测试已完成状态**
   - 刷新页面
   - 检查只有已执行的阶段显示为绿色

---

**修复日期**: 2026-03-31
**修复状态**: ✅ 完成
