# 角色数据解析和同步问题修复

## 问题诊断

根据日志分析，发现了以下问题：

1. **LLM 返回的 profile 数据结构不符合预期**
   - LLM 返回嵌套结构：`profile.basic_info.age`
   - 数据库和前端期望扁平结构：`profile.age`

2. **JSON 解析成功但数据格式不匹配**
   - LLM 返回了有效 JSON（11383 字符）
   - 但 profile 字段使用了嵌套的 `basic_info` 结构

## 根本原因

从日志可以看到 LLM 返回的格式：

```json
{
  "name": "陈默",
  "role_type": "protagonist",
  "profile": {
    "basic_info": {
      "age": 28,
      "gender": "男",
      "appearance": "..."
    },
    "personality": "...",
    "mbti": "INTJ",
    ...
  }
}
```

但数据库模型期望的格式：

```python
# backend/app/models/character.py
profile = JSON  # 存储结构：
{
  "age": 28,
  "gender": "male",
  "appearance": "...",
  "personality": "...",
  "mbti": "INTJ",
  "background": "...",
  "goals": ["..."],
  "fears": ["..."],
  "skills": ["..."],
  "relationships": {...}
}
```

## 修复方案

### 修复1: 优化 LLM 提示词

**文件**: `backend/app/agents/unified_agent.py`

**修改**: 在提示词中明确要求 `profile` 必须是扁平结构

```python
输出JSON格式：
{{
  "characters": [
    {{
      "name": "角色名",
      "role_type": "protagonist/antagonist/supporting",
      "profile": {{
        "age": 20,
        "gender": "male",
        "appearance": "外貌描述",
        "personality": "性格描述",
        "mbti": "INTJ",
        "background": "背景故事",
        "goals": ["目标1", "目标2"],
        "fears": ["恐惧1"],
        "skills": ["技能1", "技能2"],
        "relationships": {{"角色B": "朋友", "角色C": "敌人"}}
      }},
      "arc_description": "成长弧线"
    }}
  ],
  "relationship_summary": "角色关系概述"
}}
```

**关键改进**:
- 明确展示完整的 profile 结构示例
- 强调 `profile` 必须是扁平结构
- 包含所有必需字段的示例

### 修复2: 添加 profile 数据转换逻辑

**文件**: `backend/app/workflow_engine.py`

**修改**: 在 `_sync_characters_to_db` 方法中添加数据转换

```python
# 处理 profile 数据，确保是扁平结构
profile = char_data.get("profile", {})

# 如果 profile 包含嵌套的 basic_info，需要展平
if "basic_info" in profile and isinstance(profile["basic_info"], dict):
    basic_info = profile.pop("basic_info")
    profile.update(basic_info)
    logger.debug(f"[WorkflowEngine] 展平 profile.basic_info: {list(basic_info.keys())}")

# 确保必要的字段存在（支持英文和中文键名）
normalized_profile = {
    "age": profile.get("age") or profile.get("年龄"),
    "gender": profile.get("gender") or profile.get("性别"),
    "appearance": profile.get("appearance") or profile.get("外貌描述") or "",
    "personality": profile.get("personality") or profile.get("性格") or "",
    "mbti": profile.get("mbti") or profile.get("mbti类型") or "",
    "background": profile.get("background") or profile.get("背景") or "",
    "goals": profile.get("goals") or profile.get("目标") or [],
    "fears": profile.get("fears") or profile.get("恐惧") or [],
    "skills": profile.get("skills") or profile.get("技能") or [],
    "relationships": profile.get("relationships") or profile.get("人际关系") or {},
}

# 移除 None 值
normalized_profile = {k: v for k, v in normalized_profile.items() if v is not None and v != ""}
```

**处理逻辑**:
1. 检测并展平 `basic_info` 嵌套结构
2. 支持中英文键名映射（兼容性）
3. 过滤空值和 None 值
4. 记录调试日志便于排查

### 修复3: 前端数据刷新

**文件**: `frontend/src/pages/WorkflowPage.tsx`

**修改**: 在工作流执行完成后刷新角色数据

```typescript
queryClient.invalidateQueries({ queryKey: ['workflowProgress', id] });
queryClient.invalidateQueries({ queryKey: ['chapters', id] });
queryClient.invalidateQueries({ queryKey: ['characters', id] })  // 新增
```

## 数据流程

### 执行角色设计阶段

1. 用户点击"执行角色设计"
2. 前端调用 `workflowApi.executePhase`
3. 后端 `WorkflowEngine.run_phase` 执行阶段
4. `UnifiedCharacterDesignerAgent` 生成角色数据
5. `parse_result` 解析 LLM 返回的 JSON
6. `transition_to` 保存数据到工作流状态
7. `_save_phase_data` 调用 `_sync_characters_to_db`
8. `_sync_characters_to_db` 执行数据转换：
   - 展平 `basic_info` 结构
   - 映射中英文键名
   - 过滤空值
9. 同步到数据库 ✅
10. 前端刷新角色数据 ✅
11. 角色管理页面显示角色 ✅

## 测试验证

### 测试脚本

创建了 `test_character_profile_parsing.py` 验证数据转换逻辑：

```bash
python test_character_profile_parsing.py
```

**测试用例**:
1. 嵌套结构（basic_info）- 测试展平逻辑
2. 扁平结构 - 测试直接使用
3. 缺少部分字段 - 测试容错处理
4. 中文键名 - 测试键名映射
5. 完整嵌套示例 - 测试真实场景

**测试结果**:
```
[PASS] profile 展平逻辑可以处理各种格式
[PASS] 支持嵌套 basic_info 结构
[PASS] 支持中文键名映射
[PASS] 自动过滤空值
```

### 验证步骤

1. **重启后端**应用修复
   ```bash
   # 停止现有服务
   Ctrl+C

   # 重新启动
   cd d:/310Programm/KimiFiction/backend
   python -m uvicorn app.main:app --reload
   ```

2. **执行角色设计**
   - 打开工作流页面
   - 切换到"角色设计"阶段
   - 点击"执行角色设计"
   - 等待完成

3. **检查日志**
   - 查看是否显示"展平 profile.basic_info"
   - 查看是否显示"成功同步 X 个角色到数据库"

4. **验证角色管理页面**
   - 切换到"角色管理"页面
   - 检查是否显示新生成的角色
   - 点击角色卡片查看详细信息
   - 确认所有字段都正确显示

5. **运行诊断脚本**
   ```bash
   python test_character_design_sync.py <novel_id>
   ```

## 兼容性

修复后的代码兼容以下情况：

1. **LLM 返回扁平结构** - 直接使用
2. **LLM 返回嵌套 basic_info** - 自动展平
3. **LLM 使用中文键名** - 自动映射
4. **LLM 返回部分字段** - 过滤空值
5. **手动标记完成** - 同样支持数据转换

## 相关文件

- `backend/app/agents/unified_agent.py` - 优化提示词
- `backend/app/workflow_engine.py` - 添加数据转换逻辑
- `frontend/src/pages/WorkflowPage.tsx` - 刷新角色数据
- `test_character_profile_parsing.py` - 测试脚本
- `test_character_design_sync.py` - 诊断脚本

## 预期效果

修复后：
- ✅ 执行角色设计后，角色会正确同步到数据库
- ✅ 角色管理页面可以正常显示所有角色信息
- ✅ 角色卡片显示完整的 profile 数据（年龄、性别、MBTI等）
- ✅ 支持各种 LLM 返回格式
- ✅ 中英文键名自动兼容

## 下一步

1. 重启后端服务
2. 执行角色设计阶段
3. 验证角色管理页面
4. 如果仍有问题，查看日志并运行诊断脚本
