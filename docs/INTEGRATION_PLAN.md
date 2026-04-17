# KimiFiction 评测系统集成计划

## 当前状态

### Backend
- `rubric_evaluation_service.py`: 硬编码8维度的criteria，无LLM调用能力
- `/training/evaluate/{novel_id}` API: 只接受chapter_numbers列表，未接入实际评测
- 缺少调用LLM进行评判的能力

### Frontend
- `RubricEvaluation` 类型已定义 (types/index.ts)
- `listEvaluations` / `getEvaluation` API调用已存在
- **无评测入口页面/按钮**

### 评测脚本（独立）
- `evaluate_novels_llm.py`: 功能完整的LLM评测脚本
- `evaluate_rules_llm.csv`: 88条LLM评判规则
- 需要集成到后端服务

---

## 集成任务

### 1. 后端：创建评测API端点

**文件**: `backend/app/api/endpoints/evaluation.py` (新建)

```
POST /api/v1/evaluation/novel
  Body: { novel_id: int, chapter_number?: int }
  Response: { total_score, rank, dimensions: [...] }

POST /api/v1/evaluation/text
  Body: { text: string, rules_file?: string }
  Response: { total_score, rank, dimensions: [...] }

POST /api/v1/evaluation/reference/{filename}
  Body: {}
  Response: { total_score, rank, dimensions: [...] }
```

### 2. 后端：集成LLM评测服务

**修改**: `rubric_evaluation_service.py`

- 添加 `LLMEvaluationService` 类
- 调用DeepSeek API进行Yes/No判断
- 加载 `evaluate_rules_llm.csv` 规则文件

### 3. 前端：添加评测入口

**方案A**: 在 Dashboard 添加"评测"按钮
**方案B**: 新建 `Evaluation.tsx` 页面

推荐方案B，创建独立评测页面，包含：
- 选择评测模式（小说库 / 上传文本）
- 评测规则配置
- 评测结果展示（8维度雷达图）

---

## 实施步骤

1. [ ] 创建 `backend/app/api/endpoints/evaluation.py` API端点
2. [ ] 在 `rubric_evaluation_service.py` 添加LLM评测方法
3. [ ] 添加 `frontend/src/pages/Evaluation.tsx` 评测页面
4. [ ] 在 `App.tsx` 添加路由
5. [ ] 在 Dashboard 添加评测入口按钮
6. [ ] 测试联调

---

## 文件清单

| 文件 | 操作 |
|------|------|
| `backend/app/api/endpoints/evaluation.py` | 新建 |
| `backend/app/services/rubric_evaluation_service.py` | 修改 - 添加LLM评测 |
| `frontend/src/pages/Evaluation.tsx` | 新建 |
| `frontend/src/App.tsx` | 修改 - 添加路由 |
| `frontend/src/services/api.ts` | 修改 - 添加评测API |
| `evaluate_rules_llm.csv` | 移动到backend可访问位置 |
