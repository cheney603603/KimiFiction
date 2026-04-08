# 工作流"进入下一阶段"功能修复

## 问题分析

**症状**：点击"进入下一阶段"后，前端显示已切换，但左侧组件仍显示需求分析，无法进入其他阶段

**根本原因**：
1. 前端的 `handleNextPhase` 只是刷新了查询，但没有通知后端改变当前阶段
2. 后端的 `current_phase` 仍然是需求分析
3. 即使前端刷新了进度数据，后端返回的仍然是需求分析阶段

## 修复方案

### 后端修改
**文件**: `backend/app/api/endpoints/workflow.py`

添加新的 API 端点 `/phase-switch/{novel_id}` 用于只切换阶段而不执行：

```python
@router.post("/phase-switch/{novel_id}")
async def switch_workflow_phase(novel_id: int, request: WorkflowPhaseRequest):
    """只切换阶段，不执行（用于"进入下一阶段"按钮）"""
    try:
        engine = await get_workflow_engine(novel_id)
        phase = WorkflowPhase(request.phase)
        
        # 只改变当前阶段，不执行任何任务
        await engine.transition_to(phase)
        
        logger.info(f"阶段切换: novel_id={novel_id}, phase={phase.value}")
        
        return {
            "success": True,
            "message": f"已切换到{phase.value}阶段",
            "current_phase": phase.value
        }
    except Exception as e:
        logger.error(f"阶段切换失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 前端修改

**文件1**: `frontend/src/services/api.ts`

添加 `switchPhase` 方法：
```typescript
switchPhase: (novelId: number, phase: string) =>
  api.post(`/workflow/phase-switch/${novelId}`, { phase }),
```

**文件2**: `frontend/src/pages/WorkflowPage.tsx`

修改 `handleNextPhase` 函数：
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
    
    // 调用后端 API 切换阶段
    workflowApi.switchPhase(id, nextPhase.id).then(() => {
      // 刷新进度数据
      queryClient.invalidateQueries({ queryKey: ['workflowProgress', id] })
    }).catch((error: any) => {
      const msg = error?.response?.data?.detail || error?.message || '切换阶段失败'
      setChatMessages(prev => [...prev, { role: 'system', content: `错误: ${msg}`, timestamp: new Date() }])
    })
  }
}
```

## 修改的文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/app/api/endpoints/workflow.py` | 添加 `/phase-switch/{novel_id}` 端点 |
| `frontend/src/services/api.ts` | 添加 `switchPhase` 方法 |
| `frontend/src/pages/WorkflowPage.tsx` | 修改 `handleNextPhase` 调用新 API |

## 工作流程（修复后）

1. 用户点击"进入下一阶段"
2. 前端调用 `workflowApi.switchPhase(id, nextPhase.id)`
3. 后端接收请求，调用 `engine.transition_to(phase)` 改变当前阶段
4. 后端返回成功响应
5. 前端刷新进度数据 `queryClient.invalidateQueries()`
6. 后端返回新的 `current_phase`
7. 前端 UI 更新显示新阶段

## 验证步骤

1. 刷新前端页面
2. 执行需求分析
3. 点击"进入下一阶段"
4. 检查左侧组件是否更新为世界观
5. 在输入框输入内容
6. 点击"执行世界观"

---

**修复日期**: 2026-03-31
**修复状态**: ✅ 完成
**后端重启**: 已启用 --reload，自动加载新端点
