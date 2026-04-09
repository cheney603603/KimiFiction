# KimiFiction RL训练数据采集与评测系统

## 概述

本系统为KimiFiction的Writer-Reader RL对抗训练提供完整的数据采集和评测能力：

1. **训练数据采集器** (`TrainingDataCollector`) - 记录每一轮的状态、动作、奖励
2. **Rubric评测系统** (`RubricEvaluationService`) - 基于知识库的结构化评分
3. **前后对比报告** - 可视化训练效果，量化改进幅度

## 核心组件

### 1. 数据模型 (`app/models/rubric.py`)

| 模型 | 用途 |
|------|------|
| `RubricTemplate` | Rubric评测模板定义 |
| `RubricDimension` | 评分维度（8个维度） |
| `RubricEvaluation` | 单次评测记录 |
| `TrainingEpisode` | RL训练回合数据 |
| `TrainingBatch` | 训练批次聚合 |
| `ComparisonReport` | 训练前后对比报告 |

### 2. Rubric评测维度

系统基于以下8个维度进行结构化评分：

| 维度 | 权重 | 说明 |
|------|------|------|
| 情节一致性 | 20% | 情节发展、伏笔回收、时间线 |
| 逻辑合理性 | 20% | 事件逻辑、动机合理性、世界观自洽 |
| 风格匹配度 | 15% | 类型风格、语言风格、叙事节奏 |
| 角色一致性 | 15% | 性格一致、成长合理、行为符合人设 |
| 世界观一致性 | 10% | 设定无矛盾、力量体系一致 |
| 叙事流畅度 | 10% | 段落过渡、场景切换、节奏控制 |
| 情感冲击力 | 5% | 情感真实、高潮感染力 |
| 钩子强度 | 5% | 开头吸引、结尾悬念、追读欲望 |

权重会根据小说类型自动调整（如悬疑类增强情节和钩子权重）。

### 3. 文件结构

```
KimiFiction/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   │   ├── rubric.py              # 数据模型
│   │   │   ├── novel.py               # 已添加关系
│   │   │   └── chapter.py             # 已添加关系
│   │   └── services/
│   │       ├── rubric_evaluation_service.py  # Rubric评测服务
│   │       └── training_data_collector.py    # 训练数据采集
│   └── demo_rl_training.py            # 使用演示
└── test_project/                      # 训练数据保存目录
    └── training_data/
        └── {batch_name}/
            ├── episodes/              # 回合数据
            ├── evaluations/           # 评测结果
            └── reports/               # 对比报告
```

## 使用方法

### 快速开始

```python
import asyncio
from app.services.training_data_collector import TrainingDataCollector

async def train_with_collection():
    novel_id = 1
    project_path = "D:\\310Programm\\KimiFiction\\test_project"
    
    async with TrainingDataCollector(
        novel_id=novel_id,
        project_path=project_path,
        batch_name="my_first_batch"
    ) as collector:
        
        # 1. 训练前评测（基线）
        pre_eval = await collector.evaluate_before_training([1, 2, 3])
        
        # 2. 运行RL训练，采集数据
        for episode in range(1, 11):
            await collector.collect_episode(
                chapter_number=1,
                episode_number=episode,
                round_number=1,
                state_draft="当前草稿内容...",
                action_taken="generate",
                action_probs={"generate": 0.5, "revise": 0.3, ...},
                reward=0.8,
                reader_score=7.5,
                rubric_score=7.8,
                is_terminal=(episode == 10)
            )
        
        # 3. 训练后评测
        post_eval = await collector.evaluate_after_training([1, 2, 3])
        
        # 4. 生成对比报告
        report = await collector.generate_comparison_report(pre_eval, post_eval)
        
        print(f"改进率: {report['summary']['improvement_rate']}")

asyncio.run(train_with_collection())
```

### 运行演示

```bash
# 完整流程演示
cd D:\310Programm\KimiFiction\backend
python demo_rl_training.py --mode full

# 仅Rubric评测
demo_rl_training.py --mode rubric

# 仅训练采集
demo_rl_training.py --mode training
```

### 单独使用Rubric评测

```python
from app.services.rubric_evaluation_service import RubricEvaluationService

service = RubricEvaluationService(novel_id=1)
await service.initialize(genre="玄幻")

# 评测单章
result = await service.evaluate_chapter(
    chapter_number=1,
    chapter_content="章节内容...",
    eval_type="mid_training"
)

print(f"总分: {result['total_score']}")
print(f"各维度: {result['dimension_scores']}")
```

## 数据存储

### 数据库存储

所有数据保存在MySQL数据库中：
- `rubric_templates` - 评测模板
- `rubric_dimensions` - 维度评分详情
- `rubric_evaluations` - 评测记录
- `training_episodes` - 训练回合
- `training_batches` - 训练批次
- `comparison_reports` - 对比报告

### 文件存储

同时导出JSON文件便于分析：
```
training_data/
└── {batch_name}/
    ├── episodes/
    │   ├── episode_0001_ch001.json
    │   └── ...
    ├── evaluations/
    │   ├── pre_training_ch001.json
    │   ├── post_training_ch001.json
    │   ├── pre_training_summary.json
    │   └── post_training_summary.json
    └── reports/
        ├── comparison_report.json
        └── comparison_report.txt
```

## 评测流程

### 训练前评测（基线）

1. 构建Rubric（基于小说类型和知识库）
2. 对每个维度调用Reader Agent评分
3. 检查一致性（角色、情节、世界观）
4. 生成基线分数和反馈

### 训练中采集

1. 记录状态（当前草稿）
2. 记录动作（generate/revise/delete/keep）
3. 记录奖励（Reader评分 + Rubric评分）
4. 保存到数据库和JSON文件

### 训练后评测

1. 使用相同Rubric重新评测
2. 对比各维度分数变化
3. 识别改进和退步领域
4. 生成可视化报告

## 报告内容

对比报告包含：

- **总体改进**: 训练前后平均分对比
- **维度分析**: 各维度改进幅度排序
- **章节对比**: 逐章前后分数对比
- **关键发现**: 自动识别的关键结论
- **改进建议**: 基于数据的优化建议

## 与WriterReaderRL集成

在实际RL循环中使用：

```python
from app.writer_reader_rl import WriterReaderRL
from app.services.training_data_collector import TrainingDataCollector

async def run_rl_with_collection():
    async with TrainingDataCollector(...) as collector:
        # 训练前评测
        pre_eval = await collector.evaluate_before_training([1])
        
        # 创建RL循环
        rl = WriterReaderRL(
            novel_id=1,
            chapter_number=1,
            initial_draft="初始草稿"
        )
        
        # 运行多轮对抗
        for round_num in range(1, max_rounds + 1):
            result = await rl.run_single_round()
            
            # 采集数据
            await collector.collect_episode(
                chapter_number=1,
                episode_number=round_num,
                round_number=round_num,
                state_draft=result["state"].draft,
                action_taken=result["action"],
                action_probs=result["action_probs"],
                reward=result["reward"],
                reader_score=result["reader_score"],
                is_terminal=result["is_terminal"]
            )
            
            if result["is_terminal"]:
                break
        
        # 训练后评测和报告
        post_eval = await collector.evaluate_after_training([1])
        report = await collector.generate_comparison_report(pre_eval, post_eval)
```

## 注意事项

1. **数据库迁移**: 新模型需要执行数据库迁移
   ```bash
   alembic revision --autogenerate -m "add rubric and training tables"
   alembic upgrade head
   ```

2. **Ollama服务**: 确保Ollama运行且`deepseek-r1:8b`已导入

3. **数据目录**: 确保项目目录有写入权限

4. **人工评测**: 系统支持人工覆盖自动评分，但目前先用缺省模式

## 后续扩展

- [ ] 可视化图表（matplotlib/plotly）
- [ ] 多批次对比分析
- [ ] 在线监控面板
- [ ] 自动超参调优建议
