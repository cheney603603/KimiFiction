"""
RL环境模块

写作RL环境
将写作任务封装为gym风格的RL环境，
供GRPO/TPO训练使用。
"""
from typing import Dict, Tuple, List, Any
import random

from .config import RLTrainingConfig


class WritingRLEnv:
    """
    写作RL环境
    
    模拟写作任务的RL环境，支持以下动作：
    - "generate": 生成新内容
    - "revise": 修改内容
    - "delete": 删除内容
    - "keep": 保留不变
    
    状态包含：
    - current_text: 当前文本内容
    - prompt: 原始提示
    - history: 操作历史
    """
    
    def __init__(self, config: RLTrainingConfig):
        self.config = config
        self.current_state = None
        self.episode_step = 0
        self.max_steps = 5
        self.prompt = ""
        self.current_text = ""
        self.history = []
    
    async def reset(self, prompt: str = None) -> Dict:
        """
        重置环境，返回初始状态
        
        Args:
            prompt: 可选的提示词，如果不提供则使用随机提示
            
        Returns:
            初始状态字典
        """
        self.episode_step = 0
        self.history = []
        
        # 设置提示
        if prompt is None:
            sample_prompts = [
                "写一个关于勇气的故事开头",
                "描述一个雨夜的场景",
                "写一段人物对话",
                "描述一个神秘的房间",
                "写一个意想不到的结局"
            ]
            self.prompt = random.choice(sample_prompts)
        else:
            self.prompt = prompt
        
        self.current_text = ""
        
        self.current_state = {
            "prompt": self.prompt,
            "current_text": self.current_text,
            "step": self.episode_step,
            "history": self.history
        }
        
        return self.current_state
    
    async def step(self, action: str, action_input: str = None) -> Tuple[Dict, float, bool]:
        """
        执行动作，返回 (next_state, reward, done)
        
        Actions:
        - "generate": 生成新内容
        - "revise": 修改内容
        - "delete": 删除内容
        - "keep": 保留不变
        
        Args:
            action: 动作类型
            action_input: 动作输入（如生成内容）
            
        Returns:
            (next_state, reward, done)
        """
        self.episode_step += 1
        reward = 0.0
        
        if action == "generate":
            # 生成新内容
            if action_input:
                self.current_text = action_input
                reward = self._compute_generation_reward()
            else:
                reward = -0.1  # 惩罚无效动作
        
        elif action == "revise":
            # 修改内容
            if action_input and self.current_text:
                self.current_text = action_input
                reward = self._compute_revision_reward()
            else:
                reward = -0.1
        
        elif action == "delete":
            # 删除内容
            if self.current_text:
                self.current_text = ""
                reward = -0.05  # 轻微惩罚删除
            else:
                reward = -0.1
        
        elif action == "keep":
            # 保留不变
            reward = 0.0
        
        else:
            raise ValueError(f"未知动作: {action}")
        
        # 记录历史
        self.history.append({
            "step": self.episode_step,
            "action": action,
            "reward": reward
        })
        
        # 更新状态
        self.current_state = {
            "prompt": self.prompt,
            "current_text": self.current_text,
            "step": self.episode_step,
            "history": self.history
        }
        
        # 判断是否结束
        done = self.episode_step >= self.max_steps or len(self.current_text) > 1000
        
        return self.current_state, reward, done
    
    def _compute_generation_reward(self) -> float:
        """
        计算生成动作的奖励
        
        基于文本质量的启发式奖励。
        """
        reward = 0.0
        text = self.current_text
        
        # 长度奖励
        length = len(text)
        if 50 <= length <= 500:
            reward += 0.3
        elif length > 500:
            reward += 0.1
        else:
            reward -= 0.1
        
        # 相关性奖励（简单检查是否包含关键词）
        prompt_keywords = set(self.prompt.split())
        text_words = set(text.split())
        overlap = len(prompt_keywords & text_words)
        reward += overlap * 0.1
        
        # 多样性奖励
        if len(set(text)) > len(text) * 0.5:
            reward += 0.2
        
        return reward
    
    def _compute_revision_reward(self) -> float:
        """
        计算修改动作的奖励
        
        鼓励改进文本质量。
        """
        reward = 0.1  # 基础奖励
        
        # 如果文本变长了，给予额外奖励
        if len(self.current_text) > 100:
            reward += 0.1
        
        return reward
    
    def get_state_embedding(self, state: Dict = None) -> List[float]:
        """
        将状态编码为向量
        
        用于策略网络的输入。
        
        Returns:
            状态向量
        """
        if state is None:
            state = self.current_state
        
        # 简单的特征提取
        text = state.get("current_text", "")
        prompt = state.get("prompt", "")
        step = state.get("step", 0)
        
        # 基础特征
        features = [
            len(text) / 1000.0,  # 文本长度归一化
            len(prompt) / 100.0,  # 提示长度归一化
            step / self.max_steps,  # 进度
        ]
        
        # 添加更多文本特征
        if text:
            features.append(len(set(text)) / len(text))  # 字符多样性
            features.append(text.count('。') / max(len(text) / 100, 1))  # 句子密度
        else:
            features.extend([0.0, 0.0])
        
        return features
    
    def get_available_actions(self) -> List[str]:
        """
        获取当前可用的动作列表
        
        Returns:
            可用动作列表
        """
        actions = ["generate", "keep"]
        
        if self.current_text:
            actions.extend(["revise", "delete"])
        
        return actions
    
    def render(self) -> str:
        """
        渲染当前环境状态
        
        Returns:
            可视化字符串
        """
        output = []
        output.append("=" * 50)
        output.append(f"Step: {self.episode_step}/{self.max_steps}")
        output.append(f"Prompt: {self.prompt}")
        output.append("-" * 50)
        output.append(f"Current Text:\n{self.current_text[:200]}...")
        output.append("-" * 50)
        output.append(f"History: {len(self.history)} actions")
        output.append("=" * 50)
        
        return "\n".join(output)
