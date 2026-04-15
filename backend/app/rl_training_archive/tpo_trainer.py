"""
TPO训练器模块

TPO (Test-time Preference Optimization)
在推理时通过采样和偏好学习优化生成质量。
不需要训练，只需要推理时使用。

核心思想：
1. 对同一个prompt生成多个candidate responses
2. 用reward模型对每个candidate打分
3. 选择reward最高的candidate
4. 用偏好pair更新隐式reward模型

适用于：写作质量优化、情节连贯性提升

TPO和GRPO结合：
训练阶段用GRPO → 推理阶段用TPO进一步优化
"""
import asyncio
from typing import List, Callable, Optional, Tuple
import numpy as np

from .config import RLTrainingConfig
from .models import RLWritingModel


class TPOTrainer:
    """
    TPO (Test-time Preference Optimization) 训练器
    
    在测试/推理时优化生成质量，无需额外训练。
    通过采样多个候选并选择最优来提升输出质量。
    """
    
    def __init__(self, model: RLWritingModel, reward_fn: Optional[Callable] = None):
        """
        Args:
            model: RL写作模型
            reward_fn: 奖励函数，用于评估生成质量
                      签名: reward_fn(text: str, context: dict) -> float
        """
        self.model = model
        self.reward_fn = reward_fn or self._default_reward_fn
        self.config = model.config
    
    def _default_reward_fn(self, text: str, context: dict = None) -> float:
        """
        默认奖励函数
        
        基于文本长度和基本质量指标进行评分。
        实际使用中应该替换为专门的奖励模型。
        """
        score = 0.0
        
        # 长度奖励（适中长度更好）
        length = len(text)
        if 100 <= length <= 1000:
            score += 0.3
        elif length > 1000:
            score += 0.1
        
        # 多样性奖励（标点符号数量作为简单代理）
        punctuation_count = sum(1 for c in text if c in '。！？.!?')
        if punctuation_count >= 3:
            score += 0.2
        
        # 连贯性奖励（句子长度变化）
        sentences = text.replace('。', '.').replace('！', '!').replace('？', '?').split('.')
        avg_len = np.mean([len(s) for s in sentences if s.strip()])
        if 10 <= avg_len <= 100:
            score += 0.2
        
        # 避免重复
        words = text.split()
        if len(words) > 0:
            unique_ratio = len(set(words)) / len(words)
            score += unique_ratio * 0.3
        
        return score
    
    async def optimize(
        self, 
        prompt: str, 
        num_samples: int = 8,
        temperature: float = None,
        top_p: float = None
    ) -> str:
        """
        TPO优化：在生成多个候选中选择最优
        
        1. 采样 num_samples 个不同的responses
        2. 用reward_fn打分
        3. 选择/融合最优的responses
        
        Args:
            prompt: 输入提示词
            num_samples: 采样数量
            temperature: 采样温度（覆盖配置）
            top_p: nucleus采样参数（覆盖配置）
            
        Returns:
            优化后的文本
        """
        if self.model.lora_model is None:
            raise RuntimeError("模型未加载")
        
        temp = temperature or self.config.tpo_temperature
        tp = top_p or self.config.tpo_top_p
        
        print(f"TPO优化: 生成 {num_samples} 个候选...")
        
        # 生成多个候选
        candidates = []
        for i in range(num_samples):
            response = await self.model.generate_async(
                prompt,
                temperature=temp + (i * 0.1),  # 轻微变化温度以增加多样性
                top_p=tp
            )
            candidates.append(response)
        
        # 评估每个候选
        scores = []
        for candidate in candidates:
            score = self.reward_fn(candidate, {"prompt": prompt})
            scores.append(score)
        
        # 选择最优
        best_idx = np.argmax(scores)
        best_candidate = candidates[best_idx]
        best_score = scores[best_idx]
        
        print(f"TPO优化完成: 选择候选 #{best_idx + 1}, 得分={best_score:.4f}")
        
        return best_candidate
    
    async def optimize_with_rerank(
        self,
        prompt: str,
        num_samples: int = 8,
        top_k: int = 3
    ) -> Tuple[str, List[Tuple[str, float]]]:
        """
        TPO优化并返回重排序结果
        
        Args:
            prompt: 输入提示词
            num_samples: 采样数量
            top_k: 返回前k个结果
            
        Returns:
            (最优结果, [(候选, 分数), ...])
        """
        # 生成候选
        candidates = []
        for i in range(num_samples):
            response = await self.model.generate_async(
                prompt,
                temperature=self.config.tpo_temperature + (i * 0.05)
            )
            candidates.append(response)
        
        # 评分并排序
        scored_candidates = [
            (candidate, self.reward_fn(candidate, {"prompt": prompt}))
            for candidate in candidates
        ]
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        return scored_candidates[0][0], scored_candidates[:top_k]
    
    async def style_transfer(
        self, 
        text: str, 
        style: str,
        num_samples: int = 5
    ) -> str:
        """
        风格迁移：用TPO优化风格
        
        Args:
            text: 原始文本
            style: 目标风格描述（如"正式", "幽默", "简洁"）
            num_samples: 采样数量
            
        Returns:
            风格迁移后的文本
        """
        # 构建风格迁移提示
        prompt = f"请将以下文本改写为{style}风格:\n\n{text}\n\n改写后的文本:"
        
        # 使用TPO优化
        return await self.optimize(prompt, num_samples=num_samples)
    
    async def iterative_refinement(
        self,
        prompt: str,
        num_iterations: int = 3,
        samples_per_iter: int = 4
    ) -> str:
        """
        迭代优化：多轮TPO优化
        
        每轮选择最优结果作为下一轮的基础。
        
        Args:
            prompt: 初始提示词
            num_iterations: 迭代轮数
            samples_per_iter: 每轮采样数
            
        Returns:
            最终优化结果
        """
        current_text = None
        
        for iteration in range(num_iterations):
            print(f"迭代优化 {iteration + 1}/{num_iterations}...")
            
            # 构建提示
            if current_text is None:
                iter_prompt = prompt
            else:
                iter_prompt = f"基于以下内容进行改进:\n\n{current_text}\n\n改进版本:"
            
            # TPO优化
            current_text = await self.optimize(
                iter_prompt,
                num_samples=samples_per_iter
            )
        
        return current_text
    
    async def ensemble_generate(
        self,
        prompt: str,
        num_samples: int = 8,
        ensemble_method: str = "best"
    ) -> str:
        """
        集成生成：结合多个候选的优势
        
        Args:
            prompt: 输入提示词
            num_samples: 采样数量
            ensemble_method: 集成方法 ("best", "vote", "merge")
            
        Returns:
            集成后的结果
        """
        # 生成候选
        candidates = []
        for i in range(num_samples):
            response = await self.model.generate_async(
                prompt,
                temperature=self.config.tpo_temperature
            )
            candidates.append(response)
        
        # 评分
        scores = [self.reward_fn(c, {"prompt": prompt}) for c in candidates]
        
        if ensemble_method == "best":
            # 选择最优
            best_idx = np.argmax(scores)
            return candidates[best_idx]
        
        elif ensemble_method == "vote":
            # 简单投票：返回最常见的开头
            # 实际实现中可以使用更复杂的投票机制
            return candidates[np.argmax(scores)]
        
        elif ensemble_method == "merge":
            # 合并：选择得分最高的两个进行简单拼接
            top_indices = np.argsort(scores)[-2:]
            return candidates[top_indices[1]] + "\n\n" + candidates[top_indices[0]]
        
        else:
            raise ValueError(f"未知的集成方法: {ensemble_method}")
