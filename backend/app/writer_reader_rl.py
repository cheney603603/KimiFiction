"""
Writer-Reader RL Adversarial System
Writer Agent（生成器）与 Reader Agent（判别器）通过强化学习博弈

核心机制：
- PPO（近端策略优化）微调写作策略
- 动作空间：[生成/修改/删除]
- Reward = 人工评估 + 自动化指标（困惑度、连贯性、读者评分）
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


class WritingAction(str, Enum):
    """写作动作空间"""
    GENERATE = "generate"       # 生成新内容
    REVISE = "revise"          # 修改内容
    DELETE = "delete"          # 删除内容
    KEEP = "keep"              # 保留不变


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


@dataclass
class PPOConfig:
    """PPO算法配置"""
    # 策略网络
    lr_actor: float = 3e-4
    lr_critic: float = 1e-3
    gamma: float = 0.99          # 折扣因子
    lam: float = 0.95            # GAE lambda
    
    # PPO特定
    clip_epsilon: float = 0.2    # PPO裁剪范围
    entropy_coef: float = 0.01   # 熵正则化系数
    value_loss_coef: float = 0.5 # 价值损失系数
    max_grad_norm: float = 0.5   # 梯度裁剪
    
    # 训练
    ppo_epochs: int = 4           # 每次更新的epoch数
    batch_size: int = 64
    minibatch_size: int = 16
    
    # 探索
    action_noise: float = 0.1    # 动作噪声（温度采样）
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


class RewardFunction:
    """
    Reward 函数构建器
    融合人工评估与自动化指标
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
    
    def compute_batch_rewards(
        self,
        reader_feedbacks: List[Dict[str, Any]],
        previous_feedbacks: Optional[List[Dict[str, Any]]] = None,
        drafts: Optional[List[str]] = None,
        actions: Optional[List[WritingAction]] = None,
    ) -> List[float]:
        """批量计算Reward"""
        rewards = []
        for i, feedback in enumerate(reader_feedbacks):
            prev = previous_feedbacks[i] if previous_feedbacks else None
            draft = drafts[i] if drafts else ""
            action = actions[i] if actions else None
            reward, _ = self.compute(feedback, prev, draft, action)
            rewards.append(reward)
        return rewards


class PPOStrategy:
    """
    PPO策略管理器
    
    注意：由于 Writer Agent 使用外部 LLM API（GPT-4），
    这里采用"策略评分+采样"的方式实现类PPO机制：
    - 维护每个动作的期望reward估计
    - 使用clip策略限制策略更新幅度
    - 通过温度参数控制探索与利用的平衡
    """
    
    def __init__(self, config: Optional[PPOConfig] = None):
        self.config = config or PPOConfig()
        
        # 动作价值估计（简化为每个动作类型的EWMA）
        self.action_values: Dict[WritingAction, float] = {
            WritingAction.GENERATE: 0.5,
            WritingAction.REVISE: 0.5,
            WritingAction.DELETE: 0.3,
            WritingAction.KEEP: 0.4,
        }
        
        # 动作计数（用于UCB探索）
        self.action_counts: Dict[WritingAction, int] = {
            WritingAction.GENERATE: 1,
            WritingAction.REVISE: 1,
            WritingAction.DELETE: 1,
            WritingAction.KEEP: 1,
        }
        
        # 衰减因子
        self.gamma = self.config.gamma
        
        # 历史记录
        self.policy_history: List[Dict[str, Any]] = []
        self.total_iterations = 0
        
        # 熵记录
        self.entropy_history: List[float] = []
    
    def update_action_values(
        self,
        action: WritingAction,
        reward: float,
        learning_rate: float = 0.1
    ) -> None:
        """更新动作价值估计（简化的EWMA更新）"""
        current = self.action_values.get(action, 0.5)
        # 指数移动平均
        new_value = current + learning_rate * (reward - current)
        self.action_values[action] = max(0.0, min(1.0, new_value))
        self.action_counts[action] += 1
    
    def select_action_ucb(
        self,
        temperature: float = 0.5,
        use_ucb: bool = True
    ) -> Tuple[WritingAction, Dict[str, float]]:
        """
        基于UCB（Upper Confidence Bound）的动作选择
        
        Args:
            temperature: 温度参数（控制探索程度）
            use_ucb: 是否使用UCB探索
            
        Returns:
            selected_action, action_probs
        """
        import math
        
        actions = list(WritingAction)
        values = [self.action_values[a] for a in actions]
        
        # 计算UCB bonus
        total_counts = sum(self.action_counts.values())
        ucb_bonus = {}
        for action in actions:
            count = self.action_counts[action]
            if use_ucb and count > 0:
                bonus = temperature * math.sqrt(
                    math.log(total_counts + 1) / max(count, 1)
                )
                ucb_bonus[action] = bonus
            else:
                ucb_bonus[action] = 0
        
        # 综合得分
        scores = {
            a: self.action_values[a] + ucb_bonus[a]
            for a in actions
        }
        
        # 计算概率（softmax）
        max_score = max(scores.values())
        exp_scores = {
            a: math.exp((scores[a] - max_score) / max(temperature, 0.01))
            for a in actions
        }
        total_exp = sum(exp_scores.values())
        probs = {
            a: exp_scores[a] / total_exp
            for a in actions
        }
        
        # 采样
        import random
        r = random.random()
        cumsum = 0
        selected = WritingAction.KEEP
        for action in actions:
            cumsum += probs[action]
            if r <= cumsum:
                selected = action
                break
        
        # 记录
        self.policy_history.append({
            "iteration": self.total_iterations,
            "selected": selected.value,
            "probs": {a.value: probs[a] for a in actions},
            "values": {a.value: self.action_values[a] for a in actions},
            "scores": {a.value: scores[a] for a in actions},
        })
        self.total_iterations += 1
        
        return selected, probs
    
    def compute_policy_loss(
        self,
        old_probs: Dict[str, float],
        new_probs: Dict[str, float],
        advantages: List[float]
    ) -> float:
        """
        计算PPO裁剪损失（简化版）
        
        在实际LLM调用场景中，我们用概率比来近似策略梯度
        """
        loss = 0.0
        for action_str, adv in zip(old_probs.keys(), advantages):
            ratio = new_probs.get(action_str, 0.1) / max(old_probs.get(action_str, 0.1), 0.01)
            # PPO clip
            clipped_ratio = max(min(ratio, 1 + self.config.clip_epsilon),
                               1 - self.config.clip_epsilon)
            loss -= min(ratio * adv, clipped_ratio * adv)
        return loss / max(len(advantages), 1)
    
    def get_policy_summary(self) -> Dict[str, Any]:
        """获取策略摘要"""
        return {
            "action_values": {a.value: round(v, 4) for a, v in self.action_values.items()},
            "action_counts": {a.value: c for a, c in self.action_counts.items()},
            "total_iterations": self.total_iterations,
            "avg_entropy": sum(self.entropy_history[-100:]) / max(len(self.entropy_history[-100:]), 1),
        }


class WriterReaderLoop:
    """
    Writer-Reader 强化学习对抗循环
    
    流程：
    1. Writer 根据状态和策略生成/修改章节
    2. Reader Agent 评估章节质量
    3. RewardFunction 计算综合奖励
    4. PPOStrategy 更新写作策略
    5. 重复直到达到质量阈值或最大轮次
    """
    
    def __init__(
        self,
        novel_id: int,
        chapter_number: int,
        max_rounds: int = 3,
        score_threshold: float = 0.78,
        config: Optional[PPOConfig] = None,
    ):
        self.novel_id = novel_id
        self.chapter_number = chapter_number
        self.max_rounds = max_rounds
        self.score_threshold = score_threshold
        
        # 初始化组件
        self.writer = ChapterWriterAgent()
        self.reader = ReaderAgent()
        self.reward_fn = RewardFunction()
        self.ppo_strategy = PPOStrategy(config)
        
        # 状态追踪
        self.current_state: Optional[WritingState] = None
        self.best_state: Optional[WritingState] = None
        self.best_reward: float = -999
        self.loop_history: List[Dict[str, Any]] = []
        
        logger.info(
            f"[WriterReaderRL] 初始化对抗循环: "
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
        
        for round_num in range(1, self.max_rounds + 1):
            logger.info(f"[WriterReaderRL] === 第{round_num}轮 ===")
            
            # Step 1: 策略选择动作
            action, action_probs = self.ppo_strategy.select_action_ucb(
                temperature=0.3 if round_num > 1 else 0.5
            )
            
            logger.info(
                f"[WriterReaderRL] 策略选择: action={action.value}, "
                f"probs={ {k.value: round(v, 3) for k, v in action_probs.items()} }"
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
            
            # Step 5: 更新策略
            self.ppo_strategy.update_action_values(action, reward)
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
                "action_probs": {k.value: round(v, 3) for k, v in action_probs.items()},
            })
            
            if passed:
                logger.info(
                    f"[WriterReaderRL] ✅ 第{round_num}轮达标！"
                    f"reader={reader_score:.3f}, hook={hook_score:.3f}"
                )
                break
        
        # 返回最终结果
        final_draft = self.best_state.draft if self.best_state else self.current_state.draft
        final_reward = self.best_reward if self.best_state else self.current_state.reward_history[-1] if self.current_state.reward_history else 0
        
        return {
            "success": True,
            "final_draft": final_draft,
            "final_reward": final_reward,
            "best_reward": self.best_reward,
            "total_rounds": len(self.loop_history),
            "passed": self.loop_history[-1].get("passed", False) if self.loop_history else False,
            "loop_history": self.loop_history,
            "policy_summary": self.ppo_strategy.get_policy_summary(),
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
            logger.error(f"[WriterReaderRL] Writer执行异常: {e}")
            return {"success": False, "error": str(e)}
    
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
    
    def get_learning_report(self) -> Dict[str, Any]:
        """生成学习报告"""
        if not self.loop_history:
            return {"status": "no_history"}
        
        rewards = [h["reward"] for h in self.loop_history]
        reader_scores = [h.get("reader_score", 0) for h in self.loop_history]
        
        return {
            "chapter": self.chapter_number,
            "total_rounds": len(self.loop_history),
            "passed": self.loop_history[-1].get("passed", False) if self.loop_history else False,
            "best_reward": self.best_reward,
            "reward_progression": rewards,
            "reader_score_progression": reader_scores,
            "reward_improvement": rewards[-1] - rewards[0] if len(rewards) > 1 else 0,
            "policy_summary": self.ppo_strategy.get_policy_summary(),
            "most_effective_action": max(
                self.ppo_strategy.action_values.items(),
                key=lambda x: x[1]
            )[0].value if self.ppo_strategy.action_values else "unknown",
            "action_distribution": {
                k.value: v for k, v in self.ppo_strategy.action_counts.items()
            },
        }
