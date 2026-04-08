# 工作流阶段顺序与超时修复

## 修复日期
2026-03-31

## 问题描述

1. **数据库保存失败**: `_persist_phase_result_to_db` 方法尝试导入 `async_session_maker` 变量，但 `database.py` 中导出的是 `get_session_maker()` 函数
2. **超时时间不足**: 后面的阶段（如大纲、章节写作）需要更长的超时时间
3. **阶段顺序不合理**: 冲突伏笔设计应该在大纲之后，而不是在角色设计之后
4. **执行日志缺少提示**: 需要显示"正在融合提示词"和"生成阶段成果"等信息

## 修复内容

### 1. 数据库保存修复

**文件**: `backend/app/workflow_engine.py`

**问题**:
```python
from app.core.database import async_session_maker  # ❌ 错误导入

async with async_session_maker() as db:  # ❌ 错误用法
```

**修复**:
```python
from app.core.database import get_session_maker  # ✅ 正确导入

async with get_session_maker()() as db:  # ✅ 正确用法
```

### 2. 超时时间优化

**文件**: `backend/app/api/endpoints/workflow.py`

为不同阶段设置不同的超时时间：
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

### 3. 阶段顺序调整

**后端** (`backend/app/workflow_engine.py`):
```python
def get_phase_order(self) -> List[WorkflowPhase]:
    """获取正确的阶段顺序"""
    return [
        WorkflowPhase.DEMAND_ANALYSIS,      # 需求分析
        WorkflowPhase.WORLD_BUILDING,         # 世界观构建
        WorkflowPhase.CHARACTER_DESIGN,       # 角色设计
        WorkflowPhase.OUTLINE_DRAFT,          # 剧情大纲
        WorkflowPhase.PLOT_DESIGN,            # 冲突/伏笔设计（在大纲之后）
        WorkflowPhase.OUTLINE_DETAIL,         # 章节细纲
        WorkflowPhase.CHAPTER_WRITING,        # 章节写作
        WorkflowPhase.CHAPTER_REVIEW,         # 章节审核
    ]
```

**前端** (`frontend/src/types/index.ts`):
```typescript
export type WorkflowPhase = 
  | 'demand_analysis'      // 需求分析
  | 'world_building'         // 世界观构建
  | 'character_design'      // 角色设计
  | 'outline_draft'         // 剧情大纲
  | 'plot_design'           // 冲突伏笔设计（在大纲之后）
  | 'outline_detail'         // 章节细纲
  | 'chapter_writing'        // 章节写作
  // ...
```

**前端** (`frontend/src/pages/WorkflowPage.tsx`):
```typescript
const PHASES = [
  { id: 'demand_analysis', name: '需求分析', ... },
  { id: 'world_building', name: '世界观', ... },
  { id: 'character_design', name: '角色设计', ... },
  { id: 'outline_draft', name: '剧情大纲', ... },  // 移到这里
  { id: 'plot_design', name: '冲突伏笔', ... },    // 从这里移动
  { id: 'outline_detail', name: '章节细纲', ... },
  { id: 'chapter_writing', name: '章节写作', ... },
]
```

### 4. 执行日志增强

**文件**: `backend/app/workflow_engine.py`

添加更详细的日志：
```python
# 开始执行
await WorkflowLogsManager.add_log(
    self.state.workflow_id, "info",
    f"🚀 开始执行: {phase_name}",
    step=task.phase.value
)
await WorkflowLogsManager.add_log(
    self.state.workflow_id, "info",
    f"🔧 正在构建融合提示词...",
    step=task.phase.value
)

# 执行成功
await WorkflowLogsManager.add_log(
    self.state.workflow_id, "success",
    f"✅ {phase_name} 执行成功",
    step=task.phase.value
)

# 提示词构建信息
if hasattr(result, '_prompt_build_info') or (isinstance(result, dict) and '_prompt_build_info' in result):
    prompt_info = result.get('_prompt_build_info') if isinstance(result, dict) else getattr(result, '_prompt_build_info', {})
    if prompt_info:
        await WorkflowLogsManager.add_log(
            self.state.workflow_id, "info",
            f"📝 提示词构建完成: 关键需求={len(prompt_info.get('key_requirements', []))}项, 模板调整={len(prompt_info.get('template_adaptations', []))}项",
            step=task.phase.value
        )
```

## 修复的文件

1. `backend/app/workflow_engine.py`
   - 修复数据库保存错误
   - 添加阶段顺序管理方法
   - 增强执行日志
   - 添加缺失的import

2. `backend/app/api/endpoints/workflow.py`
   - 实现分阶段超时时间设置

3. `frontend/src/types/index.ts`
   - 更新阶段顺序注释

4. `frontend/src/pages/WorkflowPage.tsx`
   - 更新阶段显示顺序

## 逻辑说明

### 阶段顺序调整的理由

1. **需求分析** → 首先明确创作方向
2. **世界观构建** → 基于需求分析建立世界框架
3. **角色设计** → 在世界观内创建角色
4. **剧情大纲** → 基于世界观和角色设计故事框架
5. **冲突伏笔设计** → **调整到这里**：基于大纲来设计具体的冲突和伏笔，这样更合理
6. **章节细纲** → 基于大纲和冲突伏笔设计详细章节
7. **章节写作** → 基于细纲进行实际写作

冲突伏笔设计在大纲之后的好处：
- 有完整的故事框架后，可以更好地设计冲突和伏笔的布局
- 可以确保伏笔在大纲中就有对应的位置
- 冲突设计可以更好地服务于整体故事结构

### 超时时间设置的理由

不同阶段的复杂度和AI生成时间不同：
- 需求分析：最简单，基础超时
- 世界观、角色设计：中等复杂度，1.2-1.5倍超时
- 冲突伏笔：需要综合考虑，1.5倍超时
- 剧情大纲：需要生成完整结构，2倍超时
- 章节细纲：最详细，2.5倍超时
- 章节写作：实际写作内容，3倍超时

## 测试建议

1. 测试数据库保存是否正常
2. 测试各个阶段的超时时间是否合理
3. 测试阶段顺序是否正确
4. 查看执行日志是否显示完整信息
5. 测试提示词构建信息是否正确保存和显示

## 相关文件

- `backend/app/core/database.py` - 数据库连接管理
- `backend/app/agents/prompt_builder.py` - 提示词构建
- `backend/app/agents/unified_agent.py` - 统一Agent基类
