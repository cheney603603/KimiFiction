"""
训练数据工具模块（RL 算法已移除）
==================================

保留非 RL 的质量度量与数据侧工具（NOVEL_QUALITY_UPGRADE_PLAN §6.2）：
- LLMJudge        : LLM-as-Judge 盲评工具，供异构评审使用
- DataQualityAuditor : 训练数据质量审计

已移除：GRPO/TPO/模仿学习/LoRA/训练编排/硬件配置（§6.1）
"""

from app.training.llm_judge import (
    LLMJudge,
    JudgeDimension,
    DimensionScore,
    JudgeVerdict,
    ComparisonResult,
)
from app.training.data_quality_audit import (
    DataQualityAuditor,
    AuditResult,
    QualityIssue,
)

__all__ = [
    # LLM-as-Judge
    "LLMJudge",
    "JudgeDimension",
    "DimensionScore",
    "JudgeVerdict",
    "ComparisonResult",
    # 数据质量审计
    "DataQualityAuditor",
    "AuditResult",
    "QualityIssue",
]
