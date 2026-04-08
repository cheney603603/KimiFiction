# JSON 解析问题修复

## 问题描述

**错误日志**：
```
[GenreAnalyzer] JSON解析失败 {"error": "Expecting value: line 1 column 1 (char 0)"}
```

**现象**：
- LLM 确实返回了 JSON 数据
- 但解析仍然失败
- 日志显示 `GenreAnalyzer LLM响应: JSON\n{...` 说明响应被截断

## 问题根因

1. **日志截断**：loguru 日志在显示时对长字符串进行了截断（显示 `...`），但实际响应是完整的
2. **解析不够健壮**：原来的解析逻辑只能处理 ` ```json ` 代码块，不支持其他格式
3. **缺少多种解析策略**：没有处理嵌套 JSON、边界不完整等情况

## 修复方案

### 1. 创建通用 JSON 解析工具
**文件**：`backend/app/core/json_utils.py`（新建）

提供多种 JSON 提取策略：
- 提取 ` ```json ` 代码块
- 提取 ` ``` ` 代码块
- 正则表达式查找 JSON 对象
- 正则表达式查找 JSON 数组
- 查找 `{` 开始 `}` 结束边界
- 处理嵌套 JSON

### 2. 更新所有 Agent 使用通用解析工具

| 文件 | 修改内容 |
|------|----------|
| `analyzer.py` | 使用 `extract_json_from_response()` |
| `character_designer.py` | 使用 `extract_json_from_response()` |
| `outline_generator.py` | 使用 `extract_json_from_response()` |
| `world_builder.py` | 替换 `_extract_json()` 方法 |
| `plot_designer.py` | 替换 `_extract_json()` 方法 |
| `consistency_checker.py` | 使用 `extract_json_from_response()` |
| `memory_manager.py` | 使用 `extract_json_from_response()` |
| `reviewer.py` | 替换 `_extract_json()` 方法 |

### 3. 增强日志输出

在 `llm_service.py` 中添加：
```python
logger.debug(f"[LLM] 返回数据类型: {type(data).__name__}, 长度: {len(data) if isinstance(data, str) else 'N/A'}")
```

## 修改的文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `backend/app/core/json_utils.py` | 新建 | 通用 JSON 解析工具 |
| `backend/app/agents/analyzer.py` | 修改 | 使用通用解析工具 |
| `backend/app/agents/character_designer.py` | 修改 | 使用通用解析工具 |
| `backend/app/agents/outline_generator.py` | 修改 | 使用通用解析工具 |
| `backend/app/agents/world_builder.py` | 修改 | 替换 `_extract_json()` |
| `backend/app/agents/plot_designer.py` | 修改 | 替换 `_extract_json()` |
| `backend/app/agents/consistency_checker.py` | 修改 | 使用通用解析工具 |
| `backend/app/agents/memory_manager.py` | 修改 | 使用通用解析工具 |
| `backend/app/agents/reviewer.py` | 修改 | 替换 `_extract_json()` |
| `backend/app/services/llm_service.py` | 修改 | 增强日志输出 |

## 验证步骤

1. **访问前端**：http://localhost:5173
2. **保存 LLM 配置**（如果还没保存）
3. **执行需求分析**
4. **检查日志**，应该显示：
   ```
   [LLM] 返回数据类型: str, 长度: XXXX
   [GenreAnalyzer] 收到LLM响应 {"response_length": XXXX}
   [GenreAnalyzer] 类型分析完成 {"genre": "...", "sub_genres": [...]}
   ```

## JSON 解析工具使用示例

```python
from app.core.json_utils import extract_json_from_response

response = await llm_service.chat(messages)

# 使用通用解析
result, message = extract_json_from_response(response)

if result:
    print(f"解析成功: {result}")
else:
    print(f"解析失败: {message}")
```

## 后续优化建议

1. **流式响应支持**：处理 LLM 的流式输出
2. **自动修复**：尝试修复不完整的 JSON
3. **格式验证**：在发送前验证 JSON 格式
4. **错误恢复**：在解析失败时使用备用模型

---

**修复日期**：2026-03-31
**修复状态**：✅ 已完成
