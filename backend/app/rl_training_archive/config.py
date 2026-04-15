"""
RL训练配置模块
针对8GB显存优化的训练配置
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class RLTrainingConfig:
    """
    RL训练配置类
    
    针对NVIDIA RTX 4070 Laptop GPU (8GB显存)优化：
    - 使用4bit量化加载模型
    - batch_size=1配合gradient_accumulation_steps=8
    - 序列长度限制2048 tokens
    """
    
    # 模型配置 - 8GB显存限定
    model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"  # 最佳选择，~3GB
    # 备选: "Qwen/Qwen2.5-0.5B-Instruct" (~1.1GB), "microsoft/Phi-3.5-mini-instruct" (~2GB)
    
    # LoRA配置
    lora_rank: int = 8          # LoRA rank，8GB显存可开到16
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    lora_target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"
    ])
    
    # GRPO配置
    grpo_group_size: int = 4    # 每组样本数
    grpo_num_groups: int = 8    # 组数
    grpo_lr: float = 1e-4
    grpo_clip_ratio: float = 0.2
    grpo_entropy_coef: float = 0.01
    gamma: float = 0.99
    
    # TPO配置（推理时优化）
    tpo_temperature: float = 1.0
    tpo_num_samples: int = 8
    tpo_top_p: float = 0.9
    
    # 训练参数
    max_seq_len: int = 2048     # 8GB显存最大序列长度
    batch_size: int = 1         # 显存限制
    gradient_accumulation: int = 8  # 等效batch_size=8
    learning_rate: float = 1e-4
    num_epochs: int = 3
    warmup_steps: int = 10
    
    # 生成参数
    max_new_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    
    # 存储 - 使用正斜杠确保Windows兼容性
    output_dir: str = "D:/310Programm/KimiFiction/test_project/rl_models"
    checkpoint_dir: str = "D:/310Programm/KimiFiction/test_project/rl_checkpoints"
    data_dir: str = "D:/310Programm/KimiFiction/test_project/training_data"
    
    # 量化配置
    use_4bit: bool = True
    bnb_4bit_compute_dtype: str = "float16"
    bnb_4bit_use_double_quant: bool = True
    bnb_4bit_quant_type: str = "nf4"
    
    # 优化器配置
    optimizer_type: str = "adamw_torch"
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0
    
    # 日志配置
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 50
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            k: v for k, v in self.__dict__.items()
        }
