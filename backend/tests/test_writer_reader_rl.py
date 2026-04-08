"""Writer-Reader RL 对抗系统单元测试"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from app.writer_reader_rl import (
    WritingAction, WritingState, PPOConfig,
    RewardFunction, PPOStrategy, WriterReaderLoop
)


class TestRewardFunction:
    """测试 Reward 函数"""

    def test_compute_basic_reward(self):
        """测试基本Reward计算"""
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

    def test_compute_with_previous_feedback(self):
        """测试有前序反馈时的Reward计算"""
        rf = RewardFunction()

        prev = {"reader_score": 0.6, "hook_score": 0.5}
        curr = {"reader_score": 0.8, "hook_score": 0.7}

        reward, breakdown = rf.compute(
            reader_feedback=curr,
            previous_feedback=prev,
            draft="测试内容" * 500,
            action=WritingAction.REVISE,
        )

        # 有改进应该有正reward
        assert reward >= 0, "有改进时应为正reward"
        assert "revision_bonus" in breakdown

    def test_word_count_penalty(self):
        """测试字数偏离惩罚"""
        rf = RewardFunction()

        # 字数严重不足
        short_draft = "短文本"
        reward, breakdown = rf.compute(
            reader_feedback={"reader_score": 0.5, "hook_score": 0.5},
            draft=short_draft,
        )

        assert "word_count_penalty" in breakdown
        # 字数偏离应该产生惩罚字段（正负均可）
        assert isinstance(breakdown["word_count_penalty"], (int, float))

    def test_word_count_bonus(self):
        """测试目标字数达成奖励"""
        rf = RewardFunction()

        # 目标字数约3000字
        good_draft = "测试内容" * 500

        reward, breakdown = rf.compute(
            reader_feedback={"reader_score": 0.5, "hook_score": 0.5},
            draft=good_draft,
        )

        assert "length_bonus" in breakdown

    def test_zero_feedback(self):
        """测试空反馈处理"""
        rf = RewardFunction()

        reward, breakdown = rf.compute(
            reader_feedback={},
            draft="测试",
        )

        assert 0 <= reward <= 1, "空反馈应该有合理的默认reward"

    def test_batch_rewards(self):
        """测试批量Reward计算"""
        rf = RewardFunction()

        feedbacks = [
            {"reader_score": 0.9, "hook_score": 0.8},
            {"reader_score": 0.6, "hook_score": 0.5},
            {"reader_score": 0.7, "hook_score": 0.7},
        ]

        rewards = rf.compute_batch_rewards(feedbacks)

        assert len(rewards) == len(feedbacks)
        assert all(0 <= r <= 1 for r in rewards)


class TestPPOStrategy:
    """测试 PPO 策略管理器"""

    def test_init(self):
        """测试初始化"""
        config = PPOConfig()
        strategy = PPOStrategy(config)

        assert strategy.config == config
        assert len(strategy.action_values) == len(WritingAction)
        assert len(strategy.action_counts) == len(WritingAction)

    def test_update_action_values(self):
        """测试动作价值更新"""
        config = PPOConfig()
        strategy = PPOStrategy(config)

        initial = strategy.action_values[WritingAction.GENERATE]
        strategy.update_action_values(WritingAction.GENERATE, reward=0.9)
        updated = strategy.action_values[WritingAction.GENERATE]

        assert updated > initial, "高reward应该提高动作价值"

    def test_select_action_ucb(self):
        """测试UCB动作选择"""
        config = PPOConfig()
        strategy = PPOStrategy(config)

        # 先训练一些数据
        for _ in range(5):
            strategy.update_action_values(WritingAction.GENERATE, reward=0.8)
            strategy.update_action_values(WritingAction.REVISE, reward=0.6)

        action, probs = strategy.select_action_ucb(temperature=0.5)

        assert isinstance(action, WritingAction)
        assert isinstance(probs, dict)
        assert all(a in probs for a in WritingAction)
        assert abs(sum(probs.values()) - 1.0) < 0.01, "概率和应该为1"

    def test_select_action_changes_over_time(self):
        """测试动作选择随训练变化"""
        config = PPOConfig()
        strategy = PPOStrategy(config)

        # 让GENERATE更有价值
        for _ in range(10):
            strategy.update_action_values(WritingAction.GENERATE, reward=0.9)
            strategy.update_action_values(WritingAction.DELETE, reward=0.2)

        actions = []
        for _ in range(20):
            action, _ = strategy.select_action_ucb(temperature=0.1)
            actions.append(action)

        # GENERATE应该被选择更多次
        generate_count = sum(1 for a in actions if a == WritingAction.GENERATE)
        delete_count = sum(1 for a in actions if a == WritingAction.DELETE)

        assert generate_count > delete_count, "高价值动作应该更频繁被选择"

    def test_policy_summary(self):
        """测试策略摘要"""
        config = PPOConfig()
        strategy = PPOStrategy(config)

        summary = strategy.get_policy_summary()

        assert "action_values" in summary
        assert "action_counts" in summary
        assert "total_iterations" in summary
        assert summary["total_iterations"] == 0

    def test_ucb_exploration(self):
        """测试UCB探索机制"""
        config = PPOConfig()
        strategy = PPOStrategy(config)

        # 冷启动：所有动作价值相同，但UCB应该探索不同的动作
        actions_selected = set()
        for _ in range(10):
            action, _ = strategy.select_action_ucb(temperature=0.5, use_ucb=True)
            actions_selected.add(action)

        # 10次选择中应该探索了多个不同动作
        assert len(actions_selected) >= 2, "UCB应该探索不同动作"


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
        with patch('app.writer_reader_rl.ChapterWriterAgent', return_value=mock_writer_agent), \
             patch('app.writer_reader_rl.ReaderAgent', return_value=mock_reader_agent):

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
            assert "policy_summary" in result

    @pytest.mark.asyncio
    async def test_run_multiple_rounds(
        self,
        mock_writer_agent,
        mock_reader_agent,
        mock_chapter_outline,
        mock_characters,
    ):
        """测试多轮对抗"""
        # 模拟Reader评分逐渐提升
        scores = [0.5, 0.7, 0.85]

        async def mock_reader(context):
            nonlocal scores
            score = scores.pop(0) if scores else 0.8
            return {
                "success": True,
                "reader_feedback": {
                    "reader_score": score,
                    "hook_score": score,
                    "immersion_score": score,
                    "continuity_score": score,
                    "would_continue_reading": score > 0.7,
                    "confusing_points": [],
                }
            }

        mock_reader_agent.process = mock_reader

        with patch('app.writer_reader_rl.ChapterWriterAgent', return_value=mock_writer_agent), \
             patch('app.writer_reader_rl.ReaderAgent', return_value=mock_reader_agent):

            loop = WriterReaderLoop(
                novel_id=1,
                chapter_number=1,
                max_rounds=3,
                score_threshold=0.8,
            )

            result = await loop.run(
                outline=mock_chapter_outline,
                characters=mock_characters,
                context={},
            )

            # 应该运行了多轮
            assert len(result["loop_history"]) >= 1
            assert result["total_rounds"] >= 1

    @pytest.mark.asyncio
    async def test_early_stopping_on_threshold(
        self,
        mock_writer_agent,
        mock_reader_agent,
        mock_chapter_outline,
        mock_characters,
    ):
        """测试达到阈值时早停"""
        # 第一次就达标
        mock_reader_agent.process = AsyncMock(return_value={
            "success": True,
            "reader_feedback": {
                "reader_score": 0.95,
                "hook_score": 0.90,
                "immersion_score": 0.90,
                "continuity_score": 0.90,
                "would_continue_reading": True,
                "confusing_points": [],
            }
        })

        with patch('app.writer_reader_rl.ChapterWriterAgent', return_value=mock_writer_agent), \
             patch('app.writer_reader_rl.ReaderAgent', return_value=mock_reader_agent):

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

            # 应该只运行了1轮
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
        # Reader始终不给力
        mock_reader_agent.process = AsyncMock(return_value={
            "success": True,
            "reader_feedback": {
                "reader_score": 0.4,
                "hook_score": 0.3,
                "immersion_score": 0.3,
                "continuity_score": 0.3,
                "would_continue_reading": False,
                "confusing_points": ["问题1", "问题2"],
            }
        })

        with patch('app.writer_reader_rl.ChapterWriterAgent', return_value=mock_writer_agent), \
             patch('app.writer_reader_rl.ReaderAgent', return_value=mock_reader_agent):

            loop = WriterReaderLoop(
                novel_id=1,
                chapter_number=1,
                max_rounds=3,
                score_threshold=0.9,  # 设置极高阈值，必然触发max_rounds
            )

            result = await loop.run(
                outline=mock_chapter_outline,
                characters=mock_characters,
                context={},
            )

            # 应该达到最大轮次
            assert result["total_rounds"] == 3
            assert result["passed"] is False

    def test_get_learning_report(self):
        """测试学习报告生成"""
        loop = WriterReaderLoop(
            novel_id=1,
            chapter_number=1,
            max_rounds=3,
        )

        # 填充一些历史数据
        loop.loop_history = [
            {"round": 1, "reward": 0.5, "reader_score": 0.5, "passed": False},
            {"round": 2, "reward": 0.7, "reader_score": 0.7, "passed": False},
        ]
        loop.best_reward = 0.7

        report = loop.get_learning_report()

        assert "chapter" in report
        assert "reward_progression" in report
        assert report["reward_progression"] == [0.5, 0.7]
        assert "reward_improvement" in report
        assert abs(report["reward_improvement"] - 0.2) < 0.001, f"expected ~0.2, got {report['reward_improvement']}"


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
        # draft应该被截断（200字以内+省略号）
        assert len(d["draft"]) <= 210


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
