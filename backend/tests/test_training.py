"""
Training 模块单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHardwareConfig:
    """硬件配置测试"""
    
    def test_import_configs(self):
        """测试导入配置类"""
        from app.training import (
            RTX4070Config,
            RLTrainingConfig,
            CPUOnlyConfig,
            get_recommended_config,
        )
        
        assert RTX4070Config is not None
        assert RLTrainingConfig is not None
        assert CPUOnlyConfig is not None
    
    def test_rtx4070_config_defaults(self):
        """测试 RTX 4070 配置默认值"""
        from app.training import RTX4070Config
        
        config = RTX4070Config()
        
        assert config.lora_rank == 8
        assert config.lora_alpha == 16
        assert config.use_4bit == True
        assert config.batch_size == 1
        assert config.gradient_accumulation == 8
        assert config.max_seq_len == 2048
    
    def test_config_to_dict(self):
        """测试配置转字典"""
        from app.training import RTX4070Config
        
        config = RTX4070Config()
        d = config.to_dict()
        
        assert isinstance(d, dict)
        assert "lora_rank" in d
        assert "model_name" in d
    
    def test_config_summary(self):
        """测试配置摘要"""
        from app.training import RTX4070Config
        
        config = RTX4070Config()
        summary = config.summary()
        
        assert isinstance(summary, str)
        assert "RTX 4070" in summary
        assert "显存" in summary
    
    def test_rlx_training_config_alias(self):
        """测试向后兼容别名"""
        from app.training import RLTrainingConfig, RTX4070Config
        
        # RLTrainingConfig 应该是 RTX4070Config 的别名
        assert RLTrainingConfig is RTX4070Config
    
    def test_cpu_only_config(self):
        """测试 CPU-only 配置"""
        from app.training import CPUOnlyConfig
        
        config = CPUOnlyConfig()
        
        assert config.use_4bit == False  # CPU不支持4bit
        assert config.lora_rank == 4  # 更小的rank
    
    def test_get_recommended_config(self):
        """测试自动推荐配置"""
        from app.training import get_recommended_config, RTX4070Config, CPUOnlyConfig
        
        # 8GB+ GPU
        config_8gb = get_recommended_config(8)
        assert isinstance(config_8gb, RTX4070Config)
        
        # CPU-only
        config_cpu = get_recommended_config(0)
        assert isinstance(config_cpu, CPUOnlyConfig)


class TestTrainingImports:
    """训练模块导入测试"""
    
    def test_import_grpo(self):
        """测试导入 GRPO 相关类"""
        from app.training import (
            GRPOTrainer,
            GRPOConfig,
            GRPOPolicy,
            RewardFunction,
            WritingAction,
            Episode,
        )
        
        assert GRPOTrainer is not None
        assert GRPOConfig is not None
        assert WritingAction is not None
    
    def test_import_lora(self):
        """测试导入 LoRA 相关类"""
        from app.training import LoRATrainer, LoRAConfig
        
        assert LoRATrainer is not None
        assert LoRAConfig is not None
    
    def test_import_tpo(self):
        """测试导入 TPO 相关类"""
        from app.training import TPOService, RewardModel, TestTimeRL
        
        assert TPOService is not None
        assert RewardModel is not None
    
    def test_import_imitation_learning(self):
        """测试导入模仿学习"""
        from app.training import ImitationLearning
        
        assert ImitationLearning is not None
    
    def test_import_pipeline(self):
        """测试导入训练管道"""
        from app.training import (
            TrainingPipeline,
            TrainingPipelineResult,
            TrainingStageResult,
        )
        
        assert TrainingPipeline is not None


class TestRLTrainingCompat:
    """rl_training 兼容层测试"""
    
    def test_import_from_rl_training(self):
        """测试从 rl_training 导入（向后兼容）"""
        from app.rl_training import (
            GRPOTrainer,
            LoRATrainer,
            RTX4070Config,
            RLTrainingConfig,
        )
        
        assert GRPOTrainer is not None
        assert LoRATrainer is not None
        assert RTX4070Config is not None
    
    def test_rl_training_reexports(self):
        """测试 rl_training 重导出与 training 一致"""
        from app.rl_training import GRPOTrainer as RL_GRPO
        from app.training import GRPOTrainer as Train_GRPO
        
        assert RL_GRPO is Train_GRPO
