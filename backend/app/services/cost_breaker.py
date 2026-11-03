"""
成本熔断（P2）
============

章节级成本熔断：当单章 LLM 调用次数逼近预算上限时，跳过"定向重写/盲评"等
额外大调用，直接标记 flagged 待人工，避免成本失控（§7 成本约束）。
"""
from typing import Dict, Any
from loguru import logger

DEFAULT_BUDGET_PER_CHAPTER = 8


class CostBreaker:
    """单章 LLM 调用预算断路器。"""

    def __init__(self, budget_per_chapter: int = DEFAULT_BUDGET_PER_CHAPTER):
        self.budget_per_chapter = budget_per_chapter

    def should_rewrite(self, used_calls: int, next_call_cost: int = 1) -> bool:
        """判断是否允许发起下一次大调用（重写等）。"""
        allowed = used_calls + next_call_cost <= self.budget_per_chapter
        if not allowed:
            logger.warning(
                f"[CostBreaker] 单章调用 {used_calls} 已接近预算 {self.budget_per_chapter}，"
                f"跳过后续大调用"
            )
        return allowed

    def estimate_used_calls(self, loop_history: list) -> int:
        """从对抗循环历史估算已用大调用次数。"""
        return max(len(loop_history or []), 0)

    @classmethod
    def from_params(cls, params: Dict[str, Any]) -> "CostBreaker":
        budget = int(params.get("llm_call_budget_per_chapter") or DEFAULT_BUDGET_PER_CHAPTER)
        return cls(budget_per_chapter=budget)
