"""
RL 训练系统 - 统一入口
========================
本模块整合了两套实现：
- app/training/   → 完整 GRPO 算法（Policy/Episode 架构，推荐使用）
- rl_training_archive/ → RTX 4070 硬件优化配置（旧版，保留兼容）

推荐导入路径：
    from app.rl_training import GRPOTrainer, RLTrainingConfig, RLWritingModel

向后兼容（旧路径仍可用）：
    from app.rl_training import GRPOTrainer as OldGRPOTrainer  # 来自 rl_training_archive
"""

# ============================================================
# 优先使用 app/training/ 中的完整实现
# ============================================================
from app.training.grpo_trainer import (
    GRPOTrainer as _CanonicalGRPOTrainer,
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
from app.training.tpo_service import (
    TPOService,
    RewardModel,
    TestTimeRL,
)
from app.training.imitation_learning import ImitationLearning

# 主入口：使用 app/training 中的完整实现
GRPOTrainer = _CanonicalGRPOTrainer

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
    # TPO
    "TPOService",
    "RewardModel",
    "TestTimeRL",
    # 模仿学习
    "ImitationLearning",
]

# ============================================================
# RTX 4070 硬件优化配置
# 使用方式：from app.rl_training.config import RLTrainingConfig
# ============================================================
