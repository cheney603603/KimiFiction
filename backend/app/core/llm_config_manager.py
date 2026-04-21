"""
LLM配置管理器
用于读取前端保存的LLM配置

支持的LLM类型:
1. API调用: openai, deepseek
2. Chat2Api: kimi, yuanbao
3. 本地模型: local_qwen (Qwen3.5-2B/35B)
"""
import json
import os
from typing import Optional, Dict, Any
from loguru import logger

# 全局配置存储（用于存储前端传来的配置）
_global_config: Dict[str, Any] = {}


class LLMConfigManager:
    """
    LLM配置管理器

    读取前端通过API传来的配置
    或者读取环境变量
    """

    @staticmethod
    def get_config() -> Dict[str, Any]:
        """
        获取LLM配置

        优先级别（从高到低）：
        1. 全局配置（前端通过API设置） - 最高优先级
        2. 环境变量 - 仅在全局配置未设置时使用（保持向后兼容）
        3. 默认值 - 最后返回
        """
        # 默认配置
        default_config = {
            "provider": "deepseek",
            "api_key": "",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "response_time": None,
            # 本地模型配置
            "local_model_id": "qwen-2b",  # qwen-2b 或 qwen-35b
            "local_model_path": None,
            "local_n_ctx": 4096,
            "local_n_gpu_layers": 0,
        }

        # 从全局配置读取（前端通过API设置），最高优先级
        config = default_config.copy()
        config.update(_global_config)

        # 从环境变量读取 - 仅在全局配置为空时才使用
        if not config.get("provider") or config.get("provider") == "openai":
            if os.getenv("LLM_PROVIDER"):
                config["provider"] = os.getenv("LLM_PROVIDER")

        if not config.get("api_key"):
            env_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
            if env_key:
                config["api_key"] = env_key

        if not config.get("base_url") or config.get("base_url") == "https://api.openai.com/v1":
            if os.getenv("DEEPSEEK_BASE_URL"):
                config["base_url"] = os.getenv("DEEPSEEK_BASE_URL")
            elif os.getenv("LLM_BASE_URL"):
                config["base_url"] = os.getenv("LLM_BASE_URL")
            elif os.getenv("CHAT2API_BASE_URL"):
                config["base_url"] = os.getenv("CHAT2API_BASE_URL")

        if not config.get("model"):
            if os.getenv("LLM_MODEL"):
                config["model"] = os.getenv("LLM_MODEL")
            elif os.getenv("DEEPSEEK_MODEL"):
                config["model"] = os.getenv("DEEPSEEK_MODEL")

        if not config.get("response_time"):
            if os.getenv("LLM_RESPONSE_TIME"):
                try:
                    config["response_time"] = float(os.getenv("LLM_RESPONSE_TIME"))
                except:
                    pass

        return config

    @staticmethod
    def set_config(config: Dict[str, Any]):
        """设置全局配置（由前端API调用）"""
        global _global_config
        _global_config.update(config)
        logger.info(f"LLM全局配置已更新: {_global_config}")

    @staticmethod
    def get_timeout() -> int:
        """
        获取超时时间（秒）

        优先级别：
        1. 手动设置的timeout参数（最高优先级）
        2. 根据测试的返回时长计算
        3. 默认300秒
        """
        config = LLMConfigManager.get_config()

        # 1. 优先使用手动设置的超时时间
        if "timeout" in config and config["timeout"]:
            try:
                manual_timeout = int(config["timeout"])
                if manual_timeout > 0:
                    logger.info(f"使用手动设置的超时时间: {manual_timeout}秒")
                    return manual_timeout
            except (ValueError, TypeError):
                logger.warning(f"手动设置的超时时间无效: {config['timeout']}")

        # 2. 根据测试的返回时长计算
        response_time = config.get("response_time")
        if response_time and response_time > 0:
            timeout = max(response_time * 3, response_time + 200)
            logger.info(f"根据测试时长计算超时: {response_time}秒 -> {int(timeout)}秒")
            return int(timeout)

        # 3. 默认300秒
        return 300

    @staticmethod
    def get_provider() -> str:
        """获取提供商"""
        return LLMConfigManager.get_config().get("provider", "deepseek")

    @staticmethod
    def get_base_url() -> str:
        """获取基础URL"""
        config = LLMConfigManager.get_config()
        provider = config.get("provider", "deepseek")

        if provider == "openai":
            return config.get("base_url", "https://api.openai.com/v1")
        elif provider == "deepseek":
            return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        elif provider == "local_llama":
            return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        else:
            # chat2api服务 - 优先使用用户配置的baseUrl
            user_base_url = config.get("base_url")
            if user_base_url:
                logger.info(f"[LLMConfig] 使用用户配置的base_url: {user_base_url}")
                return user_base_url
            env_base_url = os.getenv("CHAT2API_BASE_URL", "http://localhost:8088")
            logger.info(f"[LLMConfig] 使用环境变量的CHAT2API_BASE_URL: {env_base_url}")
            return env_base_url

    @staticmethod
    def is_chat2api_mode() -> bool:
        """是否使用chat2api模式（Kimi/Yuanbao）"""
        provider = LLMConfigManager.get_provider()
        return provider in ["kimi", "yuanbao"]

    @staticmethod
    def get_deepseek_api_key() -> str:
        """获取DeepSeek API Key"""
        config = LLMConfigManager.get_config()
        return config.get("api_key") or os.getenv("DEEPSEEK_API_KEY", "")

    @staticmethod
    def is_local_model_mode() -> bool:
        """是否使用本地模型模式"""
        provider = LLMConfigManager.get_provider()
        return provider in ["local_qwen", "local_llama"]

    @staticmethod
    def get_local_model_config() -> Dict[str, Any]:
        """
        获取本地模型配置
        
        Returns:
            本地模型配置字典
        """
        config = LLMConfigManager.get_config()
        
        return {
            "model_id": config.get("local_model_id", "qwen-2b"),
            "model_path": config.get("local_model_path"),
            "n_ctx": config.get("local_n_ctx", 4096),
            "n_gpu_layers": config.get("local_n_gpu_layers", 0),
        }

    @staticmethod
    def set_local_model(model_id: str, n_ctx: int = None, n_gpu_layers: int = None):
        """
        设置本地模型
        
        Args:
            model_id: 模型ID (qwen-2b, qwen-35b)
            n_ctx: 上下文长度
            n_gpu_layers: GPU层数
        """
        global _global_config
        _global_config["provider"] = "local_qwen"
        _global_config["local_model_id"] = model_id
        if n_ctx:
            _global_config["local_n_ctx"] = n_ctx
        if n_gpu_layers is not None:
            _global_config["local_n_gpu_layers"] = n_gpu_layers
        
        logger.info(f"本地模型配置已更新: model_id={model_id}, n_ctx={n_ctx}, n_gpu_layers={n_gpu_layers}")


# 全局配置实例
llm_config = LLMConfigManager()
