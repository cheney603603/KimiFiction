"""
伏笔台账（P2）
=============

管理小说伏笔的埋设/应回收/已回收状态，供硬门禁规则6判定"超期未回收项"。

存储：以字典形式挂在工作流状态或传入即可（纯逻辑，无 IO 依赖，便于测试）。
"""
from typing import Any, Dict, List, Optional


class ForeshadowingLedger:
    """伏笔台账（纯逻辑，作用于 ledger dict）。"""

    STATUS_SEEDED = "seeded"       # 已埋设
    STATUS_COLLECTED = "collected"  # 已回收

    def __init__(self, ledger: Optional[Dict[str, Any]] = None):
        self.ledger: Dict[str, Any] = ledger if ledger is not None else {}

    def seed(self, item: str, seed_chapter: int, due_chapter: int = 0) -> Dict[str, Any]:
        """登记一条伏笔；同名重复埋设视为更新。"""
        rec = {
            "item": item,
            "seed_chapter": seed_chapter,
            "due_chapter": due_chapter or seed_chapter + 10,  # 默认 10 章内回收
            "status": self.STATUS_SEEDED,
        }
        self.ledger[item] = rec
        return rec

    def collect(self, item: str) -> Optional[Dict[str, Any]]:
        """回收一条伏笔。"""
        rec = self.ledger.get(item)
        if rec:
            rec["status"] = self.STATUS_COLLECTED
        return rec

    def overdue_items(self, current_chapter: int) -> List[str]:
        """返回超过应回收章仍未回收的伏笔项。"""
        return [
            item
            for item, rec in self.ledger.items()
            if rec.get("status") == self.STATUS_SEEDED
            and rec.get("due_chapter", 0) < current_chapter
        ]

    def open_items(self, current_chapter: int) -> List[str]:
        """返回当前未回收且未超期的伏笔项（用于注入上下文提醒作者）。"""
        return [
            item
            for item, rec in self.ledger.items()
            if rec.get("status") == self.STATUS_SEEDED
            and rec.get("due_chapter", 0) >= current_chapter
        ]

    @classmethod
    def seed_from_plot(cls, plot_setting: Dict[str, Any], current_chapter: int) -> List[Dict[str, Any]]:
        """从剧情设定中的伏笔候选字段批量埋设（幂等：已存在则跳过）。"""
        created = []
        ledger = cls()
        candidates = []
        for key in ("unresolved_mysteries", "foreshadowing", "伏笔"):
            v = plot_setting.get(key, [])
            if isinstance(v, list):
                candidates.extend(v)
            elif isinstance(v, dict):
                candidates.extend(v.keys())
        for cand in candidates:
            if isinstance(cand, str) and cand.strip():
                ledger.seed(cand.strip(), current_chapter)
                created.append(ledger.ledger[cand.strip()])
        return created


def merge_ledgers(base: Dict[str, Any], additions: Dict[str, Any]) -> Dict[str, Any]:
    """合并台账（新增项不覆盖已存在项）。"""
    merged = dict(base)
    for item, rec in additions.items():
        if item not in merged:
            merged[item] = rec
    return merged
