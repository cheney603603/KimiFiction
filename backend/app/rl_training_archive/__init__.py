"""
RL训练系统 - 主模块

提供强化学习在LLM写作上的应用：
- GRPO (Group Relative Policy Optimization): 组相对策略优化
- TPO (Test-time Preference Optimization): 测试时偏好优化
- LoRA: 低秩适配器高效微调

硬件要求：
- 最低: 8GB显存（使用4bit量化）
- 推荐: NVIDIA RTX 4070或更高

使用示例：
    from app.rl_training import RLWritingModel, GRPOTrainer, RLTrainingConfig
    
    config = RLTrainingConfig()
    model = RLWritingModel(config)
    await model.load()
    
    trainer = GRPOTrainer(model, config)
    await trainer.train(episodes, epochs=3)
"""

from .config import RLTrainingConfig
from .models import RLWritingModel
from .grpo_trainer import GRPOTrainer
from .tpo_trainer import TPOTrainer
from .lora_utils import (
    apply_lora_to_model,
    merge_lora_weights,
    prepare_lora_model
)
from .data_pipeline import RLDataPipeline, Episode
from .inference_engine import RLInferenceEngine
from .rl_env import WritingRLEnv

__version__ = "1.0.0"
__all__ = [
    "RLTrainingConfig",
    "RLWritingModel", 
    "GRPOTrainer",
    "TPOTrainer",
    "apply_lora_to_model",
    "merge_lora_weights",
    "prepare_lora_model",
    "RLDataPipeline",
    "Episode",
    "RLInferenceEngine",
    "WritingRLEnv",
]
