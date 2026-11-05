"""
Writer-Reader 写作对抗循环
Writer Agent（生成器）与 Reader Agent（评审器）迭代打磨章节

RL 体系移除后的版本（NOVEL_QUALITY_UPGRADE_PLAN §6）：
- 移除 GRPO/TPO/Episode 策略层：动作空间固定为「首轮生成、后续按反馈修订」
- 保留 RewardFunction 作为软评分汇总（非 RL 训练目标）
- Reader 评审补充前文摘要、角色卡、世界观/剧情线上下文（B7 修复）
- loop_history 补 reader_feedback 键，打通 Reader → Reviewer 反馈链路（B8 修复）
- 字数惩罚符号修正（B5 修复）：不足与超出均应为负贡献
"""
import json
import copy
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger

from app.agents.writer import ChapterWriterAgent
from app.agents.reader import ReaderAgent
from app.agents.base import BaseAgent
from app.models.writing_action import WritingAction


@dataclass
class WritingState:
    """
    写作状态
    包含当前章节草稿、写作历史、上下文
    """
    chapter_number: int
    draft: str
    draft_version: int = 0
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    reward_history: List[float] = field(default_factory=list)
    reader_scores: List[Dict[str, float]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "draft": self.draft[:200] + "..." if len(self.draft) > 200 else self.draft,
            "draft_version": self.draft_version,
            "action_history_count": len(self.action_history),
            "reward_history": self.reward_history[-5:],
            "reader_scores_count": len(self.reader_scores),
        }


class RewardFunction:
    """
    Reward 函数构建器（软评分汇总）
    """

    def __init__(self):
        # 权重配置
        self.weights = {
            "reader_score": 0.35,       # Reader Agent评分
            "hook_score": 0.20,         # 钩子吸引力评分
            "immersion_score": 0.15,     # 沉浸感评分
            "continuity_score": 0.15,    # 上下文连贯性
            "word_count_penalty": -0.05, # 字数偏离惩罚
            "length_bonus": 0.10,        # 目标字数达成奖励
            "revision_bonus": 0.05,      # 改进幅度奖励
        }
        # 目标字数
        self.target_word_count = 3000
        self.word_count_tolerance = 0.2  # 允许±20%偏离

    def compute(
        self,
        reader_feedback: Dict[str, Any],
        previous_feedback: Optional[Dict[str, Any]] = None,
        draft: str = "",
        action: Optional[WritingAction] = None,
        outline_compliance: float = 1.0,
    ) -> Tuple[float, Dict[str, float]]:
        """
        计算综合软评分

        Returns:
            total_reward: 总评分
            reward_breakdown: 分项明细
        """
        breakdown = {}

        # 1. Reader Agent 评分（核心）
        reader_score = float(reader_feedback.get("reader_score", 0) or 0)
        breakdown["reader_score"] = reader_score * self.weights["reader_score"]

        # 2. 钩子评分
        hook_score = float(reader_feedback.get("hook_score", 0) or 0)
        breakdown["hook_score"] = hook_score * self.weights["hook_score"]

        # 3. 沉浸感评分
        immersion = float(reader_feedback.get("immersion_score", 0) or 0)
        breakdown["immersion_score"] = immersion * self.weights["immersion_score"]

        # 4. 上下文连贯性（Reader提供或自动计算）
        continuity = float(reader_feedback.get("continuity_score", 0) or 0)
        if continuity == 0 and previous_feedback:
            continuity = self._compute_continuity_improvement(
                reader_feedback, previous_feedback
            )
        breakdown["continuity_score"] = continuity * self.weights["continuity_score"]

        # 5. 字数偏离惩罚（不足或超出均为负贡献）
        word_count = len(draft.replace(" ", "").replace("\n", ""))
        word_count_ratio = word_count / max(self.target_word_count, 1)
        if word_count_ratio < (1 - self.word_count_tolerance):
            # 不足：惩罚 = (缺口比例)^2 * 惩罚幅度，负贡献
            wc_penalty = (1 - word_count_ratio) * 2 * abs(self.weights["word_count_penalty"])
            breakdown["word_count_penalty"] = -wc_penalty
        elif word_count_ratio > (1 + self.word_count_tolerance):
            wc_penalty = (word_count_ratio - 1) * abs(self.weights["word_count_penalty"])
            breakdown["word_count_penalty"] = -wc_penalty
        else:
            breakdown["word_count_penalty"] = 0

        # 6. 目标字数达成奖励
        if 0.9 <= word_count_ratio <= 1.1:
            breakdown["length_bonus"] = self.weights["length_bonus"]
        else:
            breakdown["length_bonus"] = 0

        # 7. 改进幅度奖励（相比上一版本）
        revision_bonus = 0
        if previous_feedback and action == WritingAction.REVISE:
            prev_score = float(previous_feedback.get("reader_score", 0) or 0)
            curr_score = reader_score
            improvement = curr_score - prev_score
            if improvement > 0:
                revision_bonus = min(improvement * self.weights["revision_bonus"] * 5, 0.05)
            elif improvement < -0.1:
                revision_bonus = max(improvement * 2, -0.05)
        breakdown["revision_bonus"] = revision_bonus

        # 8. 大纲遵循度奖励
        if outline_compliance < 1.0:
            breakdown["outline_penalty"] = (1 - outline_compliance) * 0.05
        else:
            breakdown["outline_penalty"] = 0

        # 计算总评分（归一化到0-1）
        total = sum(breakdown.values())
        total = max(0.0, min(1.0, total + 0.5))  # 平移到0-1范围

        return total, breakdown

    def compute_batch_rewards(self, feedbacks: List[Dict[str, Any]]) -> List[float]:
        """批量计算软评分"""
        rewards = []
        for fb in feedbacks:
            reward, _ = self.compute(reader_feedback=fb, draft="测试内容" * 500)
            rewards.append(reward)
        return rewards

    def _compute_continuity_improvement(
        self,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]]
    ) -> float:
        """计算连贯性改进"""
        if not previous:
            return 0.5  # 第一版给中等分数

        # 简单实现：比较困惑点数量变化
        prev_confusing = len(previous.get("confusing_points", []))
        curr_confusing = len(current.get("confusing_points", []))

        if prev_confusing == 0:
            return 0.5
        improvement = (prev_confusing - curr_confusing) / max(prev_confusing, 1)
        return max(0.0, min(1.0, 0.5 + improvement * 0.5))


class WriterReaderLoop:
    """
    Writer-Reader 写作对抗循环（RL 移除版）

    流程：
    1. Writer 生成/修订章节（首轮生成，后续按 Reader 反馈修订）
    2. Reader Agent 盲评章节（含前文/角色卡/世界观上下文）
    3. RewardFunction 汇总软评分
    4. 达标即停，否则重写，直到最大轮次
    """

    def __init__(
        self,
        novel_id: int,
        chapter_number: int,
        max_rounds: int = 3,
        score_threshold: float = 0.78,
        hook_threshold: float = 0.70,
    ):
        self.novel_id = novel_id
        self.chapter_number = chapter_number
        self.max_rounds = max_rounds
        self.score_threshold = score_threshold
        self.hook_threshold = hook_threshold

        # 初始化组件
        self.writer = ChapterWriterAgent()
        self.reader = ReaderAgent()
        self.reward_fn = RewardFunction()

        # 状态追踪
        self.current_state: Optional[WritingState] = None
        self.best_state: Optional[WritingState] = None
        self.best_reward: float = -999
        self.loop_history: List[Dict[str, Any]] = []

        logger.info(
            f"[WriterReaderLoop] 初始化对抗循环: "
            f"novel={novel_id}, chapter={chapter_number}, "
            f"max_rounds={max_rounds}, threshold={score_threshold}"
        )

    async def run(
        self,
        outline: Dict[str, Any],
        characters: List[Dict],
        context: Dict[str, Any],
        initial_draft: str = "",
    ) -> Dict[str, Any]:
        """
        执行 Writer-Reader 对抗循环

        Args:
            outline: 章节大纲
            characters: 角色列表
            context: 写作上下文（包含RAG召回、世界观、剧情线等）
            initial_draft: 初始草稿（用于修订模式）

        Returns:
            最终结果（含最佳草稿、评分历史等）
        """
        # 初始化状态
        self.current_state = WritingState(
            chapter_number=self.chapter_number,
            draft=initial_draft,
            draft_version=0,
        )
        self.best_reward = -999
        self.best_state = None
        self.loop_history = []

        logger.info(
            f"[WriterReaderLoop] 开始对抗循环: 初始draft长度={len(initial_draft)}"
        )

        for round_num in range(1, self.max_rounds + 1):
            logger.info(f"[WriterReaderLoop] === 第{round_num}轮 ===")

            # 动作固定：首轮生成，后续修订
            if round_num == 1 and not initial_draft:
                action = WritingAction.GENERATE
            elif round_num == 1 and initial_draft:
                action = WritingAction.REVISE
            else:
                action = WritingAction.REVISE

            # 用量归属：writer/reader 子阶段细分
            from app.core.llm_call_tracker import set_phase_context, set_agent_context
            set_phase_context("writer")
            set_agent_context("writer")
            writer_result = await self._writer_act(
                action=action,
                outline=outline,
                characters=characters,
                context=context,
            )

            if not writer_result.get("success"):
                logger.error(f"[WriterReaderLoop] Writer执行失败: {writer_result.get('error')}")
                self.loop_history.append({
                    "round": round_num,
                    "action": action.value,
                    "success": False,
                    "error": writer_result.get("error"),
                })
                continue

            new_draft = writer_result.get("content", "")
            self.current_state.draft = new_draft
            self.current_state.draft_version = round_num

            # 用量归属：reader 子阶段
            from app.core.llm_call_tracker import set_phase_context, set_agent_context
            set_phase_context("reader")
            set_agent_context("reader")
            reader_result = await self._reader_evaluate(
                draft=new_draft,
                outline=outline,
                characters=characters,
                context=context,
            )

            # 计算软评分
            previous_feedback = None
            if len(self.current_state.reader_scores) > 0:
                previous_feedback = self.current_state.reader_scores[-1]

            reward, breakdown = self.reward_fn.compute(
                reader_feedback=reader_result.get("reader_feedback", {}),
                previous_feedback=previous_feedback,
                draft=new_draft,
                action=action,
            )

            self.current_state.reward_history.append(reward)
            self.current_state.reader_scores.append(reader_result.get("reader_feedback", {}))
            self.current_state.action_history.append({
                "round": round_num,
                "action": action.value,
                "reward": reward,
                "breakdown": breakdown,
                "draft_length": len(new_draft),
            })

            logger.info(
                f"[WriterReaderLoop] 第{round_num}轮结果: "
                f"reward={reward:.4f}, "
                f"reader_score={breakdown.get('reader_score', 0):.4f}, "
                f"hook_score={breakdown.get('hook_score', 0):.4f}"
            )

            # 检查是否达标
            feedback = reader_result.get("reader_feedback", {})
            reader_score = float(feedback.get("reader_score", 0) or 0)
            hook_score = float(feedback.get("hook_score", 0) or 0)
            continue_reading = bool(feedback.get("would_continue_reading", False))

            passed = (
                reader_score >= self.score_threshold and
                hook_score >= self.hook_threshold and
                continue_reading
            )

            # 记录最佳状态
            if reward > self.best_reward:
                self.best_reward = reward
                self.best_state = copy.deepcopy(self.current_state)
                logger.info(f"[WriterReaderLoop] 发现新的最佳Reward: {reward:.4f}")

            self.loop_history.append({
                "round": round_num,
                "action": action.value,
                "reward": reward,
                "breakdown": breakdown,
                "reader_score": reader_score,
                "hook_score": hook_score,
                "continue_reading": continue_reading,
                "passed": passed,
                "reader_feedback": feedback,
                "draft_length": len(new_draft),
            })

            if passed:
                logger.info(
                    f"[WriterReaderLoop] ✅ 第{round_num}轮达标！"
                    f"reader={reader_score:.3f}, hook={hook_score:.3f}"
                )
                break

        # 取最佳草稿
        final_draft = self.best_state.draft if self.best_state else self.current_state.draft

        # 返回最终结果
        return {
            "success": True,
            "final_draft": final_draft,
            "final_reward": self.best_reward if self.best_state else self.current_state.reward_history[-1] if self.current_state.reward_history else 0,
            "best_reward": self.best_reward,
            "total_rounds": len(self.loop_history),
            "passed": self.loop_history[-1].get("passed", False) if self.loop_history else False,
            "loop_history": self.loop_history,
            "best_state": self.best_state.to_dict() if self.best_state else None,
            "word_count": len(final_draft.replace(" ", "").replace("\n", "")),
        }

    async def _writer_act(
        self,
        action: WritingAction,
        outline: Dict[str, Any],
        characters: List[Dict],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Writer Agent 执行动作"""
        try:
            writer_context = {
                "novel_id": self.novel_id,
                "chapter_number": self.chapter_number,
                "outline": outline,
                "characters": characters,
                "context": context,
                "rewrite_round": self.current_state.draft_version + 1,
                "writing_style": context.get("writing_style", "叙事流畅，情节紧凑"),
                "env_description_level": context.get("env_level", "normal"),
                "dialogue_ratio": context.get("dialogue_ratio", 0.3),
            }

            if action == WritingAction.GENERATE:
                return await self.writer.process(writer_context)

            elif action == WritingAction.REVISE:
                writer_context["previous_draft"] = self.current_state.draft
                writer_context["reader_feedback"] = (
                    self.current_state.reader_scores[-1] if self.current_state.reader_scores else {}
                )
                return await self.writer.process(writer_context)

            elif action == WritingAction.DELETE:
                # 删除策略：使用更精简的prompt重新生成
                writer_context["notes"] = "本轮采用精简策略：删除冗余内容，保留核心情节，字数控制在目标的80%"
                return await self.writer.process(writer_context)

            elif action == WritingAction.KEEP:
                # 保留：仅进行轻微润色
                return {
                    "success": True,
                    "content": self.current_state.draft,
                    "word_count": len(self.current_state.draft),
                }

            return {"success": False, "error": f"未知动作: {action}"}

        except Exception as e:
            logger.error(f"[WriterReaderLoop] Writer执行异常: {e}")
            return {"success": False, "error": str(e)}

    async def _reader_evaluate(
        self,
        draft: str,
        outline: Dict[str, Any],
        characters: List[Dict],
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Reader Agent 评估章节"""
        try:
            reader_context = {
                "chapter_number": self.chapter_number,
                "chapter_content": draft,
                "outline": outline,
                "characters": characters,
                "target_reader": "大众网文读者",
            }
            # B7 修复：补入前文摘要、世界观、剧情线，让 Reader 的连贯性判断有依据
            if context:
                if context.get("world_setting"):
                    reader_context["world_setting"] = context["world_setting"]
                if context.get("plot_setting"):
                    reader_context["plot_setting"] = context["plot_setting"]
                if context.get("previous_chapter_summary"):
                    reader_context["previous_chapter_summary"] = context["previous_chapter_summary"]
                if context.get("unresolved_mysteries"):
                    reader_context["unresolved_mysteries"] = context["unresolved_mysteries"]
            return await self.reader.process(reader_context)
        except Exception as e:
            logger.error(f"[WriterReaderLoop] Reader执行异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "reader_feedback": {
                    "reader_score": 0.5,
                    "hook_score": 0.5,
                    "would_continue_reading": True,
                }
            }

    def get_learning_report(self) -> Dict[str, Any]:
        """生成循环报告"""
        if not self.loop_history:
            return {"status": "no_history"}

        rewards = [h.get("reward", 0.0) for h in self.loop_history]
        reader_scores = [h.get("reader_score", 0) for h in self.loop_history]

        report = {
            "chapter": self.chapter_number,
            "total_rounds": len(self.loop_history),
            "passed": self.loop_history[-1].get("passed", False) if self.loop_history else False,
            "best_reward": self.best_reward,
            "reward_progression": rewards,
            "reader_score_progression": reader_scores,
            "reward_improvement": rewards[-1] - rewards[0] if len(rewards) > 1 else 0,
        }

        return report

    async def run_with_collection(
        self,
        collector,
        outline: Dict[str, Any],
        characters: List[Dict],
        context: Dict[str, Any],
        initial_draft: str = "",
        do_pre_eval: bool = True,
        do_post_eval: bool = True,
    ) -> Dict[str, Any]:
        """
        执行带数据采集的 Writer-Reader 循环
        （训练数据采集器保留为「章节-评分」诊断日志，见 §6.2）
        """
        from app.services.rubric_evaluation_service import RubricEvaluationService
        from app.models.rubric import EvaluationType

        # 可选：循环前评测
        pre_eval = None
        if do_pre_eval:
            logger.info("[WriterReaderLoop] 执行循环前 Rubric 评测...")
            pre_eval = await collector.evaluate_before_training([self.chapter_number])
            logger.info(f"[WriterReaderLoop] 循环前分数: {pre_eval.get('average_score', 0):.2f}")

        # 运行对抗循环
        logger.info("[WriterReaderLoop] 开始对抗循环...")
        rl_result = await self.run(
            outline=outline,
            characters=characters,
            context=context,
            initial_draft=initial_draft,
        )

        # 采集每一轮数据
        episode_number = 0
        for round_data in self.loop_history:
            episode_number += 1
            action_taken = round_data.get("action", "generate")

            await collector.collect_episode(
                chapter_number=self.chapter_number,
                episode_number=episode_number,
                round_number=round_data.get("round", episode_number),
                state_draft=rl_result.get("final_draft", ""),
                action_taken=action_taken,
                action_probs={"generate": 0.25, "revise": 0.25, "delete": 0.25, "keep": 0.25},
                reward=round_data.get("reward", 0),
                reader_score=round_data.get("reader_score"),
                hook_score=round_data.get("hook_score"),
                immersion_score=round_data.get("reader_score"),
                policy_version=0,
                is_terminal=round_data.get("passed", False) or episode_number == self.max_rounds,
                termination_reason="达标" if round_data.get("passed") else (
                    "达到最大轮次" if episode_number == self.max_rounds else None
                )
            )
            logger.info(
                f"[WriterReaderLoop] 回合 {episode_number} 数据已采集: "
                f"action={action_taken}, reward={round_data.get('reward', 0):.4f}"
            )

        # 可选：循环后评测
        post_eval = None
        if do_post_eval:
            logger.info("[WriterReaderLoop] 执行循环后 Rubric 评测...")
            post_eval = await collector.evaluate_after_training([self.chapter_number])
            logger.info(f"[WriterReaderLoop] 循环后分数: {post_eval.get('average_score', 0):.2f}")

        # 生成对比报告
        comparison_report = None
        if pre_eval and post_eval:
            logger.info("[WriterReaderLoop] 生成对比报告...")
            comparison_report = await collector.generate_comparison_report(pre_eval, post_eval)
            logger.info(
                f"[WriterReaderLoop] 改进率: {comparison_report.get('summary', {}).get('improvement_rate', 'N/A')}"
            )

        # 返回完整结果
        return {
            **rl_result,
            "pre_training_eval": pre_eval,
            "post_training_eval": post_eval,
            "comparison_report": comparison_report,
            "data_directory": collector.get_data_directory(),
        }
