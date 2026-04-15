"""
LoRA 工具函数 - 兼容层
=========================

从 rl_training_archive/lora_utils.py 迁移。
主实现在 app/training/lora_trainer.py 中。

RTX 4070 优化用法：
    from app.rl_training.models import LoRATrainer
    trainer = LoRATrainer(model_path="Qwen/Qwen2.5-1.5B-Instruct", ...)
"""

# 重导出主实现
from app.training.lora_trainer import LoRATrainer, LoRAConfig

__all__ = ["LoRATrainer", "LoRAConfig"]
