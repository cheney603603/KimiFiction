"""
推理引擎模块

RL推理引擎
使用训练好的LoRA适配器进行推理，
支持GRPO采样和TPO优化。
"""
import asyncio
from typing import List, Tuple, Optional, Callable
import numpy as np
import torch

from .config import RLTrainingConfig
from .models import RLWritingModel


class RLInferenceEngine:
    """
    RL推理引擎
    
    功能：
    - 加载基础模型和LoRA适配器
    - 支持GRPO采样（生成多个候选）
    - 支持TPO优化（选择最优候选）
    """
    
    def __init__(
        self, 
        base_model: str, 
        adapter_path: str = None,
        config: RLTrainingConfig = None
    ):
        """
        Args:
            base_model: 基础模型名称或路径
            adapter_path: LoRA适配器路径（可选）
            config: 训练配置（可选，使用默认配置）
        """
        self.base_model = base_model
        self.adapter_path = adapter_path
        self.config = config or RLTrainingConfig()
        self.config.model_name = base_model
        
        self.model = RLWritingModel(self.config)
        self.reward_fn = None
    
    async def load(self):
        """加载模型和适配器"""
        await self.model.load()
        
        if self.adapter_path:
            self.model.load_adapter(self.adapter_path)
            print(f"已加载适配器: {self.adapter_path}")
    
    def set_reward_function(self, reward_fn: Callable):
        """
        设置奖励函数
        
        Args:
            reward_fn: 奖励函数，签名 reward_fn(text: str, context: dict) -> float
        """
        self.reward_fn = reward_fn
    
    async def generate_with_grpo(
        self,
        prompt: str,
        group_size: int = 4,
        temperature: float = 0.7,
        return_all: bool = False
    ) -> Tuple[str, List[str]]:
        """
        GRPO生成：返回最优response和所有候选
        
        1. 采样 group_size 个responses
        2. 用reward模型排序
        3. 返回最优
        
        Args:
            prompt: 输入提示词
            group_size: 每组样本数
            temperature: 采样温度
            return_all: 是否返回所有候选
            
        Returns:
            (最优response, 所有候选列表)
        """
        print(f"GRPO生成: 采样 {group_size} 个候选...")
        
        # 生成多个候选
        candidates = []
        for i in range(group_size):
            # 轻微变化温度以增加多样性
            temp = temperature + (i * 0.05)
            response = await self.model.generate_async(
                prompt,
                temperature=temp
            )
            candidates.append(response)
        
        # 如果没有奖励函数，返回第一个
        if self.reward_fn is None:
            return candidates[0], candidates if return_all else []
        
        # 评估每个候选
        scores = []
        for candidate in candidates:
            score = self.reward_fn(candidate, {"prompt": prompt})
            scores.append(score)
        
        # 选择最优
        best_idx = int(np.argmax(scores))
        best_response = candidates[best_idx]
        
        print(f"GRPO选择: 候选 #{best_idx + 1}, 得分={scores[best_idx]:.4f}")
        
        if return_all:
            return best_response, candidates
        return best_response, []
    
    async def generate_with_tpo(
        self,
        prompt: str,
        num_candidates: int = 8,
        num_iterations: int = 1
    ) -> str:
        """
        TPO生成：返回优化后的response
        
        通过多轮采样和选择来优化生成质量。
        
        Args:
            prompt: 输入提示词
            num_candidates: 每轮候选数量
            num_iterations: 迭代轮数
            
        Returns:
            优化后的文本
        """
        current_prompt = prompt
        
        for iteration in range(num_iterations):
            print(f"TPO迭代 {iteration + 1}/{num_iterations}...")
            
            # 生成候选
            candidates = []
            for i in range(num_candidates):
                response = await self.model.generate_async(
                    current_prompt,
                    temperature=0.7 + (i * 0.05)
                )
                candidates.append(response)
            
            # 评估并选择最优
            if self.reward_fn:
                scores = [self.reward_fn(c, {"prompt": current_prompt}) for c in candidates]
                best_idx = int(np.argmax(scores))
                best_response = candidates[best_idx]
                print(f"  选择候选 #{best_idx + 1}, 得分={scores[best_idx]:.4f}")
            else:
                best_response = candidates[0]
            
            # 更新prompt进行下一轮迭代
            if iteration < num_iterations - 1:
                current_prompt = f"基于以下内容进行改进:\n\n{best_response}\n\n改进版本:"
        
        return best_response
    
    async def generate_best_of_n(
        self,
        prompt: str,
        n: int = 8
    ) -> str:
        """
        Best-of-N生成：生成N个选择最优
        
        这是TPO的简化版本，只进行一轮选择。
        
        Args:
            prompt: 输入提示词
            n: 采样数量
            
        Returns:
            最优结果
        """
        best, _ = await self.generate_with_grpo(prompt, group_size=n)
        return best
    
    async def self_consistency_generate(
        self,
        prompt: str,
        num_samples: int = 5,
        aggregation: str = "vote"
    ) -> str:
        """
        自一致性生成
        
        通过多次采样并聚合结果来提高一致性。
        
        Args:
            prompt: 输入提示词
            num_samples: 采样次数
            aggregation: 聚合方法 ("vote", "average")
            
        Returns:
            聚合后的结果
        """
        # 生成多个样本
        samples = []
        for _ in range(num_samples):
            response = await self.model.generate_async(prompt, temperature=0.7)
            samples.append(response)
        
        if aggregation == "vote":
            # 简单投票：返回最常见的（这里使用奖励函数选择）
            if self.reward_fn:
                scores = [self.reward_fn(s, {"prompt": prompt}) for s in samples]
                best_idx = int(np.argmax(scores))
                return samples[best_idx]
            return samples[0]
        
        elif aggregation == "average":
            # 返回第一个（实际应用中可以实现更复杂的平均逻辑）
            return samples[0]
        
        else:
            raise ValueError(f"未知的聚合方法: {aggregation}")
    
    def create_default_reward_fn(self) -> Callable:
        """
        创建默认奖励函数
        
        基于文本质量的基本评估。
        """
        def reward_fn(text: str, context: dict = None) -> float:
            score = 0.0
            
            # 长度适中
            length = len(text)
            if 50 <= length <= 2000:
                score += 0.3
            
            # 句子多样性
            sentences = text.replace('。', '.').split('.')
            if len(sentences) >= 3:
                score += 0.2
            
            # 词汇多样性
            words = text.split()
            if words:
                unique_ratio = len(set(words)) / len(words)
                score += unique_ratio * 0.3
            
            # 标点使用
            if any(c in text for c in '，。！？'):
                score += 0.2
            
            return score
        
        return reward_fn
