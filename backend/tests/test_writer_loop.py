"""WriterReaderLoop 容错单元测试（失败轮次无 reward 不崩溃；全部失败不产出空章节）。"""
from unittest.mock import AsyncMock

import pytest

from app.writer_reader_loop import WriterReaderLoop


def _make_loop(history):
    loop = WriterReaderLoop.__new__(WriterReaderLoop)
    loop.loop_history = history
    loop.best_reward = -999
    loop.chapter_number = 5
    return loop


class TestLearningReportTolerance:
    def test_failure_entry_without_reward(self):
        """Writer 失败轮次（无 reward 键）不应让 get_learning_report 抛 KeyError。"""
        loop = _make_loop([
            {"round": 1, "action": "GENERATE", "success": False, "error": "LLM 403"},
        ])
        report = loop.get_learning_report()
        assert report["total_rounds"] == 1
        assert report["reward_progression"] == [0.0]

    def test_mixed_failure_and_success(self):
        loop = _make_loop([
            {"round": 1, "action": "GENERATE", "success": False, "error": "timeout"},
            {"round": 2, "action": "GENERATE", "reward": 0.8, "reader_score": 0.7,
             "hook_score": 0.6, "continue_reading": True, "passed": True,
             "reader_feedback": {}, "draft_length": 3000},
        ])
        loop.best_reward = 0.8
        report = loop.get_learning_report()
        assert report["reward_progression"] == [0.0, 0.8]
        assert report["reward_improvement"] == 0.8

    def test_no_history(self):
        loop = _make_loop([])
        report = loop.get_learning_report()
        assert report["status"] == "no_history"


class TestEmptyDraftNotSuccess:
    async def _run_with_writer_failing(self):
        loop = WriterReaderLoop(novel_id=1, chapter_number=1, max_rounds=3)
        loop._writer_act = AsyncMock(return_value={
            "success": False, "error": "DeepSeek API 返回 HTTP 503: 资源池已满",
        })
        return await loop.run(outline={"summary": "s"}, characters=[], context={})

    @pytest.mark.asyncio
    async def test_all_writer_rounds_failed_returns_failure(self):
        """Writer 全部轮次失败且无产出 → run() 必须返回 success=False（不得存空章节）。"""
        result = await self._run_with_writer_failing()
        assert result["success"] is False
        assert result.get("final_draft") == ""
        assert "未产出正文" in result.get("error", "")
