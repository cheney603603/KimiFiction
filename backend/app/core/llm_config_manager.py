"""
LLM 配置管理器
用于读取前端保存的 LLM 配置
"""
import json
import os
from typing import Optional, Dict, Any
from loguru import logger

# 全局配置存储（用于存储前端传递的配置）
_global_config: Dict[str, Any] = {}


class LLMConfigManager:
    """
    LLM 配置管理器
    
    读取前端通过 API 传递的配置
    或者读取环境变量
    """
    
    @staticmethod
    def get_config() -> Dict[str, Any]:
        """
        获取 LLM 配置
        
        优先级（从高到低）：
        1. 全局配置（前端通过 API 设置）- 最高优先级
        2. 环境变量 - 仅在全局配置未设置时使用
        3. 默认值 - 最终回退
        """
        # 默认配置
        default_config = {
            "provider": "openai",
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4-turbo-preview",
            "response_time": None,  # 测试返回时长（秒）
        }
        
        # 从全局配置读取（前端通过 API 设置）- 最高优先级
        config = default_config.copy()
        config.update(_global_config)
        
        # 从环境变量读取 - 仅在全局配置为空时才使用（保持向后兼容）
        # 注意：环境变量只填充空值，不覆盖前端已设置的值
        if not config.get("provider") or config.get("provider") == "openai":
            if os.getenv("LLM_PROVIDER"):
                config["provider"] = os.getenv("LLM_PROVIDER")
        
        if not config.get("api_key"):
            if os.getenv("LLM_API_KEY"):
                config["api_key"] = os.getenv("LLM_API_KEY")
        
        if not config.get("base_url") or config.get("base_url") == "https://api.openai.com/v1":
            if os.getenv("LLM_BASE_URL"):
                config["base_url"] = os.getenv("LLM_BASE_URL")
            elif os.getenv("CHAT2API_BASE_URL"):
                config["base_url"] = os.getenv("CHAT2API_BASE_URL")
        
        if not config.get("model"):
            if os.getenv("LLM_MODEL"):
                config["model"] = os.getenv("LLM_MODEL")
        
        if not config.get("response_time"):
            if os.getenv("LLM_RESPONSE_TIME"):
                try:
                    config["response_time"] = float(os.getenv("LLM_RESPONSE_TIME"))
                except:
                    pass
        
        return config
    
    @staticmethod
    def set_config(config: Dict[str, Any]):
        """设置全局配置（由前端 API 调用）"""
        global _global_config
        _global_config.update(config)
        logger.info(f"LLM 全局配置已更新: {_global_config}")
    
    @staticmethod
    def get_timeout() -> int:
        """
        获取超时时间（秒）

        优先级：
        1. 手动设置的 timeout 参数（最高优先级）
        2. 根据测试的返回时长计算
        3. 默认 300 秒
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
            # 计算超时：3倍测试时长 或 测试时长+200秒，取较大值
            timeout = max(response_time * 3, response_time + 200)
            logger.info(f"根据测试时长计算超时: {response_time}秒 -> {int(timeout)}秒")
            return int(timeout)

        # 3. 默认 300 秒
        return 300
    
    @staticmethod
    def get_provider() -> str:
        """获取提供商"""
        return LLMConfigManager.get_config().get("provider", "openai")
    
    @staticmethod
    def get_base_url() -> str:
        """获取基础 URL"""
        config = LLMConfigManager.get_config()
        provider = config.get("provider", "openai")

        if provider == "openai":
            return config.get("base_url", "https://api.openai.com/v1")
        else:
            # chat2api 服务 - 优先使用用户配置的baseUrl
            user_base_url = config.get("base_url")
            if user_base_url:
                logger.info(f"[LLMConfig] 使用用户配置的base_url: {user_base_url}")
                return user_base_url
            # 回退到环境变量
            env_base_url = os.getenv("CHAT2API_BASE_URL", "http://localhost:8088")
            logger.info(f"[LLMConfig] 使用环境变量的CHAT2API_BASE_URL: {env_base_url}")
            return env_base_url
    
    @staticmethod
    def is_chat2api_mode() -> bool:
        """是否使用 chat2api 模式"""
        provider = LLMConfigManager.get_provider()
        return provider in ["kimi", "deepseek", "yuanbao"]


# 全局配置实例
llm_config = LLMConfigManager()
