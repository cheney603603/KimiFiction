"""P2 产能工程模块测试（伏笔台账 / 设定预检 / 成本熔断）"""
import pytest

from app.services.foreshadowing_ledger import ForeshadowingLedger, merge_ledgers
from app.services.setting_precheck import (
    precheck_world_setting,
    precheck_characters,
    precheck_outline,
    precheck_all,
)
from app.services.cost_breaker import CostBreaker


class TestForeshadowingLedger:
    """伏笔台账"""

    def test_seed_and_overdue(self):
        ledger = ForeshadowingLedger()
        ledger.seed("身世之谜", seed_chapter=1, due_chapter=10)
        ledger.seed("旧怨", seed_chapter=1, due_chapter=5)

        assert ledger.overdue_items(current_chapter=6) == ["旧怨"]
        # 第 10 章：旧怨(应5)仍未回收 → 超期；身世之谜(应10)恰好到期，不算超期
        assert ledger.overdue_items(current_chapter=10) == ["旧怨"]

    def test_collect_clears_overdue(self):
        ledger = ForeshadowingLedger()
        ledger.seed("旧怨", seed_chapter=1, due_chapter=5)
        ledger.collect("旧怨")
        assert ledger.overdue_items(current_chapter=6) == []

    def test_open_items(self):
        ledger = ForeshadowingLedger()
        ledger.seed("A", seed_chapter=1, due_chapter=5)
        ledger.seed("B", seed_chapter=1, due_chapter=3)
        assert ledger.open_items(current_chapter=4) == ["A"]

    def test_seed_from_plot_idempotent(self):
        plot = {"unresolved_mysteries": ["身世之谜", "戒指的来历"]}
        created = ForeshadowingLedger.seed_from_plot(plot, current_chapter=1)
        assert len(created) == 2
        # 再跑一次，应覆盖同名（不产生重复键）
        again = ForeshadowingLedger.seed_from_plot(plot, current_chapter=2)
        assert len(again) == 2

    def test_merge_ledgers(self):
        base = {"A": {"status": "seeded"}}
        additions = {"B": {"status": "seeded"}}
        merged = merge_ledgers(base, additions)
        assert "A" in merged and "B" in merged


class TestSettingPrecheck:
    """设定预检"""

    def test_empty_world(self):
        issues = precheck_world_setting({})
        assert "世界观设定为空" in issues

    def test_missing_fields(self):
        issues = precheck_world_setting({"power_systems": []})
        assert any("地理" in i or "势力" in i or "geography" in i for i in issues)

    def test_character_missing_personality(self):
        issues = precheck_characters([{"name": "李云", "role_type": "protagonist"}])
        assert any("李云" in i for i in issues)

    def test_character_ok(self):
        issues = precheck_characters([{
            "name": "李云",
            "role_type": "protagonist",
            "profile": {"personality": "沉稳", "dialogue_style": "简洁"},
        }])
        assert issues == []

    def test_outline_missing_summary(self):
        issues = precheck_outline({"key_points": ["A"]})
        assert any("summary" in i for i in issues)

    def test_precheck_all(self):
        report = precheck_all({"world_setting": {}, "characters": [], "outline": {}})
        assert set(report.keys()) == {"world_setting", "characters", "outline"}


class TestCostBreaker:
    """成本熔断"""

    def test_allow_within_budget(self):
        breaker = CostBreaker(budget_per_chapter=8)
        assert breaker.should_rewrite(used_calls=3) is True

    def test_block_when_exhausted(self):
        breaker = CostBreaker(budget_per_chapter=5)
        assert breaker.should_rewrite(used_calls=5) is False
        assert breaker.should_rewrite(used_calls=4, next_call_cost=2) is False

    def test_estimate_from_loop_history(self):
        breaker = CostBreaker()
        assert breaker.estimate_used_calls([1, 2, 3]) == 3
        assert breaker.estimate_used_calls([]) == 0
