"""
数据管道模块

RL训练数据管道
从 training_data/ 目录读取采集的episode数据，
构建GRPO/TPO训练所需的格式。
"""
import json
import os
from typing import List, Dict, Tuple, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Episode:
    """
    训练Episode数据结构
    
    包含：
    - prompt: 输入提示
    - responses: 生成的回复列表
    - rewards: 对应的奖励列表
    - metadata: 元数据（如章节ID、时间戳等）
    """
    prompt: str
    responses: List[str]
    rewards: List[float]
    metadata: Dict[str, Any] = None
    episode_id: str = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RLDataPipeline:
    """
    RL训练数据管道
    
    负责：
    - 从JSON文件加载训练episode
    - 构建GRPO训练数据格式
    - 创建偏好对（用于DPO/TPO）
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def load_episodes(self, batch_name: str = "latest") -> List[Episode]:
        """
        从JSON文件加载训练episode
        
        Args:
            batch_name: 批次名称或"latest"获取最新批次
            
        Returns:
            Episode列表
        """
        if batch_name == "latest":
            # 查找最新的批次文件
            batch_files = list(self.data_dir.glob("batch_*.json"))
            if not batch_files:
                print(f"警告: 在 {self.data_dir} 中没有找到批次文件")
                return []
            latest_file = max(batch_files, key=lambda p: p.stat().st_mtime)
            file_path = latest_file
        else:
            file_path = self.data_dir / f"{batch_name}.json"
        
        if not file_path.exists():
            print(f"警告: 文件不存在 {file_path}")
            return []
        
        print(f"加载数据: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        episodes = []
        for item in data.get("episodes", []):
            episode = Episode(
                prompt=item.get("prompt", ""),
                responses=item.get("responses", []),
                rewards=item.get("rewards", []),
                metadata=item.get("metadata", {}),
                episode_id=item.get("episode_id")
            )
            episodes.append(episode)
        
        print(f"加载了 {len(episodes)} 个episodes")
        return episodes
    
    def build_grpo_data(self, episodes: List[Episode]) -> Dict[str, List]:
        """
        构建GRPO训练数据
        
        GRPO需要：
        - prompts: 输入提示列表
        - responses: 生成的回复列表
        - rewards: 奖励列表
        - groups: 分组索引（每个prompt对应多个response）
        
        Returns:
            {
                "prompts": [...],      # 输入提示
                "responses": [...],    # 生成的回复
                "rewards": [...],      # 奖励
                "groups": [...]        # 分组索引
            }
        """
        prompts = []
        responses = []
        rewards = []
        groups = []
        
        for episode in episodes:
            group_start = len(prompts)
            
            # 每个episode的responses形成一个组
            for resp, reward in zip(episode.responses, episode.rewards):
                prompts.append(episode.prompt)
                responses.append(resp)
                rewards.append(reward)
            
            group_end = len(prompts)
            groups.append((group_start, group_end))
        
        return {
            "prompts": prompts,
            "responses": responses,
            "rewards": rewards,
            "groups": groups
        }
    
    def create_preference_pairs(self, episodes: List[Episode]) -> List[Tuple]:
        """
        创建偏好对（用于DPO/TPO）
        
        每个样本生成多个回复，选出最优和最差的作为pair。
        
        Returns:
            [(prompt, chosen, rejected, metadata), ...]
        """
        pairs = []
        
        for episode in episodes:
            if len(episode.responses) < 2 or len(episode.rewards) < 2:
                continue
            
            # 找出最优和最差的回复
            rewards_array = episode.rewards
            best_idx = rewards_array.index(max(rewards_array))
            worst_idx = rewards_array.index(min(rewards_array))
            
            # 确保最优和最差不是同一个
            if best_idx != worst_idx:
                pair = (
                    episode.prompt,
                    episode.responses[best_idx],
                    episode.responses[worst_idx],
                    episode.metadata
                )
                pairs.append(pair)
        
        print(f"创建了 {len(pairs)} 个偏好对")
        return pairs
    
    def save_episodes(self, episodes: List[Episode], batch_name: str):
        """
        保存episodes到JSON文件
        
        Args:
            episodes: Episode列表
            batch_name: 批次名称
        """
        file_path = self.data_dir / f"{batch_name}.json"
        
        data = {
            "batch_name": batch_name,
            "episodes": []
        }
        
        for ep in episodes:
            data["episodes"].append({
                "episode_id": ep.episode_id,
                "prompt": ep.prompt,
                "responses": ep.responses,
                "rewards": ep.rewards,
                "metadata": ep.metadata
            })
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"保存了 {len(episodes)} 个episodes到 {file_path}")
    
    def create_synthetic_episodes(
        self, 
        num_episodes: int = 10,
        group_size: int = 4
    ) -> List[Episode]:
        """
        创建合成episode数据（用于测试）
        
        Args:
            num_episodes: episode数量
            group_size: 每组response数量
            
        Returns:
            Episode列表
        """
        episodes = []
        
        sample_prompts = [
            "写一个关于勇气的故事开头",
            "描述一个雨夜的场景",
            "写一段人物对话",
            "描述一个神秘的房间",
            "写一个意想不到的结局"
        ]
        
        for i in range(num_episodes):
            prompt = sample_prompts[i % len(sample_prompts)]
            
            # 生成模拟的responses和rewards
            responses = [f"这是第{j+1}个回复示例..." for j in range(group_size)]
            rewards = [0.5 + (j * 0.1) for j in range(group_size)]
            
            episode = Episode(
                prompt=prompt,
                responses=responses,
                rewards=rewards,
                episode_id=f"synthetic_{i}",
                metadata={"source": "synthetic", "index": i}
            )
            episodes.append(episode)
        
        return episodes
    
    def get_statistics(self, episodes: List[Episode]) -> Dict:
        """
        获取数据集的统计信息
        
        Returns:
            统计信息字典
        """
        if not episodes:
            return {}
        
        total_responses = sum(len(ep.responses) for ep in episodes)
        all_rewards = [r for ep in episodes for r in ep.rewards]
        
        return {
            "num_episodes": len(episodes),
            "total_responses": total_responses,
            "avg_responses_per_episode": total_responses / len(episodes),
            "reward_mean": sum(all_rewards) / len(all_rewards) if all_rewards else 0,
            "reward_min": min(all_rewards) if all_rewards else 0,
            "reward_max": max(all_rewards) if all_rewards else 0,
        }
