"""
LoRA工具模块
提供LoRA适配器的应用、合并和准备功能
"""
import torch
from peft import LoraConfig, get_peft_model, PeftModel
from transformers import PreTrainedModel

from .config import RLTrainingConfig


def apply_lora_to_model(model: PreTrainedModel, config: RLTrainingConfig) -> PeftModel:
    """
    给模型应用LoRA适配器
    
    Args:
        model: 基础模型
        config: 训练配置
        
    Returns:
        应用了LoRA的模型
    """
    lora_config = LoraConfig(
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        target_modules=config.lora_target_modules,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    lora_model = get_peft_model(model, lora_config)
    
    # 打印可训练参数信息
    trainable_params = sum(p.numel() for p in lora_model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in lora_model.parameters())
    print(f"LoRA应用完成:")
    print(f"  可训练参数: {trainable_params:,} ({100 * trainable_params / total_params:.2f}%)")
    print(f"  总参数: {total_params:,}")
    
    return lora_model


def merge_lora_weights(model: PeftModel) -> PreTrainedModel:
    """
    合并LoRA权重到主模型
    
    合并后可以直接使用基础模型进行推理，
    无需加载LoRA适配器。
    
    Args:
        model: LoRA模型
        
    Returns:
        合并后的基础模型
    """
    print("正在合并LoRA权重到主模型...")
    merged_model = model.merge_and_unload()
    print("LoRA权重合并完成")
    return merged_model


def prepare_lora_model(model: PreTrainedModel, config: RLTrainingConfig) -> PeftModel:
    """
    从头准备LoRA模型
    
    这是主要入口函数，包含完整的LoRA准备流程：
    1. 配置LoRA参数
    2. 应用LoRA到模型
    3. 启用梯度检查点（节省显存）
    
    Args:
        model: 基础模型
        config: 训练配置
        
    Returns:
        准备好的LoRA模型
    """
    # 应用LoRA
    lora_model = apply_lora_to_model(model, config)
    
    # 启用梯度检查点以节省显存
    if hasattr(lora_model, 'gradient_checkpointing_enable'):
        lora_model.gradient_checkpointing_enable()
        print("已启用梯度检查点")
    
    # 准备模型进行训练
    if hasattr(lora_model, 'enable_input_require_grads'):
        lora_model.enable_input_require_grads()
    
    return lora_model


def get_lora_state_dict(model: PeftModel) -> dict:
    """
    获取LoRA状态字典（仅包含可训练参数）
    
    用于保存和加载LoRA权重
    """
    return {k: v for k, v in model.state_dict().items() if "lora" in k}


def print_trainable_parameters(model: torch.nn.Module):
    """
    打印模型的可训练参数信息
    """
    trainable_params = 0
    all_params = 0
    
    for _, param in model.named_parameters():
        all_params += param.numel()
        if param.requires_grad:
            trainable_params += param.numel()
    
    print(f"可训练参数: {trainable_params:,} || "
          f"总参数: {all_params:,} || "
          f"可训练比例: {100 * trainable_params / all_params:.2f}%")
