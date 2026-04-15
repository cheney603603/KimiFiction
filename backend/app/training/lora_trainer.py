"""
LoRA (Low-Rank Adaptation) 训练器

在消费级显卡上高效微调大模型的参数高效方法。
只训练低秩矩阵，大幅减少可训练参数数量。

适用于Qwen3.5-2B等模型的微调。
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger


@dataclass
class LoRAConfig:
    """LoRA配置"""
    
    # 低秩参数
    r: int = 8                    # 低秩维度
    lora_alpha: int = 16          # 缩放参数
    lora_dropout: float = 0.05    # dropout率
    
    # 训练参数
    learning_rate: float = 2e-4
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    warmup_steps: int = 100
    max_seq_length: int = 2048
    
    # 目标模块
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])
    
    # 保存配置
    save_steps: int = 100
    logging_steps: int = 10
    output_dir: str = "./lora_adapters"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "r": self.r,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "learning_rate": self.learning_rate,
            "num_epochs": self.num_epochs,
            "batch_size": self.batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "warmup_steps": self.warmup_steps,
            "max_seq_length": self.max_seq_length,
            "target_modules": self.target_modules,
        }


@dataclass
class TrainingSample:
    """训练样本"""
    prompt: str
    completion: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class LoRATrainer:
    """
    LoRA训练器
    
    支持Qwen3.5-2B等模型的LoRA微调
    """
    
    def __init__(
        self,
        model_path: str,
        config: Optional[LoRAConfig] = None,
    ):
        self.model_path = model_path
        self.config = config or LoRAConfig()
        
        # 模型和分词器（懒加载）
        self._model = None
        self._tokenizer = None
        self._peft_model = None
        
        # 训练状态
        self.training_samples: List[TrainingSample] = []
        self.current_epoch = 0
        self.global_step = 0
        
        logger.info(f"[LoRATrainer] 初始化: model_path={model_path}")
    
    def _load_model(self):
        """加载基础模型和分词器"""
        if self._model is not None:
            return
        
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            logger.info(f"[LoRATrainer] 加载模型: {self.model_path}")
            
            # 加载分词器
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True
            )
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token
            
            # 加载模型（使用4bit量化节省显存）
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                load_in_4bit=True,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype="auto",
            )
            
            # 准备LoRA
            self._setup_lora()
            
            logger.info("[LoRATrainer] 模型加载完成")
            
        except ImportError as e:
            logger.error(f"[LoRATrainer] 依赖缺失: {e}")
            logger.error("请安装: pip install transformers peft bitsandbytes accelerate")
            raise
        except Exception as e:
            logger.error(f"[LoRATrainer] 模型加载失败: {e}")
            raise
    
    def _setup_lora(self):
        """设置LoRA适配器"""
        try:
            from peft import get_peft_model, LoraConfig, TaskType
            
            lora_config = LoraConfig(
                r=self.config.r,
                lora_alpha=self.config.lora_alpha,
                target_modules=self.config.target_modules,
                lora_dropout=self.config.lora_dropout,
                bias="none",
                task_type=TaskType.CAUSAL_LM,
            )
            
            self._peft_model = get_peft_model(self._model, lora_config)
            
            # 打印可训练参数信息
            self._peft_model.print_trainable_parameters()
            
            logger.info(f"[LoRATrainer] LoRA配置完成: r={self.config.r}, alpha={self.config.lora_alpha}")
            
        except Exception as e:
            logger.error(f"[LoRATrainer] LoRA设置失败: {e}")
            raise
    
    def add_training_sample(
        self,
        prompt: str,
        completion: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """添加训练样本"""
        sample = TrainingSample(
            prompt=prompt,
            completion=completion,
            metadata=metadata or {}
        )
        self.training_samples.append(sample)
        logger.debug(f"[LoRATrainer] 添加训练样本，当前共{len(self.training_samples)}条")
    
    def add_samples_from_dicts(self, samples: List[Dict[str, str]]):
        """从字典列表添加样本"""
        for sample in samples:
            self.add_training_sample(
                prompt=sample.get("prompt", ""),
                completion=sample.get("completion", ""),
                metadata=sample.get("metadata", {})
            )
    
    def _format_training_data(self) -> List[Dict[str, str]]:
        """格式化训练数据为对话格式"""
        formatted = []
        for sample in self.training_samples:
            # 构建对话格式
            messages = [
                {"role": "system", "content": "你是一个专业的小说写作助手。"},
                {"role": "user", "content": sample.prompt},
                {"role": "assistant", "content": sample.completion}
            ]
            
            # 使用分词器格式化
            if self._tokenizer:
                text = self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=False
                )
            else:
                text = f"{sample.prompt}\n\n{sample.completion}"
            
            formatted.append({"text": text})
        
        return formatted
    
    async def train(self) -> Dict[str, Any]:
        """
        执行LoRA训练
        
        Returns:
            训练统计信息
        """
        if len(self.training_samples) < 10:
            return {
                "status": "error",
                "message": f"训练样本不足: {len(self.training_samples)} < 10"
            }
        
        self._load_model()
        
        try:
            from datasets import Dataset
            from transformers import TrainingArguments, Trainer, DataCollatorForLanguageModeling
            
            # 准备数据集
            formatted_data = self._format_training_data()
            dataset = Dataset.from_list(formatted_data)
            
            # 分词
            def tokenize_function(examples):
                return self._tokenizer(
                    examples["text"],
                    truncation=True,
                    max_length=self.config.max_seq_length,
                    padding="max_length"
                )
            
            tokenized_dataset = dataset.map(
                tokenize_function,
                batched=True,
                remove_columns=["text"]
            )
            
            # 训练参数
            training_args = TrainingArguments(
                output_dir=self.config.output_dir,
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                warmup_steps=self.config.warmup_steps,
                learning_rate=self.config.learning_rate,
                logging_steps=self.config.logging_steps,
                save_steps=self.config.save_steps,
                save_total_limit=3,
                fp16=True,
                gradient_checkpointing=True,
                optim="paged_adamw_8bit",
                report_to="none",
            )
            
            # 数据整理器
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=self._tokenizer,
                mlm=False
            )
            
            # 创建训练器
            trainer = Trainer(
                model=self._peft_model,
                args=training_args,
                train_dataset=tokenized_dataset,
                data_collator=data_collator,
            )
            
            logger.info("[LoRATrainer] 开始训练...")
            
            # 训练
            train_result = trainer.train()
            
            # 保存最终模型
            final_output_dir = os.path.join(self.config.output_dir, "final")
            trainer.save_model(final_output_dir)
            
            # 保存训练统计
            stats = {
                "status": "success",
                "train_runtime": train_result.metrics.get("train_runtime", 0),
                "train_samples_per_second": train_result.metrics.get("train_samples_per_second", 0),
                "total_flos": train_result.metrics.get("total_flos", 0),
                "final_loss": train_result.metrics.get("train_loss", 0),
                "num_samples": len(self.training_samples),
                "output_dir": final_output_dir,
            }
            
            # 保存统计信息
            stats_path = os.path.join(final_output_dir, "training_stats.json")
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[LoRATrainer] 训练完成: {stats}")
            
            return stats
            
        except Exception as e:
            logger.error(f"[LoRATrainer] 训练失败: {e}")
            return {"status": "error", "message": str(e)}
    
    def save_adapter(self, path: str):
        """保存LoRA适配器"""
        if self._peft_model is None:
            logger.error("[LoRATrainer] 模型未加载")
            return
        
        os.makedirs(path, exist_ok=True)
        self._peft_model.save_pretrained(path)
        
        # 保存配置
        config_path = os.path.join(path, "lora_config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"[LoRATrainer] 适配器已保存: {path}")
    
    def load_adapter(self, path: str):
        """加载LoRA适配器"""
        if self._model is None:
            self._load_model()
        
        try:
            from peft import PeftModel
            
            self._peft_model = PeftModel.from_pretrained(self._model, path)
            
            # 加载配置
            config_path = os.path.join(path, "lora_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_dict = json.load(f)
                    self.config = LoRAConfig(**config_dict)
            
            logger.info(f"[LoRATrainer] 适配器已加载: {path}")
            
        except Exception as e:
            logger.error(f"[LoRATrainer] 加载适配器失败: {e}")
            raise
    
    def merge_and_save(self, output_path: str):
        """
        合并LoRA权重到基础模型并保存
        
        用于部署时减少推理开销
        """
        if self._peft_model is None:
            logger.error("[LoRATrainer] 模型未加载")
            return
        
        logger.info("[LoRATrainer] 合并LoRA权重...")
        
        # 合并权重
        merged_model = self._peft_model.merge_and_unload()
        
        # 保存
        merged_model.save_pretrained(output_path)
        self._tokenizer.save_pretrained(output_path)
        
        logger.info(f"[LoRATrainer] 合并模型已保存: {output_path}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        info = {
            "base_model": self.model_path,
            "config": self.config.to_dict(),
            "training_samples": len(self.training_samples),
            "current_epoch": self.current_epoch,
            "global_step": self.global_step,
        }
        
        if self._peft_model:
            info["trainable_parameters"] = self._peft_model.print_trainable_parameters()
        
        return info


class LLamaCppLoRATrainer:
    """
    基于llama.cpp的LoRA训练器
    
    用于直接训练GGUF格式的Qwen模型
    """
    
    def __init__(
        self,
        model_path: str,
        config: Optional[LoRAConfig] = None,
    ):
        self.model_path = model_path
        self.config = config or LoRAConfig()
        self.training_samples: List[TrainingSample] = []
        
        logger.info(f"[LLamaCppLoRATrainer] 初始化: model_path={model_path}")
    
    def add_training_sample(self, prompt: str, completion: str, metadata: Optional[Dict] = None):
        """添加训练样本"""
        self.training_samples.append(TrainingSample(
            prompt=prompt,
            completion=completion,
            metadata=metadata or {}
        ))
    
    def _prepare_training_file(self, output_path: str):
        """准备训练文件（llama.cpp格式）"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in self.training_samples:
                # llama.cpp格式: 每条样本一行JSON
                data = {
                    "prompt": sample.prompt,
                    "completion": sample.completion
                }
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        
        logger.info(f"[LLamaCppLoRATrainer] 训练文件已准备: {output_path}")
    
    async def train(self) -> Dict[str, Any]:
        """
        使用llama.cpp进行LoRA训练
        
        注意：需要系统安装llama.cpp并编译
        """
        if len(self.training_samples) < 10:
            return {"status": "error", "message": "训练样本不足"}
        
        try:
            import subprocess
            
            # 准备训练文件
            train_file = os.path.join(self.config.output_dir, "train_data.jsonl")
            os.makedirs(self.config.output_dir, exist_ok=True)
            self._prepare_training_file(train_file)
            
            # 构建训练命令
            cmd = [
                "./llama.cpp/lora-finetune",
                "--model", self.model_path,
                "--train-data", train_file,
                "--lora-out", os.path.join(self.config.output_dir, "adapter.bin"),
                "--epochs", str(self.config.num_epochs),
                "--batch", str(self.config.batch_size),
                "--learning-rate", str(self.config.learning_rate),
                "--rank", str(self.config.r),
                "--alpha", str(self.config.lora_alpha),
            ]
            
            logger.info(f"[LLamaCppLoRATrainer] 执行训练: {' '.join(cmd)}")
            
            # 执行训练
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            return {
                "status": "success",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "adapter_path": os.path.join(self.config.output_dir, "adapter.bin"),
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"[LLamaCppLoRATrainer] 训练失败: {e}")
            return {
                "status": "error",
                "message": str(e),
                "stdout": e.stdout if hasattr(e, 'stdout') else "",
                "stderr": e.stderr if hasattr(e, 'stderr') else "",
            }
        except Exception as e:
            logger.error(f"[LLamaCppLoRATrainer] 训练失败: {e}")
            return {"status": "error", "message": str(e)}
