"""
RL 写作模型封装 - 兼容层
=========================

从 rl_training_archive/models.py 迁移并重构。
主要使用 app/training/lora_trainer.py 中的 LoRATrainer。

如需 RTX 4070 优化的模型加载，请使用：
    from app.training.lora_trainer import LoRATrainer, LoRAConfig
"""

# 重导出主实现
from app.training.lora_trainer import LoRATrainer, LoRAConfig, TrainingSample

__all__ = [
    "LoRATrainer",
    "LoRAConfig",
    "TrainingSample",
]
