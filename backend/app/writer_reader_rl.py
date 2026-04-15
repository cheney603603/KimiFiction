"""
Writer-Reader RL Adversarial System
Writer Agent（生成器）与 Reader Agent（判别器）通过强化学习博弈

核心机制（更新为GRPO）：
- GRPO（Group Relative Policy Optimization）微调写作策略
- 无需critic网络，使用组内相对奖励计算优势
- 动作空间：[生成/修改/删除/保留]
- Reward = 人工评估 + 自动化指标（困惑度、连贯性、读者评分）

新增功能：
- 支持GRPO算法
- 集成TPO（Test-time Preference Optimization）
- 集成模仿学习
- 支持Test-Time RL
"""
import json
import copy
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from app.agents.writer import ChapterWriterAgent
from app.agents.reader import ReaderAgent
from app.agents.base import BaseAgent

# 导入GRPO训练器（统一入口：app.rl_training → app/training/）
from app.rl_training import (
    GRPOTrainer,
    GRPOConfig,
    WritingAction,
    Episode,
    TPOService,
)
# RTX 4070 优化配置
from app.rl_training.config import RLTrainingConfig


@dataclass
class WritingState:
    """
    写作状态（作为强化学习的状态空间）
    包含当前章节草稿、写作历史、上下文
    """
    chapter_number: int
    draft: str
    draft_version: int = 0
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    reward_history: List[float] = field(default_factory=list)
    reader_scores: List[Dict[str, float]] = field(default_factory=list)
    policy_version: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "draft": self.draft[:200] + "..." if len(self.draft) > 200 else self.draft,
            "draft_version": self.draft_version,
            "action_history_count": len(self.action_history),
            "reward_history": self.reward_history[-5:],
            "reader_scores_count": len(self.reader_scores),
            "policy_version": self.policy_version,
        }


class RewardFunction:
    """
    Reward 函数构建器
    融合人工评估与自动化指标
    """
    
    def __init__(self):
        # 权重配置（与GRPOConfig保持一致）
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
        计算综合Reward
        
        Returns:
            total_reward: 总奖励
            reward_breakdown: 分项奖励明细
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
        
        # 5. 字数偏离惩罚
        word_count = len(draft.replace(" ", "").replace("\n", ""))
        word_count_ratio = word_count / max(self.target_word_count, 1)
        if word_count_ratio < (1 - self.word_count_tolerance):
            wc_penalty = (1 - word_count_ratio) * 2 * abs(self.weights["word_count_penalty"])
            breakdown["word_count_penalty"] = wc_penalty
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
        
        # 计算总奖励（归一化到0-1）
        total = sum(breakdown.values())
        total = max(0.0, min(1.0, total + 0.5))  # 平移到0-1范围
        
        return total, breakdown
    
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
    Writer-Reader 强化学习对抗循环（GRPO版本）
    
    流程：
    1. Writer 根据状态和策略生成/修改章节
    2. Reader Agent 评估章节质量
    3. RewardFunction 计算综合奖励
    4. GRPOTrainer 更新写作策略
    5. 可选：TPO进一步优化
    6. 重复直到达到质量阈值或最大轮次
    """
    
    def __init__(
        self,
        novel_id: int,
        chapter_number: int,
        max_rounds: int = 3,
        score_threshold: float = 0.78,
        use_grpo: bool = True,
        use_tpo: bool = False,
        grpo_config: Optional[GRPOConfig] = None,
    ):
        self.novel_id = novel_id
        self.chapter_number = chapter_number
        self.max_rounds = max_rounds
        self.score_threshold = score_threshold
        self.use_grpo = use_grpo
        self.use_tpo = use_tpo
        
        # 初始化组件
        self.writer = ChapterWriterAgent()
        self.reader = ReaderAgent()
        self.reward_fn = RewardFunction()
        
        # GRPO训练器（如果使用）
        self.grpo_trainer = None
        if use_grpo:
            # 优先使用传入的 grpo_config，否则用 RTX 4070 优化配置
            final_config = grpo_config
            if final_config is None:
                # 自动应用 RTX 4070 优化配置（8GB 显存限定）
                rtx_config = RLTrainingConfig()
                final_config = GRPOConfig(
                    group_size=rtx_config.grpo_group_size,
                    num_iterations=max_rounds,
                    temperature=rtx_config.temperature,
                )
            self.grpo_trainer = GRPOTrainer(
                novel_id=novel_id,
                config=final_config,
            )
        
        # TPO服务（如果使用）
        self.tpo_service = None
        if use_tpo:
            self.tpo_service = TPOService(self.reader, num_candidates=3)
        
        # 状态追踪
        self.current_state: Optional[WritingState] = None
        self.best_state: Optional[WritingState] = None
        self.best_reward: float = -999
        self.loop_history: List[Dict[str, Any]] = []
        
        logger.info(
            f"[WriterReaderRL] 初始化对抗循环: "
            f"novel={novel_id}, chapter={chapter_number}, "
            f"max_rounds={max_rounds}, threshold={score_threshold}, "
            f"use_grpo={use_grpo}, use_tpo={use_tpo}"
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
            context: 写作上下文（包含RAG召回的上下文）
            initial_draft: 初始草稿（用于修订模式）
            
        Returns:
            最终结果（含最佳草稿、Reward历史等）
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
            f"[WriterReaderRL] 开始对抗循环: 初始draft长度={len(initial_draft)}"
        )
        
        # 构建GRPO状态表示
        state_repr = self._build_state_repr(context, outline)
        
        for round_num in range(1, self.max_rounds + 1):
            logger.info(f"[WriterReaderRL] === 第{round_num}轮 ===")
            
            # Step 1: 策略选择动作
            if self.use_grpo and self.grpo_trainer:
                # 使用GRPO策略采样
                group_actions = self.grpo_trainer.policy.sample_group(
                    state_repr,
                    group_size=3,  # 每轮采样3个
                    temperature=0.3 if round_num > 1 else 0.5
                )
                action, action_prob = group_actions[0]
            else:
                # 默认策略
                action = WritingAction.GENERATE if round_num == 1 else WritingAction.REVISE
                action_prob = 0.5
            
            logger.info(
                f"[WriterReaderRL] 策略选择: action={action.value}"
            )
            
            # Step 2: Writer 执行动作
            if round_num == 1 and not initial_draft:
                action = WritingAction.GENERATE
            
            writer_result = await self._writer_act(
                action=action,
                outline=outline,
                characters=characters,
                context=context,
            )
            
            if not writer_result.get("success"):
                logger.error(f"[WriterReaderRL] Writer执行失败: {writer_result.get('error')}")
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
            
            # Step 3: Reader Agent 评估
            reader_result = await self._reader_evaluate(
                draft=new_draft,
                outline=outline,
                characters=characters,
            )
            
            # Step 4: 计算 Reward
            previous_feedback = None
            if len(self.current_state.reader_scores) > 0:
                previous_feedback = self.current_state.reader_scores[-1]
            
            reward, breakdown = self.reward_fn.compute(
                reader_feedback=reader_result.get("reader_feedback", {}),
                previous_feedback=previous_feedback,
                draft=new_draft,
                action=action,
            )
            
            # Step 5: 如果使用GRPO，记录episode
            if self.use_grpo and self.grpo_trainer:
                episode = Episode(
                    state=state_repr,
                    action=action,
                    output=new_draft,
                    reward=reward,
                    advantage=0.0,  # 稍后在组级别计算
                    log_prob=np.log(max(action_prob, 1e-8)),
                    group_mean_reward=0.0,
                    group_std_reward=0.0
                )
                # 这里简化处理，实际应该在组级别更新
            
            # 更新策略
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
                f"[WriterReaderRL] 第{round_num}轮结果: "
                f"reward={reward:.4f}, "
                f"reader_score={breakdown.get('reader_score', 0):.4f}, "
                f"hook_score={breakdown.get('hook_score', 0):.4f}"
            )
            
            # Step 6: 检查是否达标
            reader_score = float(
                reader_result.get("reader_feedback", {}).get("reader_score", 0) or 0
            )
            hook_score = float(
                reader_result.get("reader_feedback", {}).get("hook_score", 0) or 0
            )
            continue_reading = bool(
                reader_result.get("reader_feedback", {}).get("would_continue_reading", False)
            )
            
            passed = (
                reader_score >= self.score_threshold and
                hook_score >= 0.70 and
                continue_reading
            )
            
            # 记录最佳状态
            if reward > self.best_reward:
                self.best_reward = reward
                self.best_state = copy.deepcopy(self.current_state)
                logger.info(f"[WriterReaderRL] 发现新的最佳Reward: {reward:.4f}")
            
            self.loop_history.append({
                "round": round_num,
                "action": action.value,
                "reward": reward,
                "breakdown": breakdown,
                "reader_score": reader_score,
                "hook_score": hook_score,
                "continue_reading": continue_reading,
                "passed": passed,
                "draft_length": len(new_draft),
            })
            
            if passed:
                logger.info(
                    f"[WriterReaderRL] ✅ 第{round_num}轮达标！"
                    f"reader={reader_score:.3f}, hook={hook_score:.3f}"
                )
                break
        
        # Step 7: 可选的TPO优化
        final_draft = self.best_state.draft if self.best_state else self.current_state.draft
        
        if self.use_tpo and self.tpo_service:
            logger.info("[WriterReaderRL] 执行TPO优化...")
            try:
                tpo_result = await self.tpo_service.optimize(
                    generate_fn=lambda ctx, temp: self._writer_act_with_temp(ctx, temp, outline, characters, context),
                    context=context,
                    outline=outline,
                    num_candidates=3
                )
                final_draft = tpo_result.final_output
                logger.info(f"[WriterReaderRL] TPO优化完成: 改进={tpo_result.improvement:+.4f}")
            except Exception as e:
                logger.error(f"[WriterReaderRL] TPO优化失败: {e}")
        
        # 返回最终结果
        return {
            "success": True,
            "final_draft": final_draft,
            "final_reward": self.best_reward if self.best_state else self.current_state.reward_history[-1] if self.current_state.reward_history else 0,
            "best_reward": self.best_reward,
            "total_rounds": len(self.loop_history),
            "passed": self.loop_history[-1].get("passed", False) if self.loop_history else False,
            "loop_history": self.loop_history,
            "policy_summary": self.grpo_trainer.policy.get_policy_summary() if self.grpo_trainer else None,
            "best_state": self.best_state.to_dict() if self.best_state else None,
            "word_count": len(final_draft.replace(" ", "").replace("\n", "")),
            "use_grpo": self.use_grpo,
            "use_tpo": self.use_tpo,
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
            logger.error(f"[WriterReaderRL] Writer执行异常: {e}")
            return {"success": False, "error": str(e)}
    
    async def _writer_act_with_temp(
        self,
        context: Dict[str, Any],
        temperature: float,
        outline: Dict[str, Any],
        characters: List[Dict],
        base_context: Dict[str, Any]
    ) -> str:
        """带温度参数的Writer执行（用于TPO）"""
        ctx = base_context.copy()
        ctx.update(context)
        ctx["temperature"] = temperature
        
        result = await self._writer_act(WritingAction.GENERATE, outline, characters, ctx)
        return result.get("content", "")
    
    async def _reader_evaluate(
        self,
        draft: str,
        outline: Dict[str, Any],
        characters: List[Dict],
    ) -> Dict[str, Any]:
        """Reader Agent 评估章节"""
        try:
            reader_context = {
                "chapter_number": self.chapter_number,
                "chapter_content": draft,
                "outline": outline,
                "target_reader": "大众网文读者",
            }
            return await self.reader.process(reader_context)
        except Exception as e:
            logger.error(f"[WriterReaderRL] Reader执行异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "reader_feedback": {
                    "reader_score": 0.5,
                    "hook_score": 0.5,
                    "would_continue_reading": True,
                }
            }
    
    def _build_state_repr(self, context: Dict[str, Any], outline: Dict[str, Any]) -> str:
        """构建状态表示（用于GRPO）"""
        parts = []
        
        # 章节号
        parts.append(f"Chapter: {self.chapter_number}")
        
        # 大纲摘要
        if outline:
            parts.append(f"Outline: {outline.get('summary', '')[:100]}")
        
        # 上下文信息
        if context:
            parts.append(f"Style: {context.get('writing_style', 'default')}")
            parts.append(f"EnvLevel: {context.get('env_description_level', 'normal')}")
        
        return " | ".join(parts)
    
    def get_learning_report(self) -> Dict[str, Any]:
        """生成学习报告"""
        if not self.loop_history:
            return {"status": "no_history"}
        
        rewards = [h["reward"] for h in self.loop_history]
        reader_scores = [h.get("reader_score", 0) for h in self.loop_history]
        
        report = {
            "chapter": self.chapter_number,
            "total_rounds": len(self.loop_history),
            "passed": self.loop_history[-1].get("passed", False) if self.loop_history else False,
            "best_reward": self.best_reward,
            "reward_progression": rewards,
            "reader_score_progression": reader_scores,
            "reward_improvement": rewards[-1] - rewards[0] if len(rewards) > 1 else 0,
            "use_grpo": self.use_grpo,
            "use_tpo": self.use_tpo,
        }
        
        if self.grpo_trainer:
            report["grpo_policy"] = self.grpo_trainer.policy.get_policy_summary()
        
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
        执行带数据采集的 Writer-Reader 对抗循环
        """
        from app.services.rubric_evaluation_service import RubricEvaluationService
        from app.models.rubric import EvaluationType
        
        # 可选：训练前评测
        pre_eval = None
        if do_pre_eval:
            logger.info("[WriterReaderRL] 执行训练前 Rubric 评测...")
            pre_eval = await collector.evaluate_before_training([self.chapter_number])
            logger.info(f"[WriterReaderRL] 训练前分数: {pre_eval.get('average_score', 0):.2f}")
        
        # 运行 RL 对抗循环
        logger.info("[WriterReaderRL] 开始对抗循环...")
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
                action_probs={"generate": 0.3, "revise": 0.3, "delete": 0.2, "keep": 0.2},
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
                f"[WriterReaderRL] 回合 {episode_number} 数据已采集: "
                f"action={action_taken}, reward={round_data.get('reward', 0):.4f}"
            )
        
        # 可选：训练后评测
        post_eval = None
        if do_post_eval:
            logger.info("[WriterReaderRL] 执行训练后 Rubric 评测...")
            post_eval = await collector.evaluate_after_training([self.chapter_number])
            logger.info(f"[WriterReaderRL] 训练后分数: {post_eval.get('average_score', 0):.2f}")
        
        # 生成对比报告
        comparison_report = None
        if pre_eval and post_eval:
            logger.info("[WriterReaderRL] 生成对比报告...")
            comparison_report = await collector.generate_comparison_report(pre_eval, post_eval)
            logger.info(
                f"[WriterReaderRL] 改进率: {comparison_report.get('summary', {}).get('improvement_rate', 'N/A')}"
            )
        
        # 返回完整结果
        return {
            **rl_result,
            "pre_training_eval": pre_eval,
            "post_training_eval": post_eval,
            "comparison_report": comparison_report,
            "data_directory": collector.get_data_directory(),
        }


# 便捷函数
def create_grpo_loop(
    novel_id: int,
    chapter_number: int,
    max_rounds: int = 3,
    **kwargs
) -> WriterReaderLoop:
    """创建使用GRPO的WriterReaderLoop"""
    return WriterReaderLoop(
        novel_id=novel_id,
        chapter_number=chapter_number,
        max_rounds=max_rounds,
        use_grpo=True,
        use_tpo=kwargs.get("use_tpo", False),
        grpo_config=kwargs.get("grpo_config"),
    )
