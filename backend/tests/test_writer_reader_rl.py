"""Writer-Reader 写作对抗循环单元测试（RL 移除版）"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from app.writer_reader_loop import (
    WritingState,
    RewardFunction,
    WriterReaderLoop,
)
from app.models.writing_action import WritingAction


class TestRewardFunction:
    """测试 Reward 函数"""

    def test_compute_basic_reward(self):
        """测试基本评分计算"""
        rf = RewardFunction()

        reader_feedback = {
            "reader_score": 0.85,
            "hook_score": 0.78,
            "immersion_score": 0.80,
            "continuity_score": 0.75,
        }

        reward, breakdown = rf.compute(
            reader_feedback=reader_feedback,
            draft="测试内容" * 500,  # 约3000字
        )

        assert 0 <= reward <= 1, f"Reward应在0-1之间，实际: {reward}"
        assert "reader_score" in breakdown
        assert "hook_score" in breakdown

    def test_word_count_penalty_sign(self):
        """B5 修复：字数不足应为负贡献（此前为正数，越短得分越高）"""
        rf = RewardFunction()

        short_draft = "短文本"
        _, breakdown_short = rf.compute(
            reader_feedback={"reader_score": 0.5, "hook_score": 0.5},
            draft=short_draft,
        )
        # 字数严重不足 → 惩罚应为负值
        assert breakdown_short["word_count_penalty"] < 0, (
            f"字数不足时 penalty 应为负，实际: {breakdown_short['word_count_penalty']}"
        )

        over_draft = "超长文本" * 2000
        _, breakdown_over = rf.compute(
            reader_feedback={"reader_score": 0.5, "hook_score": 0.5},
            draft=over_draft,
        )
        assert breakdown_over["word_count_penalty"] < 0

        good_draft = "测试内容" * 750  # 约 3000 字，落在容差区间
        _, breakdown_good = rf.compute(
            reader_feedback={"reader_score": 0.5, "hook_score": 0.5},
            draft=good_draft,
        )
        assert breakdown_good["word_count_penalty"] == 0

    def test_revision_bonus_on_improvement(self):
        """有改进时修订应得正奖励"""
        rf = RewardFunction()

        prev = {"reader_score": 0.6, "hook_score": 0.5}
        curr = {"reader_score": 0.8, "hook_score": 0.7}

        reward, breakdown = rf.compute(
            reader_feedback=curr,
            previous_feedback=prev,
            draft="测试内容" * 500,
            action=WritingAction.REVISE,
        )

        assert breakdown["revision_bonus"] > 0
        assert reward >= 0

    def test_compute_batch_rewards(self):
        """批量评分"""
        rf = RewardFunction()

        feedbacks = [
            {"reader_score": 0.9, "hook_score": 0.8},
            {"reader_score": 0.6, "hook_score": 0.5},
            {"reader_score": 0.7, "hook_score": 0.7},
        ]

        rewards = rf.compute_batch_rewards(feedbacks)

        assert len(rewards) == len(feedbacks)
        assert all(0 <= r <= 1 for r in rewards)


class TestWritingState:
    """测试写作状态"""

    def test_state_init(self):
        """测试状态初始化"""
        state = WritingState(
            chapter_number=5,
            draft="测试内容",
        )

        assert state.chapter_number == 5
        assert state.draft == "测试内容"
        assert state.draft_version == 0
        assert state.action_history == []
        assert state.reward_history == []

    def test_state_to_dict(self):
        """测试状态序列化"""
        state = WritingState(
            chapter_number=5,
            draft="测试内容" * 100,
        )

        d = state.to_dict()

        assert d["chapter_number"] == 5
        assert "draft_version" in d
        assert "action_history_count" in d


class TestWriterReaderLoop:
    """测试 Writer-Reader 对抗循环"""

    @pytest.fixture
    def mock_writer_agent(self):
        """模拟Writer Agent"""
        agent = AsyncMock()
        agent.process = AsyncMock(return_value={
            "success": True,
            "content": "这是生成的章节内容" * 100,
            "word_count": 3000,
        })
        return agent

    @pytest.fixture
    def mock_reader_agent(self):
        """模拟Reader Agent"""
        agent = AsyncMock()
        agent.process = AsyncMock(return_value={
            "success": True,
            "reader_feedback": {
                "reader_score": 0.8,
                "hook_score": 0.75,
                "immersion_score": 0.78,
                "continuity_score": 0.7,
                "would_continue_reading": True,
                "confusing_points": [],
            }
        })
        return agent

    @pytest.mark.asyncio
    async def test_loop_init(self, mock_novel_id):
        """测试循环初始化"""
        loop = WriterReaderLoop(
            novel_id=mock_novel_id,
            chapter_number=1,
            max_rounds=3,
            score_threshold=0.75,
        )

        assert loop.novel_id == mock_novel_id
        assert loop.max_rounds == 3
        assert loop.score_threshold == 0.75
        assert loop.current_state is None

    @pytest.mark.asyncio
    async def test_run_generates_draft(
        self,
        mock_writer_agent,
        mock_reader_agent,
        mock_chapter_outline,
        mock_characters,
        mock_chapter_content,
    ):
        """测试完整对抗循环"""
        with patch('app.writer_reader_loop.ChapterWriterAgent', return_value=mock_writer_agent), \
             patch('app.writer_reader_loop.ReaderAgent', return_value=mock_reader_agent):

            loop = WriterReaderLoop(
                novel_id=1,
                chapter_number=5,
                max_rounds=3,
                score_threshold=0.6,  # 设置较低阈值确保通过
            )

            result = await loop.run(
                outline=mock_chapter_outline,
                characters=mock_characters,
                context={"writing_style": "叙事流畅"},
                initial_draft="",
            )

            assert result.get("success") is True
            assert "final_draft" in result
            assert result["final_draft"] != ""
            assert "loop_history" in result
            assert len(result["loop_history"]) >= 1

    @pytest.mark.asyncio
    async def test_loop_history_has_reader_feedback(
        self,
        mock_writer_agent,
        mock_reader_agent,
        mock_chapter_outline,
        mock_characters,
    ):
        """B8 修复：loop_history 元素必须含 reader_feedback，保证下游取到非空反馈"""
        with patch('app.writer_reader_loop.ChapterWriterAgent', return_value=mock_writer_agent), \
             patch('app.writer_reader_loop.ReaderAgent', return_value=mock_reader_agent):

            loop = WriterReaderLoop(
                novel_id=1,
                chapter_number=1,
                max_rounds=2,
                score_threshold=0.9,  # 阈值高 → 跑满2轮
            )

            result = await loop.run(
                outline=mock_chapter_outline,
                characters=mock_characters,
                context={},
            )

            for entry in result["loop_history"]:
                assert "reader_feedback" in entry
                assert isinstance(entry["reader_feedback"], dict)
                assert entry["reader_feedback"] != {}

    @pytest.mark.asyncio
    async def test_reader_receives_context(
        self,
        mock_writer_agent,
        mock_reader_agent,
        mock_chapter_outline,
        mock_characters,
        mock_world_setting,
    ):
        """B7 修复：Reader 应收到前文/角色/世界观上下文"""
        captured = {}

        async def spy_reader(context):
            captured.update(context)
            return {
                "success": True,
                "reader_feedback": {
                    "reader_score": 0.9,
                    "hook_score": 0.9,
                    "would_continue_reading": True,
                    "confusing_points": [],
                }
            }

        mock_reader_agent.process = spy_reader

        with patch('app.writer_reader_loop.ChapterWriterAgent', return_value=mock_writer_agent), \
             patch('app.writer_reader_loop.ReaderAgent', return_value=mock_reader_agent):

            loop = WriterReaderLoop(
                novel_id=1,
                chapter_number=1,
                max_rounds=1,
                score_threshold=0.8,
            )

            await loop.run(
                outline=mock_chapter_outline,
                characters=mock_characters,
                context={
                    "world_setting": mock_world_setting,
                    "plot_setting": {"main_plot": "寻亲"},
                    "unresolved_mysteries": ["身世之谜"],
                },
            )

            assert "world_setting" in captured
            assert "characters" in captured
            assert "unresolved_mysteries" in captured
            assert captured["world_setting"] is mock_world_setting
            assert captured["unresolved_mysteries"] == ["身世之谜"]

    @pytest.mark.asyncio
    async def test_early_stopping_on_threshold(
        self,
        mock_writer_agent,
        mock_reader_agent,
        mock_chapter_outline,
        mock_characters,
    ):
        """测试达到阈值时早停"""
        mock_reader_agent.process = AsyncMock(return_value={
            "success": True,
            "reader_feedback": {
                "reader_score": 0.95,
                "hook_score": 0.90,
                "would_continue_reading": True,
                "confusing_points": [],
            }
        })

        with patch('app.writer_reader_loop.ChapterWriterAgent', return_value=mock_writer_agent), \
             patch('app.writer_reader_loop.ReaderAgent', return_value=mock_reader_agent):

            loop = WriterReaderLoop(
                novel_id=1,
                chapter_number=1,
                max_rounds=5,
                score_threshold=0.78,
            )

            result = await loop.run(
                outline=mock_chapter_outline,
                characters=mock_characters,
                context={},
            )

            assert result["total_rounds"] == 1
            assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_max_rounds_limit(
        self,
        mock_writer_agent,
        mock_reader_agent,
        mock_chapter_outline,
        mock_characters,
    ):
        """测试最大轮次限制"""
        mock_reader_agent.process = AsyncMock(return_value={
            "success": True,
            "reader_feedback": {
                "reader_score": 0.4,
                "hook_score": 0.3,
                "would_continue_reading": False,
                "confusing_points": ["问题1", "问题2"],
            }
        })

        with patch('app.writer_reader_loop.ChapterWriterAgent', return_value=mock_writer_agent), \
             patch('app.writer_reader_loop.ReaderAgent', return_value=mock_reader_agent):

            loop = WriterReaderLoop(
                novel_id=1,
                chapter_number=1,
                max_rounds=3,
                score_threshold=0.9,
            )

            result = await loop.run(
                outline=mock_chapter_outline,
                characters=mock_characters,
                context={},
            )

            assert result["total_rounds"] == 3
            assert result["passed"] is False

    def test_get_learning_report(self):
        """测试循环报告生成"""
        loop = WriterReaderLoop(
            novel_id=1,
            chapter_number=1,
            max_rounds=3,
        )

        loop.loop_history = [
            {"round": 1, "reward": 0.5, "reader_score": 0.5, "passed": False},
            {"round": 2, "reward": 0.7, "reader_score": 0.7, "passed": False},
        ]
        loop.best_reward = 0.7

        report = loop.get_learning_report()

        assert "chapter" in report
        assert "reward_progression" in report
        assert report["reward_progression"] == [0.5, 0.7]
        assert abs(report["reward_improvement"] - 0.2) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
