"""
训练模块 - 包含 RL 训练、LoRA 微调、模仿学习等功能
=====================================================

快速开始：
    from app.training import GRPOTrainer, LoRATrainer, ImitationLearning

RTX 4070 (8GB) 优化配置：
    from app.rl_training.config import RLTrainingConfig
    config = RLTrainingConfig()
    config.summary()  # 打印显存占用估算

完整训练 Pipeline：
    from app.training import TrainingPipeline
    result = await TrainingPipeline(novel_id=1, project_path="output")
        .run_full_pipeline(run_grpo=True, run_lora=True)
"""

from app.training.grpo_trainer import (
    GRPOTrainer,
    GRPOConfig,
    GRPOPolicy,
    RewardFunction,
    GroupRewardNormalizer,
    WritingAction,
    Episode,
)
from app.training.lora_trainer import (
    LoRATrainer,
    LoRAConfig,
)
from app.training.imitation_learning import ImitationLearning
from app.training.tpo_service import (
    TPOService,
    RewardModel,
    TestTimeRL,
)
from app.training.training_pipeline import (
    TrainingPipeline,
    TrainingPipelineResult,
    TrainingStageResult,
)

__all__ = [
    # GRPO
    "GRPOTrainer",
    "GRPOConfig",
    "GRPOPolicy",
    "RewardFunction",
    "GroupRewardNormalizer",
    "WritingAction",
    "Episode",
    # LoRA
    "LoRATrainer",
    "LoRAConfig",
    # 模仿学习
    "ImitationLearning",
    # TPO
    "TPOService",
    "RewardModel",
    "TestTimeRL",
    # Pipeline
    "TrainingPipeline",
    "TrainingPipelineResult",
    "TrainingStageResult",
]
