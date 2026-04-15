"""
模型定义模块
RL写作模型封装，支持4bit量化和LoRA
"""
import asyncio
import torch
from typing import Optional, Dict, Any
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer,
    BitsAndBytesConfig
)
from peft import PeftModel

from .config import RLTrainingConfig
from .lora_utils import prepare_lora_model


class RLWritingModel:
    """
    RL写作模型封装
    
    功能：
    - 使用transformers加载模型和分词器
    - 支持4bit量化（bitsandbytes）
    - 支持LoRA适配器
    - 提供同步和异步生成接口
    """
    
    def __init__(self, config: RLTrainingConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.lora_model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
    
    async def load(self):
        """
        加载模型和分词器（使用transformers）
        
        加载流程：
        1. 加载tokenizer
        2. 配置4bit量化（如果启用）
        3. 加载基础模型
        4. 应用LoRA适配器
        """
        print(f"正在加载模型: {self.config.model_name}")
        print(f"使用设备: {self.device}")
        
        # 加载tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            trust_remote_code=True,
            padding_side="left"
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # 配置4bit量化
        quantization_config = None
        if self.config.use_4bit and self.device == "cuda":
            print("启用4bit量化以节省显存")
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=getattr(torch, self.config.bnb_4bit_compute_dtype),
                bnb_4bit_use_double_quant=self.config.bnb_4bit_use_double_quant,
                bnb_4bit_quant_type=self.config.bnb_4bit_quant_type
            )
        
        # 加载基础模型
        load_kwargs = {
            "pretrained_model_name_or_path": self.config.model_name,
            "trust_remote_code": True,
            "torch_dtype": torch.float16 if self.device == "cuda" else torch.float32,
            "device_map": "auto" if self.device == "cuda" else None,
        }
        if quantization_config:
            load_kwargs["quantization_config"] = quantization_config
        
        self.model = AutoModelForCausalLM.from_pretrained(**load_kwargs)
        
        # 应用LoRA
        self.lora_model = prepare_lora_model(self.model, self.config)
        
        print("模型加载完成!")
        
        # 打印显存使用情况
        if self.device == "cuda":
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            print(f"显存使用: {allocated:.2f}GB / {reserved:.2f}GB")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """
        同步生成文本
        
        Args:
            prompt: 输入提示词
            **kwargs: 生成参数覆盖
            
        Returns:
            生成的文本
        """
        if self.lora_model is None:
            raise RuntimeError("模型未加载，请先调用load()")
        
        # 合并默认参数和用户参数
        gen_kwargs = {
            "max_new_tokens": self.config.max_new_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "do_sample": True,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        gen_kwargs.update(kwargs)
        
        # 编码输入
        inputs = self.tokenizer(
            prompt, 
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_seq_len
        ).to(self.device)
        
        # 生成
        with torch.no_grad():
            outputs = self.lora_model.generate(
                **inputs,
                **gen_kwargs
            )
        
        # 解码输出
        generated_text = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:],
            skip_special_tokens=True
        )
        
        return generated_text
    
    async def generate_async(self, prompt: str, **kwargs) -> str:
        """
        异步生成文本
        
        在事件循环中执行同步生成
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.generate(prompt, **kwargs))
    
    def generate_batch(self, prompts: list, **kwargs) -> list:
        """
        批量生成文本
        
        Args:
            prompts: 输入提示词列表
            **kwargs: 生成参数
            
        Returns:
            生成的文本列表
        """
        if self.lora_model is None:
            raise RuntimeError("模型未加载，请先调用load()")
        
        gen_kwargs = {
            "max_new_tokens": self.config.max_new_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "do_sample": True,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        gen_kwargs.update(kwargs)
        
        # 批量编码
        inputs = self.tokenizer(
            prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.config.max_seq_len
        ).to(self.device)
        
        # 批量生成
        with torch.no_grad():
            outputs = self.lora_model.generate(
                **inputs,
                **gen_kwargs
            )
        
        # 解码输出
        results = []
        for i, output in enumerate(outputs):
            input_len = inputs['input_ids'][i].shape[0]
            generated = self.tokenizer.decode(
                output[input_len:],
                skip_special_tokens=True
            )
            results.append(generated)
        
        return results
    
    def save_adapter(self, path: str):
        """
        只保存LoRA适配器权重
        
        比保存完整模型节省大量磁盘空间
        """
        if self.lora_model is None:
            raise RuntimeError("模型未加载")
        
        import os
        os.makedirs(path, exist_ok=True)
        self.lora_model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
        print(f"LoRA适配器已保存到: {path}")
    
    def load_adapter(self, path: str):
        """
        加载LoRA适配器权重
        """
        if self.model is None:
            raise RuntimeError("基础模型未加载")
        
        from peft import PeftModel
        self.lora_model = PeftModel.from_pretrained(self.model, path)
        print(f"LoRA适配器已加载: {path}")
    
    def get_trainable_params(self) -> int:
        """获取可训练参数数量"""
        if self.lora_model is None:
            return 0
        return sum(p.numel() for p in self.lora_model.parameters() if p.requires_grad)
    
    def get_total_params(self) -> int:
        """获取总参数数量"""
        if self.model is None:
            return 0
        return sum(p.numel() for p in self.model.parameters())
