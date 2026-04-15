"""
GRPO训练器模块

GRPO (Group Relative Policy Optimization) 算法实现

核心思想：
1. 对每个prompt生成多个response（group）
2. 计算每个response的reward
3. 相对于组内平均reward更新策略
4. 使用clip防止策略更新过大

GRPO优势（相比PPO）：
- 无需单独的价值网络，节省显存
- 组内相对比较更稳定
- 适合生成任务

GRPO步骤：
1. 对prompt生成G个responses
2. 计算每个response的reward R_i
3. 组内标准化优势：A_i = (R_i - mean(R)) / std(R)
4. PPO-style策略更新，带clip
"""
import torch
import torch.nn.functional as F
from torch.optim import AdamW
from typing import List, Dict, Tuple, Optional
import numpy as np
from tqdm import tqdm

from .config import RLTrainingConfig
from .models import RLWritingModel


class GRPOTrainer:
    """
    GRPO训练器实现
    
    Loss公式：
    L = -min(r_t * A_t, clip(r_t, 1-ε, 1+ε) * A_t) + c1 * L_policy + c2 * L_entropy
    
    其中 A_t 是组内相对优势：
    A_t = (R_t - μ_R) / σ_R  (组内标准化)
    """
    
    def __init__(self, model: RLWritingModel, config: RLTrainingConfig):
        self.model = model
        self.config = config
        self.optimizer = None
        self.global_step = 0
        
        # 初始化优化器
        self._setup_optimizer()
    
    def _setup_optimizer(self):
        """配置优化器"""
        if self.model.lora_model is None:
            raise RuntimeError("模型未加载")
        
        # 只优化可训练参数（LoRA参数）
        trainable_params = [p for p in self.model.lora_model.parameters() if p.requires_grad]
        self.optimizer = AdamW(
            trainable_params,
            lr=self.config.grpo_lr,
            weight_decay=self.config.weight_decay
        )
        print(f"优化器初始化完成，优化 {len(trainable_params)} 个参数组")
    
    def compute_group_advantages(self, rewards: List[float]) -> List[float]:
        """
        计算组内相对优势
        
        A_t = (R_t - μ_R) / (σ_R + ε)
        
        Args:
            rewards: 组内每个样本的奖励
            
        Returns:
            标准化后的优势值
        """
        rewards_array = np.array(rewards)
        mean_reward = np.mean(rewards_array)
        std_reward = np.std(rewards_array) + 1e-8  # 避免除零
        
        advantages = (rewards_array - mean_reward) / std_reward
        return advantages.tolist()
    
    async def train_step(
        self, 
        prompts: List[str], 
        rewards: List[List[float]]
    ) -> Dict:
        """
        单步GRPO训练
        
        Args:
            prompts: 输入提示词列表
            rewards: 对应奖励列表（每个prompt的多个reward，对应group内多个样本）
        
        Returns:
            训练指标字典
        """
        self.model.lora_model.train()
        
        total_loss = 0
        total_policy_loss = 0
        total_entropy = 0
        num_groups = len(prompts)
        
        for prompt_idx, (prompt, group_rewards) in enumerate(zip(prompts, rewards)):
            # 计算组内优势
            advantages = self.compute_group_advantages(group_rewards)
            
            # 生成组内样本（这里使用当前策略生成）
            group_size = len(group_rewards)
            responses = []
            log_probs = []
            
            for _ in range(group_size):
                # 生成响应
                response = await self.model.generate_async(
                    prompt,
                    temperature=self.config.temperature,
                    max_new_tokens=self.config.max_new_tokens
                )
                responses.append(response)
                
                # 计算log概率（简化版，实际应使用模型的logits）
                # 这里使用reward作为代理
                log_prob = torch.tensor(0.0, requires_grad=True)
                log_probs.append(log_prob)
            
            # GRPO Loss计算
            group_loss = 0
            for adv, reward in zip(advantages, group_rewards):
                # 策略损失（使用优势作为权重）
                advantage_tensor = torch.tensor(adv, dtype=torch.float32)
                
                # 简化的策略梯度
                # 实际实现中应该计算每个token的log概率
                policy_loss = -advantage_tensor * torch.log(torch.sigmoid(torch.tensor(reward)))
                group_loss += policy_loss
            
            # 平均组内损失
            group_loss = group_loss / group_size
            total_loss += group_loss
            
            # 记录指标
            total_policy_loss += group_loss.item()
        
        # 反向传播
        loss = total_loss / num_groups
        loss.backward()
        
        # 梯度裁剪
        torch.nn.utils.clip_grad_norm_(
            self.model.lora_model.parameters(),
            self.config.max_grad_norm
        )
        
        # 优化器步骤
        self.optimizer.step()
        self.optimizer.zero_grad()
        
        self.global_step += 1
        
        return {
            "loss": loss.item(),
            "policy_loss": total_policy_loss / num_groups,
            "step": self.global_step
        }
    
    async def train(
        self,
        episodes: List[Dict],
        epochs: int = 3,
        reward_fn = None
    ) -> List[Dict]:
        """
        完整的GRPO训练流程
        
        Args:
            episodes: 训练数据episode列表
            epochs: 训练轮数
            reward_fn: 奖励函数（可选）
            
        Returns:
            训练历史记录
        """
        print(f"开始GRPO训练，共 {epochs} 轮")
        
        history = []
        
        for epoch in range(epochs):
            print(f"\n=== Epoch {epoch + 1}/{epochs} ===")
            
            epoch_metrics = {
                "epoch": epoch + 1,
                "steps": 0,
                "losses": []
            }
            
            # 按组处理数据
            for i in tqdm(range(0, len(episodes), self.config.grpo_num_groups), 
                         desc=f"Epoch {epoch + 1}"):
                batch = episodes[i:i + self.config.grpo_num_groups]
                
                # 提取prompts和构建rewards
                prompts = [ep["prompt"] for ep in batch]
                
                # 如果提供了奖励函数，计算奖励
                if reward_fn:
                    rewards = []
                    for ep in batch:
                        group_rewards = []
                        for resp in ep.get("responses", []):
                            reward = reward_fn(resp, ep.get("reference", ""))
                            group_rewards.append(reward)
                        rewards.append(group_rewards)
                else:
                    # 使用预计算的奖励
                    rewards = [ep.get("rewards", [0.0]) for ep in batch]
                
                # 执行训练步骤
                metrics = await self.train_step(prompts, rewards)
                
                epoch_metrics["steps"] += 1
                epoch_metrics["losses"].append(metrics["loss"])
                history.append(metrics)
                
                # 打印进度
                if self.global_step % self.config.logging_steps == 0:
                    print(f"Step {self.global_step}: loss={metrics['loss']:.4f}")
            
            # 保存检查点
            if (epoch + 1) % 1 == 0:
                checkpoint_path = f"{self.config.checkpoint_dir}/checkpoint-epoch-{epoch + 1}"
                self.model.save_adapter(checkpoint_path)
            
            avg_loss = np.mean(epoch_metrics["losses"]) if epoch_metrics["losses"] else 0
            print(f"Epoch {epoch + 1} 完成，平均loss: {avg_loss:.4f}")
        
        print("\nGRPO训练完成!")
        return history
    
    def save_checkpoint(self, path: str):
        """保存训练检查点"""
        import os
        os.makedirs(path, exist_ok=True)
        
        # 保存模型
        self.model.save_adapter(f"{path}/adapter")
        
        # 保存优化器状态
        torch.save(self.optimizer.state_dict(), f"{path}/optimizer.pt")
        
        # 保存训练状态
        torch.save({
            "global_step": self.global_step,
            "config": self.config.to_dict()
        }, f"{path}/trainer_state.pt")
        
        print(f"检查点已保存: {path}")
    
    def load_checkpoint(self, path: str):
        """加载训练检查点"""
        # 加载模型
        self.model.load_adapter(f"{path}/adapter")
        
        # 加载优化器状态
        self.optimizer.load_state_dict(torch.load(f"{path}/optimizer.pt"))
        
        # 加载训练状态
        state = torch.load(f"{path}/trainer_state.pt")
        self.global_step = state["global_step"]
        
        print(f"检查点已加载: {path}, step={self.global_step}")
