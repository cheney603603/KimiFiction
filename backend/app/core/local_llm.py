"""
本地LLM服务 - 支持Qwen系列模型

使用llama-cpp-python加载本地GGUF格式模型，
支持LoRA适配器加载，适用于消费级显卡。

支持的模型:
- Qwen3.5-2B-Q4_K_M.gguf (1.2GB) - 轻量级，适合快速推理
- Qwen3.5-35B-A3B-UD-Q4_K_XL.gguf (20.7GB) - 高质量，需要更多内存
"""
import os
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger


# 预定义模型配置
PREDEFINED_MODELS = {
    "qwen-2b": {
        "name": "Qwen3.5-2B-Q4_K_M",
        "path": "D:/002 llm ware/models/Qwen3.5-2B-Q4_K_M.gguf",
        "n_ctx": 4096,
        "n_gpu_layers": 0,  # CPU only
        "description": "轻量级模型，适合快速推理",
    },
    "qwen-35b": {
        "name": "Qwen3.5-35B-A3B",
        "path": "D:/002 llm ware/models/Qwen3.5-35B-A3B-UD-Q4_K_XL.gguf",
        "n_ctx": 8192,
        "n_gpu_layers": 0,  # 需要大量GPU内存，默认CPU
        "description": "高质量模型，需要20GB+内存",
    },
}


@dataclass
class LocalLLMConfig:
    """本地LLM配置"""
    model_path: str = "D:/002 llm ware/models/Qwen3.5-2B-Q4_K_M.gguf"
    model_name: str = "qwen-2b"
    n_ctx: int = 4096              # 上下文长度
    n_threads: Optional[int] = None  # 线程数（默认自动）
    n_batch: int = 512            # 批处理大小
    n_gpu_layers: int = 0         # GPU层数（0表示纯CPU）
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    max_tokens: int = 2048
    stop_sequences: Optional[List[str]] = None
    
    # LoRA配置
    lora_path: Optional[str] = None
    lora_scale: float = 1.0


class LocalLLMService:
    """
    本地LLM服务
    
    基于llama-cpp-python封装，支持Qwen系列模型
    """
    
    def __init__(self, config: Optional[LocalLLMConfig] = None):
        self.config = config or LocalLLMConfig()
        self._model = None
        self._loaded = False
        
        logger.info(f"[LocalLLM] 初始化: model_path={self.config.model_path}")
    
    def _load_model(self):
        """懒加载模型"""
        if self._loaded:
            return
        
        try:
            from llama_cpp import Llama
            
            model_path = Path(self.config.model_path)
            if not model_path.exists():
                # 尝试相对路径
                model_path = Path(os.getcwd()) / self.config.model_path
            
            if not model_path.exists():
                raise FileNotFoundError(f"模型文件不存在: {self.config.model_path}")
            
            logger.info(f"[LocalLLM] 正在加载模型: {model_path}")
            
            # 构建加载参数
            load_params = {
                "model_path": str(model_path),
                "n_ctx": self.config.n_ctx,
                "n_batch": self.config.n_batch,
                "verbose": False,
            }
            
            # 线程数
            if self.config.n_threads:
                load_params["n_threads"] = self.config.n_threads
            
            # GPU层数
            if self.config.n_gpu_layers > 0:
                load_params["n_gpu_layers"] = self.config.n_gpu_layers
                logger.info(f"[LocalLLM] 使用GPU加速: {self.config.n_gpu_layers}层")
            
            # 加载模型
            self._model = Llama(**load_params)
            
            # 加载LoRA（如果指定）
            if self.config.lora_path and Path(self.config.lora_path).exists():
                logger.info(f"[LocalLLM] 加载LoRA适配器: {self.config.lora_path}")
                self._model.set_lora(
                    path=self.config.lora_path,
                    scale=self.config.lora_scale
                )
            
            self._loaded = True
            
            # 打印模型信息
            logger.info(f"[LocalLLM] 模型加载完成")
            logger.info(f"[LocalLLM] 上下文长度: {self.config.n_ctx}")
            logger.info(f"[LocalLLM] 词汇表大小: {self._model.n_vocab()}")
            
        except ImportError:
            logger.error("[LocalLLM] llama-cpp-python未安装")
            logger.error("请安装: pip install llama-cpp-python")
            raise
        except Exception as e:
            logger.error(f"[LocalLLM] 模型加载失败: {e}")
            raise
    
    def _format_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        格式化消息为Qwen对话格式
        
        Qwen3.5格式:
        <|im_start|>system
        {system_message}<|im_end|>
        <|im_start|>user
        {user_message}<|im_end|>
        <|im_start|>assistant
        """
        formatted = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                formatted.append(f"<|im_start|>system\n{content}<|im_end|>")
            elif role == "user":
                formatted.append(f"<|im_start|>user\n{content}<|im_end|>")
            elif role == "assistant":
                formatted.append(f"<|im_start|>assistant\n{content}<|im_end|>")
        
        # 添加assistant开始标记
        formatted.append("<|im_start|>assistant\n")
        
        return "\n".join(formatted)
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> str:
        """
        生成文本
        
        Args:
            messages: 消息列表
            temperature: 温度（覆盖配置）
            max_tokens: 最大生成token数
            stream: 是否流式输出
            **kwargs: 其他生成参数
            
        Returns:
            生成的文本
        """
        self._load_model()
        
        # 格式化prompt
        prompt = self._format_prompt(messages)
        
        # 构建生成参数
        gen_params = {
            "temperature": temperature or self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "repeat_penalty": self.config.repeat_penalty,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stop": self.config.stop_sequences or ["<|im_end|>", "<|endoftext|>"],
        }
        
        # 更新额外参数
        gen_params.update(kwargs)
        
        try:
            logger.debug(f"[LocalLLM] 生成: prompt_length={len(prompt)}, max_tokens={gen_params['max_tokens']}")
            
            if stream:
                return self._generate_stream(prompt, gen_params)
            else:
                output = self._model(prompt, **gen_params)
                text = output["choices"][0]["text"]
                
                # 清理特殊token
                text = text.replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
                
                logger.debug(f"[LocalLLM] 生成完成: length={len(text)}")
                return text
                
        except Exception as e:
            logger.error(f"[LocalLLM] 生成失败: {e}")
            raise
    
    def _generate_stream(
        self,
        prompt: str,
        gen_params: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """流式生成"""
        # 简化实现：直接返回完整结果
        # 可以扩展为真正的流式输出
        output = self._model(prompt, **gen_params)
        text = output["choices"][0]["text"]
        text = text.replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
        
        # 按句子分割模拟流式
        sentences = text.split("。")
        for sent in sentences:
            if sent.strip():
                yield sent + "。"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        聊天接口（兼容LLMService）
        
        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 其他参数
            
        Returns:
            回复文本
        """
        return await self.generate(messages, temperature, max_tokens, **kwargs)
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        info = {
            "model_path": self.config.model_path,
            "loaded": self._loaded,
            "config": {
                "n_ctx": self.config.n_ctx,
                "n_threads": self.config.n_threads,
                "n_batch": self.config.n_batch,
                "n_gpu_layers": self.config.n_gpu_layers,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
        }
        
        if self._loaded and self._model:
            info["vocab_size"] = self._model.n_vocab()
            info["context_size"] = self._model.n_ctx()
        
        return info
    
    def reload_with_lora(self, lora_path: str, lora_scale: float = 1.0):
        """
        重新加载模型并应用新的LoRA适配器
        
        Args:
            lora_path: LoRA适配器路径
            lora_scale: LoRA缩放系数
        """
        logger.info(f"[LocalLLM] 重新加载LoRA: {lora_path}, scale={lora_scale}")
        
        self.config.lora_path = lora_path
        self.config.lora_scale = lora_scale
        
        # 重新加载
        self._loaded = False
        self._model = None
        self._load_model()
    
    def unload(self):
        """卸载模型释放内存"""
        if self._model:
            del self._model
            self._model = None
        self._loaded = False
        logger.info("[LocalLLM] 模型已卸载")


# 全局服务实例
_local_llm_service: Optional[LocalLLMService] = None


def get_local_llm_service(
    model_path: Optional[str] = None,
    **kwargs
) -> LocalLLMService:
    """
    获取本地LLM服务实例
    
    Args:
        model_path: 模型路径（可选）
        **kwargs: 其他配置参数
        
    Returns:
        LocalLLMService实例
    """
    global _local_llm_service
    
    if _local_llm_service is None:
        config = LocalLLMConfig(**kwargs)
        if model_path:
            config.model_path = model_path
        _local_llm_service = LocalLLMService(config)
    
    return _local_llm_service


def reset_local_llm_service():
    """重置服务实例"""
    global _local_llm_service
    if _local_llm_service:
        _local_llm_service.unload()
    _local_llm_service = None


# 便捷函数
async def generate_with_local_llm(
    prompt: str,
    system_prompt: str = "你是一个专业的小说写作助手。",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    使用本地LLM生成文本的便捷函数
    
    Args:
        prompt: 用户提示
        system_prompt: 系统提示
        temperature: 温度
        max_tokens: 最大token数
        
    Returns:
        生成的文本
    """
    service = get_local_llm_service()
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    return await service.chat(messages, temperature, max_tokens)


async def check_local_model() -> Dict[str, Any]:
    """检查本地模型状态"""
    try:
        service = get_local_llm_service()
        service._load_model()
        
        return {
            "available": True,
            "info": service.get_model_info()
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }


def list_available_models() -> Dict[str, Dict[str, Any]]:
    """
    列出所有可用的预定义模型
    
    Returns:
        模型配置字典
    """
    available = {}
    
    for model_id, config in PREDEFINED_MODELS.items():
        model_path = Path(config["path"])
        available[model_id] = {
            **config,
            "exists": model_path.exists(),
            "size_gb": model_path.stat().st_size / (1024**3) if model_path.exists() else 0,
        }
    
    return available


def get_model_config(model_id: str) -> Optional[LocalLLMConfig]:
    """
    根据模型ID获取配置
    
    Args:
        model_id: 模型ID (qwen-2b, qwen-35b)
        
    Returns:
        LocalLLMConfig配置对象
    """
    if model_id not in PREDEFINED_MODELS:
        logger.warning(f"未知的模型ID: {model_id}")
        return None
    
    model_info = PREDEFINED_MODELS[model_id]
    
    return LocalLLMConfig(
        model_path=model_info["path"],
        model_name=model_id,
        n_ctx=model_info.get("n_ctx", 4096),
        n_gpu_layers=model_info.get("n_gpu_layers", 0),
    )


def create_local_llm_service(model_id: str = "qwen-2b", **kwargs) -> LocalLLMService:
    """
    根据模型ID创建本地LLM服务
    
    Args:
        model_id: 模型ID (qwen-2b, qwen-35b)
        **kwargs: 额外配置参数
        
    Returns:
        LocalLLMService实例
    """
    config = get_model_config(model_id)
    
    if config is None:
        # 使用默认配置
        config = LocalLLMConfig(**kwargs)
    
    # 应用额外参数
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return LocalLLMService(config)
