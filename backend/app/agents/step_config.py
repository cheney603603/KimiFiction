"""
Agent ReAct 步数配置
======================

各 Agent 的 ReAct 循环最大步数配置。

为什么需要区分步数：
- demand_analysis：只需分类，2 步够
- world_building：需要构建力量体系/社会/地理，5 步
- character_design：涉及多角色关系，4 步
- outline_draft：长篇结构规划，5 步
- chapter_writing：生成任务不需要太多反思，3 步
- review：评估类，3 步

使用方式：
    from app.agents.step_config import AGENT_STEP_CONFIG
    max_steps = AGENT_STEP_CONFIG["UnifiedWorldBuilderAgent"]  # → 5

或者在 workflow_engine 中运行时覆盖：
    context["agent_loop_steps"] = 6
"""

from typing import Dict

# 键为 Agent 类名，值为最大 ReAct 步数
AGENT_STEP_CONFIG: Dict[str, int] = {
    # ── 规划阶段 ──────────────────────────────────────────
    "GenreAnalyzerAgent":      2,   # 简单分类任务，2步足够
    "AnalyzerAgent":            2,

    # ── 设计阶段（复杂，需要多轮推理）───────────────────
    "UnifiedWorldBuilderAgent":    5,   # 世界观：力量体系/社会结构/地理/历史
    "WorldBuilderAgent":           5,
    "UnifiedCharacterDesignerAgent": 4,  # 角色：多角色关系/性格弧线
    "CharacterDesignerAgent":       4,

    # ── 冲突与大纲（结构规划，需要全局思考）────────────
    "UnifiedPlotDesignerAgent":     5,   # 冲突/伏笔/悬念系统
    "PlotDesignerAgent":            5,
    "UnifiedOutlineGeneratorAgent":  5,  # 大纲：情节弧/章节结构
    "OutlineGeneratorAgent":         5,

    # ── 写作阶段（生成为主，反思为辅）──────────────────
    "ChapterWriterAgent":          3,   # 生成任务，3步足够
    "WriterAgent":                  3,

    # ── 评估阶段 ────────────────────────────────────────
    "ReaderAgent":                 3,   # 评估，3步
    "ReviewerAgent":               3,   # 审核，3步
    "ConsistencyCheckerAgent":      3,

    # ── 默认值 ──────────────────────────────────────────
    "BaseAgent":                   3,
}

# 温度配置（可选扩展：各 Agent 默认温度）
AGENT_TEMPERATURE_CONFIG: Dict[str, float] = {
    # 规划/分析类：低温度保证一致性
    "GenreAnalyzerAgent":      0.3,
    "AnalyzerAgent":            0.3,
    "UnifiedWorldBuilderAgent": 0.4,
    "WorldBuilderAgent":         0.4,

    # 创意类：适中温度
    "UnifiedCharacterDesignerAgent": 0.5,
    "CharacterDesignerAgent":       0.5,
    "UnifiedPlotDesignerAgent":     0.5,
    "PlotDesignerAgent":            0.5,
    "UnifiedOutlineGeneratorAgent":  0.5,
    "OutlineGeneratorAgent":         0.5,

    # 生成类：较高温度保证多样性
    "ChapterWriterAgent":   0.7,   # 默认 0.7
    "WriterAgent":           0.7,

    # 评估类：低温度保证稳定
    "ReaderAgent":      0.3,
    "ReviewerAgent":    0.3,
}
