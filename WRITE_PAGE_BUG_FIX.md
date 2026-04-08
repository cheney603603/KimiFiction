# 章节写作页面Bug修复

## 修复日期
2026-03-31

## 问题列表

### 1. 角色数据加载失败
**错误信息**:
```
[WorkflowEngine] 加载角色数据失败: name 'get_session' is not defined
```

**原因**:
- `get_session()` 是一个异步上下文管理器，需要使用 `async with` 语法
- 原代码错误地使用了 `async for db in get_session():` 语法

**修复位置**: `backend/app/workflow_engine.py`

**修复内容**:
- 将 `_load_characters_from_db()` 中的 `async for db in get_session()` 改为 `async with get_session() as db:`
- 将 `_sync_characters_to_db()` 中的相同问题一并修复

---

### 2. EmbeddingService 初始化错误
**错误信息**:
```
数据库事务回滚: EmbeddingService.__init__() takes 1 positional argument but 2 were given
```

**原因**:
- `EmbeddingService.__init__()` 不需要 `db` 参数
- `context_manager.py` 中错误地传入了 `db` 参数

**修复位置**: `backend/app/context_manager.py`

**修复内容**:
- 移除 `_get_db_session()` 方法
- 直接使用 `from app.core.database import get_session`
- `retrieve_relevant_context()` 中：将 `EmbeddingService(db)` 改为 `EmbeddingService()`
- `retrieve_chapter_context()` 中：将 `async with await self._get_db_session() as db:` 改为 `async with get_session() as db:`

---

### 3. 数据库上下文管理器错误
**错误信息**:
```
'_AsyncGeneratorContextManager' object has no attribute 'args'
```

**原因**:
- 错误地使用了 `await` 关键字在上下文管理器前
- 应该直接使用 `async with get_session() as db:` 而不是 `async with await get_session() as db:`

**修复位置**: `backend/app/context_manager.py`

**修复内容**:
- 移除 `_get_db_session()` 方法（它是多余的）
- 直接在需要的地方使用 `async with get_session() as db:`

---

### 4. Timeout 参数无法调整
**问题描述**:
- 章节写作页面的超时时间是固定的，用户无法根据需要调整
- 默认使用 `base_timeout * 3` 的固定值

**修复位置**:
- 后端: `backend/app/schemas/workflow.py`, `backend/app/api/endpoints/workflow.py`
- 前端: `frontend/src/services/api.ts`, `frontend/src/pages/ChapterWriter.tsx`

**修复内容**:

#### 后端修改:
1. `workflow.py` schema:
   - 在 `ChapterWriteRequest` 中添加 `timeout` 字段
   - 类型: `Optional[int]`
   - 范围: 30-3600秒
   - 描述: 超时时间（秒），不填则使用默认值

2. `endpoints/workflow.py`:
   - 修改超时计算逻辑
   - 如果请求中指定了 `timeout`，使用请求中的值
   - 否则使用默认的 `base_timeout * 3`

#### 前端修改:
1. `api.ts`:
   - 在 `writeChapter` 参数中添加 `timeout?: number`

2. `ChapterWriter.tsx`:
   - 在 `WritingSettings` 接口中添加 `timeout?: number`
   - 默认值设置为 900 秒（15分钟）
   - 添加 timeout 滑块控件
   - 范围: 60-3600秒（1分钟到1小时）
   - 步长: 60秒（1分钟）
   - 显示当前选择的时间
   - 提示用户建议范围: 600-1800秒（10-30分钟）

---

## 修复总结

### 修改的文件

#### 后端 (5个文件)
1. `backend/app/workflow_engine.py`
   - 修复 `get_session()` 使用方式
   - 添加 `_load_characters_from_db()` 方法
   - 添加 `_sync_characters_to_db()` 方法
   - 改进 `write_chapter()` 上下文构建

2. `backend/app/context_manager.py`
   - 移除 `_get_db_session()` 方法
   - 修复 `EmbeddingService` 初始化
   - 修复数据库会话使用方式

3. `backend/app/schemas/workflow.py`
   - 在 `ChapterWriteRequest` 中添加 `timeout` 字段

4. `backend/app/api/endpoints/workflow.py`
   - 支持使用请求中的 `timeout` 参数

5. `backend/app/services/embedding_service.py`
   - 确认 `__init__()` 不需要参数（无需修改）

#### 前端 (2个文件)
1. `frontend/src/services/api.ts`
   - 在 `writeChapter` 参数中添加 `timeout?: number`

2. `frontend/src/pages/ChapterWriter.tsx`
   - 添加 `timeout` 字段到设置
   - 添加 timeout 滑块控件
   - 更新 UI 显示和提示信息

---

## 功能改进

### 1. 角色数据同步
- 角色设计阶段完成后自动同步到数据库
- 章节写作时自动从数据库加载角色数据
- 支持创建新角色和更新已存在角色

### 2. 完整上下文支持
- 世界观设定
- 相关角色列表
- 前文摘要（从上一章）
- 章节细纲
- 用户可以在写作前预览所有上下文

### 3. 灵活的超时配置
- 用户可根据章节长度和网络情况调整超时
- 范围: 1分钟到1小时
- 默认15分钟
- 提供合理建议范围

### 4. 编辑和保存功能
- 生成后可编辑内容
- 编辑模式使用 textarea
- 支持创建新章节和更新已存在章节
- 保存前必须确认

---

## 使用说明

### 正常使用流程
1. 进入章节写作页面 (`/novel/:novelId/write`)
2. 选择要编写的章节编号
3. 点击"查看上下文"检查世界观、角色、前文摘要
4. 点击"查看细纲"确认章节大纲
5. 调整写作参数（可选）:
   - 文风
   - 环境描写级别
   - 对话占比
   - 写作注意事项
   - **请求超时时间（新增）**
6. 点击"开始生成"
7. 生成完成后，如需修改点击"编辑"
8. 确认后点击"保存到数据库"

### 超时时间建议
- **短章节（2000-3000字）**: 600-900秒（10-15分钟）
- **中等章节（3000-5000字）**: 900-1200秒（15-20分钟）
- **长章节（5000-8000字）**: 1200-1800秒（20-30分钟）
- **超长章节（8000字以上）**: 1800-3600秒（30-60分钟）

**影响因素**:
- LLM 模型速度
- 网络连接质量
- 服务器负载
- 章节复杂度

---

## 技术细节

### 数据库会话管理
正确用法:
```python
async with get_session() as db:
    # 使用 db 进行操作
    result = await db.execute(...)
    # 自动提交和关闭
```

错误用法:
```python
async for db in get_session():  # 错误：不是迭代器
async with await get_session() as db:  # 错误：不需要 await
```

### EmbeddingService 初始化
```python
# 正确
embedding_service = EmbeddingService()

# 错误
embedding_service = EmbeddingService(db)  # 不需要 db 参数
```

### 上下文构建
章节写作的完整上下文包括：
1. **世界设定** (world_setting): 来自工作流的世界观构建阶段
2. **角色状态** (characters): 来自数据库 characters 表
3. **冲突伏笔** (plot_setting): 来自工作流的剧情设计阶段
4. **大纲** (outline): 来自工作流的大纲阶段，包含章节细纲
5. **前文摘要** (previous_chapter_summary): 来自上一章的 summary 字段
6. **RAG检索结果**: 从向量数据库检索的相关记忆节点

---

## 测试建议

### 功能测试
1. ✅ 角色数据同步
   - 运行工作流角色设计阶段
   - 检查数据库 characters 表是否有数据
   - 进入章节写作页面，检查角色是否加载

2. ✅ 上下文显示
   - 进入章节写作页面
   - 点击"查看上下文"按钮
   - 验证世界观、角色、前文摘要正确显示

3. ✅ 超时配置
   - 调整超时时间滑块
   - 点击"开始生成"
   - 检查后端日志确认使用了正确的超时时间

4. ✅ 编辑和保存
   - 生成章节后点击"编辑"
   - 修改内容后点击"确认保存"
   - 检查数据库 chapters 表是否更新

### 错误测试
1. ✅ 网络超时
   - 设置较短的超时时间（如60秒）
   - 验证错误处理

2. ✅ 角色数据缺失
   - 清空角色表
   - 验证系统不会崩溃
   - 检查错误日志

3. ✅ 数据库连接失败
   - 停止数据库服务
   - 验证错误提示
   - 恢复后重试

---

## 注意事项

1. **角色同步是自动的**: 角色设计完成后会自动同步到数据库，无需手动操作

2. **超时时间要合理**: 过短会导致超时，过长浪费资源。建议根据章节长度和网络情况调整。

3. **编辑不会自动保存**: 修改后必须点击"确认保存"才会写入数据库

4. **上下文依赖工作流**: 完整的上下文需要工作流完成世界观构建、角色设计、大纲阶段

5. **数据库连接**: 确保 MySQL 服务正常运行，否则无法加载角色和保存章节

---

## 后续优化建议

1. **章节预览**: 在生成前显示预期内容和字数
2. **批量生成**: 支持一次生成多个章节
3. **版本管理**: 保存章节的历史版本
4. **快速插入**: 从角色卡快速插入角色描述到章节
5. **统计信息**: 显示章节的字数、角色出场次数等统计
6. **进度条优化**: 显示更详细的生成进度
