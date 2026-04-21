"""
RL 训练系统 - 统一入口（兼容层）
================================

本模块是 app/training/ 的重导出层，保持向后兼容。

推荐导入路径（新）：
    from app.training import GRPOTrainer, LoRATrainer, ImitationLearning
    from app.training.hardware_config import RTX4070Config, get_recommended_config

兼容导入路径（旧）：
    from app.rl_training import GRPOTrainer, RLTrainingConfig
"""

# 重导出 training 模块的所有内容
from app.training import (
    # GRPO
    GRPOTrainer,
    GRPOConfig,
    GRPOPolicy,
    RewardFunction,
    GroupRewardNormalizer,
    WritingAction,
    Episode,
    # LoRA
    LoRATrainer,
    LoRAConfig,
    # 模仿学习
    ImitationLearning,
    # TPO
    TPOService,
    RewardModel,
    TestTimeRL,
    # Pipeline
    TrainingPipeline,
    TrainingPipelineResult,
    TrainingStageResult,
)

# 硬件配置
from app.training.hardware_config import (
    RTX4070Config,
    RLTrainingConfig,  # 向后兼容别名
    CPUOnlyConfig,
    get_recommended_config,
)

__all__ = [
    # GRPO 核心
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
    # 硬件配置
    "RTX4070Config",
    "RLTrainingConfig",
    "CPUOnlyConfig",
    "get_recommended_config",
]
