"""
GRPO (Group Relative Policy Optimization) 训练器

GRPO是DeepSeek在DeepSeekMath论文中提出的算法，相比PPO:
1. 不需要critic网络，减少内存开销
2. 使用组内相对奖励计算优势，更稳定
3. 适合大模型RL训练

算法流程:
1. 对每条prompt采样G个输出
2. 计算每个输出的奖励
3. 计算组内均值和标准差进行归一化
4. 使用PPO-clip更新策略
"""
import json
import math
import random
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import numpy as np


class WritingAction(str, Enum):
    """写作动作空间"""
    GENERATE = "generate"       # 生成新内容
    REVISE = "revise"          # 修改内容
    DELETE = "delete"          # 删除内容
    KEEP = "keep"              # 保留不变


@dataclass
class GRPOConfig:
    """GRPO算法配置"""
    
    # 组大小（采样数量）
    group_size: int = 4
    
    # PPO参数
    clip_epsilon: float = 0.2          # 裁剪范围
    beta: float = 0.04                 # KL惩罚系数
    
    # 训练参数
    learning_rate: float = 1e-5
    num_iterations: int = 3            # 每批数据迭代次数
    temperature: float = 0.7           # 采样温度
    
    # 奖励权重
    reward_weights: Dict[str, float] = field(default_factory=lambda: {
        "reader_score": 0.35,
        "hook_score": 0.20,
        "immersion_score": 0.15,
        "continuity_score": 0.15,
        "length_bonus": 0.10,
        "revision_bonus": 0.05,
    })
    
    # 目标字数
    target_word_count: int = 3000
    word_count_tolerance: float = 0.2
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_size": self.group_size,
            "clip_epsilon": self.clip_epsilon,
            "beta": self.beta,
            "learning_rate": self.learning_rate,
            "num_iterations": self.num_iterations,
            "temperature": self.temperature,
            "reward_weights": self.reward_weights,
            "target_word_count": self.target_word_count,
            "word_count_tolerance": self.word_count_tolerance,
        }


@dataclass
class Episode:
    """训练回合数据"""
    state: str                          # 状态（写作上下文）
    action: WritingAction              # 动作
    output: str                        # 输出内容
    reward: float                      # 奖励
    advantage: float                   # 优势值
    log_prob: float                    # 动作对数概率
    group_mean_reward: float           # 组内平均奖励
    group_std_reward: float            # 组内奖励标准差


class GroupRewardNormalizer:
    """组内奖励归一化器"""
    
    @staticmethod
    def normalize(rewards: List[float]) -> Tuple[List[float], float, float]:
        """
        对组内奖励进行归一化
        
        Returns:
            normalized_rewards: 归一化后的奖励
            mean: 组内均值
            std: 组内标准差
        """
        if len(rewards) < 2:
            return [0.0] * len(rewards), sum(rewards) / len(rewards) if rewards else 0.0, 1.0
        
        mean = sum(rewards) / len(rewards)
        variance = sum((r - mean) ** 2 for r in rewards) / len(rewards)
        std = math.sqrt(variance) if variance > 0 else 1.0
        
        # 避免除以0
        if std < 1e-8:
            std = 1.0
        
        normalized = [(r - mean) / std for r in rewards]
        return normalized, mean, std


class GRPOPolicy:
    """
    GRPO策略管理器
    
    维护动作价值估计，支持基于组的策略更新
    """
    
    def __init__(self, config: GRPOConfig):
        self.config = config
        
        # 动作价值估计
        self.action_values: Dict[WritingAction, float] = {
            WritingAction.GENERATE: 0.5,
            WritingAction.REVISE: 0.5,
            WritingAction.DELETE: 0.3,
            WritingAction.KEEP: 0.4,
        }
        
        # 动作计数
        self.action_counts: Dict[WritingAction, int] = {
            WritingAction.GENERATE: 1,
            WritingAction.REVISE: 1,
            WritingAction.DELETE: 1,
            WritingAction.KEEP: 1,
        }
        
        # 历史记录
        self.episode_history: List[Episode] = []
        self.total_episodes = 0
        
        # 旧策略（用于计算概率比）
        self.old_action_values: Dict[WritingAction, float] = self.action_values.copy()
    
    def sample_group(
        self,
        state: str,
        group_size: int,
        temperature: float = 0.7
    ) -> List[Tuple[WritingAction, float]]:
        """
        采样一组动作
        
        Returns:
            [(action, log_prob), ...]
        """
        actions = []
        probs = self._get_action_probs(temperature)
        
        for _ in range(group_size):
            action = self._sample_action(probs)
            log_prob = math.log(probs[action])
            actions.append((action, log_prob))
        
        return actions
    
    def _get_action_probs(self, temperature: float = 0.7) -> Dict[WritingAction, float]:
        """获取动作概率分布"""
        actions = list(WritingAction)
        values = [self.action_values[a] for a in actions]
        
        # 使用温度参数调整分布
        max_val = max(values)
        exp_values = [math.exp((v - max_val) / temperature) for v in values]
        total = sum(exp_values)
        
        return {a: exp_values[i] / total for i, a in enumerate(actions)}
    
    def _sample_action(self, probs: Dict[WritingAction, float]) -> WritingAction:
        """根据概率采样动作"""
        r = random.random()
        cumsum = 0.0
        for action, prob in probs.items():
            cumsum += prob
            if r <= cumsum:
                return action
        return WritingAction.GENERATE
    
    def compute_advantages(self, episodes: List[Episode]) -> List[Episode]:
        """
        计算优势值（组内归一化）
        
        GRPO核心：使用组内相对奖励作为优势
        """
        rewards = [ep.reward for ep in episodes]
        normalized_rewards, mean, std = GroupRewardNormalizer.normalize(rewards)
        
        for i, ep in enumerate(episodes):
            ep.advantage = normalized_rewards[i]
            ep.group_mean_reward = mean
            ep.group_std_reward = std
        
        return episodes
    
    def update(
        self,
        episodes: List[Episode],
        old_policy_probs: Optional[Dict[WritingAction, float]] = None
    ) -> Dict[str, Any]:
        """
        使用GRPO更新策略
        
        Args:
            episodes: 训练回合列表（已计算优势）
            old_policy_probs: 旧策略概率（用于计算概率比）
            
        Returns:
            训练统计信息
        """
        if not episodes:
            return {"status": "no_data"}
        
        # 保存旧策略
        self.old_action_values = self.action_values.copy()
        
        # 计算当前策略概率
        current_probs = self._get_action_probs(self.config.temperature)
        
        # 按动作分组计算更新
        action_gradients: Dict[WritingAction, List[float]] = {
            a: [] for a in WritingAction
        }
        
        for ep in episodes:
            action = ep.action
            advantage = ep.advantage
            
            # 计算概率比 r(θ) = π_θ(a|s) / π_θ_old(a|s)
            old_prob = old_policy_probs.get(action, 0.25) if old_policy_probs else ep.log_prob
            current_prob = current_probs[action]
            
            ratio = current_prob / max(old_prob, 1e-8)
            
            # PPO-clip目标
            clipped_ratio = max(min(ratio, 1 + self.config.clip_epsilon),
                              1 - self.config.clip_epsilon)
            
            # 取最小值
            objective = min(ratio * advantage, clipped_ratio * advantage)
            
            # KL惩罚
            kl_penalty = self.config.beta * (current_prob - old_prob)
            
            # 总梯度
            gradient = objective - kl_penalty
            action_gradients[action].append(gradient)
        
        # 更新动作价值
        learning_rate = self.config.learning_rate
        update_stats = {}
        
        for action in WritingAction:
            if action_gradients[action]:
                avg_gradient = sum(action_gradients[action]) / len(action_gradients[action])
                old_value = self.action_values[action]
                new_value = old_value + learning_rate * avg_gradient
                self.action_values[action] = max(0.0, min(1.0, new_value))
                
                update_stats[action.value] = {
                    "old": round(old_value, 4),
                    "new": round(self.action_values[action], 4),
                    "gradient": round(avg_gradient, 4),
                }
                
                self.action_counts[action] += len(action_gradients[action])
        
        self.total_episodes += len(episodes)
        self.episode_history.extend(episodes)
        
        return {
            "status": "success",
            "episodes_processed": len(episodes),
            "total_episodes": self.total_episodes,
            "action_updates": update_stats,
            "avg_advantage": sum(ep.advantage for ep in episodes) / len(episodes),
        }
    
    def get_policy_summary(self) -> Dict[str, Any]:
        """获取策略摘要"""
        probs = self._get_action_probs()
        return {
            "action_values": {a.value: round(v, 4) for a, v in self.action_values.items()},
            "action_probs": {a.value: round(p, 4) for a, p in probs.items()},
            "action_counts": {a.value: c for a, c in self.action_counts.items()},
            "total_episodes": self.total_episodes,
        }


class RewardFunction:
    """
    奖励函数 - 融合人工评估与自动化指标
    """
    
    def __init__(self, config: GRPOConfig):
        self.config = config
    
    def compute(
        self,
        reader_feedback: Dict[str, Any],
        draft: str,
        action: WritingAction,
        previous_feedback: Optional[Dict[str, Any]] = None,
        outline_compliance: float = 1.0,
    ) -> Tuple[float, Dict[str, float]]:
        """
        计算综合Reward
        
        Returns:
            total_reward: 总奖励
            reward_breakdown: 分项奖励明细
        """
        breakdown = {}
        weights = self.config.reward_weights
        
        # 1. Reader Agent 评分（核心）
        reader_score = float(reader_feedback.get("reader_score", 0) or 0)
        breakdown["reader_score"] = reader_score * weights["reader_score"]
        
        # 2. 钩子评分
        hook_score = float(reader_feedback.get("hook_score", 0) or 0)
        breakdown["hook_score"] = hook_score * weights["hook_score"]
        
        # 3. 沉浸感评分
        immersion = float(reader_feedback.get("immersion_score", 0) or 0)
        breakdown["immersion_score"] = immersion * weights["immersion_score"]
        
        # 4. 上下文连贯性
        continuity = float(reader_feedback.get("continuity_score", 0) or 0)
        breakdown["continuity_score"] = continuity * weights["continuity_score"]
        
        # 5. 字数奖励
        word_count = len(draft.replace(" ", "").replace("\n", ""))
        word_count_ratio = word_count / max(self.config.target_word_count, 1)
        
        if 0.9 <= word_count_ratio <= 1.1:
            breakdown["length_bonus"] = weights["length_bonus"]
        elif word_count_ratio < 0.8:
            breakdown["length_bonus"] = -weights["length_bonus"]
        else:
            breakdown["length_bonus"] = 0
        
        # 6. 改进幅度奖励
        revision_bonus = 0
        if previous_feedback and action == WritingAction.REVISE:
            prev_score = float(previous_feedback.get("reader_score", 0) or 0)
            improvement = reader_score - prev_score
            if improvement > 0:
                revision_bonus = min(improvement * weights["revision_bonus"] * 5, 0.05)
            elif improvement < -0.1:
                revision_bonus = max(improvement * 2, -0.05)
        breakdown["revision_bonus"] = revision_bonus
        
        # 7. 大纲遵循度
        if outline_compliance < 1.0:
            breakdown["outline_penalty"] = (1 - outline_compliance) * 0.05
        else:
            breakdown["outline_penalty"] = 0
        
        # 计算总奖励（归一化到0-1）
        total = sum(breakdown.values())
        total = max(0.0, min(1.0, total + 0.5))
        
        return total, breakdown


class GRPOTrainer:
    """
    GRPO训练器 - 用于Writer-Reader RL对抗训练
    """
    
    def __init__(
        self,
        novel_id: int,
        config: Optional[GRPOConfig] = None,
    ):
        self.novel_id = novel_id
        self.config = config or GRPOConfig()
        
        # 初始化策略
        self.policy = GRPOPolicy(self.config)
        self.reward_fn = RewardFunction(self.config)
        
        # 训练统计
        self.training_history: List[Dict[str, Any]] = []
        self.iteration = 0
        
        logger.info(f"[GRPOTrainer] 初始化完成: novel_id={novel_id}, group_size={self.config.group_size}")
    
    async def train_step(
        self,
        state: str,
        writer_agent,
        reader_agent,
        context: Dict[str, Any],
        outline: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行一个GRPO训练步骤
        
        流程:
        1. 采样一组动作
        2. 执行动作生成输出
        3. Reader评估
        4. 计算奖励
        5. 计算优势（组内归一化）
        6. 更新策略
        
        Returns:
            训练结果统计
        """
        self.iteration += 1
        logger.info(f"[GRPOTrainer] 训练步骤 {self.iteration}")
        
        # 1. 采样动作组
        group_actions = self.policy.sample_group(
            state,
            self.config.group_size,
            self.config.temperature
        )
        
        # 2. 执行动作并收集结果
        episodes: List[Episode] = []
        
        for action, log_prob in group_actions:
            # 生成输出
            output = await self._execute_action(
                writer_agent,
                action,
                context,
                outline
            )
            
            # Reader评估
            reader_feedback = await self._evaluate_output(
                reader_agent,
                output,
                outline
            )
            
            # 计算奖励
            reward, breakdown = self.reward_fn.compute(
                reader_feedback=reader_feedback,
                draft=output,
                action=action
            )
            
            episode = Episode(
                state=state,
                action=action,
                output=output,
                reward=reward,
                advantage=0.0,  # 稍后计算
                log_prob=log_prob,
                group_mean_reward=0.0,
                group_std_reward=0.0
            )
            episodes.append(episode)
            
            logger.debug(f"[GRPOTrainer] 动作={action.value}, 奖励={reward:.4f}")
        
        # 3. 计算优势
        episodes = self.policy.compute_advantages(episodes)
        
        # 4. 更新策略
        old_probs = self.policy._get_action_probs()
        update_stats = self.policy.update(episodes, old_probs)
        
        # 5. 记录历史
        step_record = {
            "iteration": self.iteration,
            "episodes": len(episodes),
            "avg_reward": sum(ep.reward for ep in episodes) / len(episodes),
            "avg_advantage": sum(ep.advantage for ep in episodes) / len(episodes),
            "update_stats": update_stats,
            "policy_summary": self.policy.get_policy_summary(),
        }
        self.training_history.append(step_record)
        
        logger.info(f"[GRPOTrainer] 步骤 {self.iteration} 完成: 平均奖励={step_record['avg_reward']:.4f}")
        
        return step_record
    
    async def _execute_action(
        self,
        writer_agent,
        action: WritingAction,
        context: Dict[str, Any],
        outline: Dict[str, Any]
    ) -> str:
        """执行写作动作"""
        # 根据动作调整上下文
        action_context = context.copy()
        action_context["outline"] = outline
        action_context["action"] = action.value
        
        try:
            result = await writer_agent.process(action_context)
            return result.get("content", "")
        except Exception as e:
            logger.error(f"[GRPOTrainer] 执行动作失败: {e}")
            return ""
    
    async def _evaluate_output(
        self,
        reader_agent,
        output: str,
        outline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用Reader Agent评估输出"""
        try:
            reader_context = {
                "chapter_content": output,
                "outline": outline,
                "target_reader": "大众网文读者",
            }
            result = await reader_agent.process(reader_context)
            return result.get("reader_feedback", {})
        except Exception as e:
            logger.error(f"[GRPOTrainer] 评估失败: {e}")
            return {}
    
    def get_training_report(self) -> Dict[str, Any]:
        """生成训练报告"""
        if not self.training_history:
            return {"status": "no_history"}
        
        rewards = [r["avg_reward"] for r in self.training_history]
        advantages = [r["avg_advantage"] for r in self.training_history]
        
        return {
            "novel_id": self.novel_id,
            "total_iterations": self.iteration,
            "config": self.config.to_dict(),
            "reward_progression": {
                "initial": rewards[0] if rewards else 0,
                "final": rewards[-1] if rewards else 0,
                "improvement": rewards[-1] - rewards[0] if len(rewards) > 1 else 0,
                "trend": "improving" if len(rewards) > 1 and rewards[-1] > rewards[0] else "stable",
            },
            "advantage_stats": {
                "mean": sum(advantages) / len(advantages) if advantages else 0,
                "max": max(advantages) if advantages else 0,
                "min": min(advantages) if advantages else 0,
            },
            "final_policy": self.policy.get_policy_summary(),
            "training_history": self.training_history[-10:],  # 最近10次
        }
    
    def save_checkpoint(self, path: str):
        """保存训练检查点"""
        checkpoint = {
            "novel_id": self.novel_id,
            "config": self.config.to_dict(),
            "policy": self.policy.get_policy_summary(),
            "iteration": self.iteration,
            "training_history": self.training_history,
        }
        
        import json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[GRPOTrainer] 检查点已保存: {path}")
    
    def load_checkpoint(self, path: str):
        """加载训练检查点"""
        import json
        with open(path, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)
        
        self.iteration = checkpoint.get("iteration", 0)
        self.training_history = checkpoint.get("training_history", [])
        
        policy_data = checkpoint.get("policy", {})
        if "action_values" in policy_data:
            for action_str, value in policy_data["action_values"].items():
                action = WritingAction(action_str)
                self.policy.action_values[action] = value
        
        logger.info(f"[GRPOTrainer] 检查点已加载: {path}")
