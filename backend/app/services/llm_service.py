"""
LLM服务客户端
支持两种调用方式：
1. 标准OpenAI API调用
2. chat2api_service本地服务调用
"""
import json
import asyncio
from typing import Optional, Dict, Any, List, AsyncGenerator
from enum import Enum
from loguru import logger
import aiohttp

from app.core.config import settings
from app.core.llm_config_manager import llm_config, LLMConfigManager


class LLMProvider(str, Enum):
    """LLM提供商"""
    OPENAI = "openai"
    KIMI = "kimi"
    DEEPSEEK = "deepseek"
    YUANBAO = "yuanbao"


class LLMService:
    """
    LLM服务客户端
    
    支持两种模式：
    - openai: 直接调用OpenAI API或兼容API
    - chat2api: 调用本地chat2api_service服务
    """
    
    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        chat2api_base_url: Optional[str] = None
    ):
        # 从配置管理器读取配置
        config = LLMConfigManager.get_config()
        
        # 确定提供商
        if provider:
            self.provider = provider
        else:
            provider_str = config.get("provider", "openai")
            self.provider = LLMProvider(provider_str)
        
        self.model = model or config.get("model") or settings.OPENAI_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 确定 chat2api 基础 URL
        if chat2api_base_url:
            self.chat2api_base_url = chat2api_base_url
        else:
            self.chat2api_base_url = config.get("base_url", "http://localhost:8088")
        
        # 如果是openai模式，初始化OpenAI客户端
        if self.provider == LLMProvider.OPENAI:
            try:
                from langchain_openai import ChatOpenAI
                api_key = config.get("api_key") or settings.OPENAI_API_KEY
                base_url = config.get("base_url") or settings.OPENAI_BASE_URL
                
                self.openai_client = ChatOpenAI(
                    model=self.model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=api_key,
                    base_url=base_url,
                )
                logger.info(f"LLMService初始化: OpenAI模式, model={self.model}, base_url={base_url}")
            except Exception as e:
                logger.error(f"OpenAI客户端初始化失败: {e}")
                self.openai_client = None
        else:
            self.openai_client = None
            logger.info(f"LLMService初始化: chat2api模式, provider={self.provider.value}, base_url={self.chat2api_base_url}")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """
        发送聊天消息
        
        Args:
            messages: 消息列表，格式 [{"role": "system"/"user"/"assistant", "content": "..."}]
            json_mode: 是否要求JSON输出
            **kwargs: 额外参数
            
        Returns:
            LLM回复文本
        """
        if self.provider == LLMProvider.OPENAI:
            return await self._chat_openai(messages, json_mode, **kwargs)
        else:
            return await self._chat_chat2api(messages, json_mode, **kwargs)
    
    async def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """使用OpenAI API调用"""
        config = LLMConfigManager.get_config()
        api_key = config.get("api_key") or settings.OPENAI_API_KEY
        base_url = config.get("base_url") or settings.OPENAI_BASE_URL
        
        if not api_key or api_key == "your-openai-api-key":
            raise ValueError(
                "【配置错误】未设置有效的 OpenAI API Key！\n"
                "请在设置页面配置LLM，或在 backend/.env 文件中设置: OPENAI_API_KEY=你的真实API密钥\n"
                "或者切换到其他LLM提供商"
            )
        
        if not self.openai_client:
            # 尝试重新初始化
            try:
                from langchain_openai import ChatOpenAI
                self.openai_client = ChatOpenAI(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    api_key=api_key,
                    base_url=base_url,
                )
                logger.info(f"OpenAI客户端重新初始化: model={self.model}, base_url={base_url}")
            except Exception as init_err:
                raise ValueError(f"OpenAI客户端初始化失败: {init_err}")
        
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
            
            # 转换消息格式
            langchain_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    langchain_messages.append(SystemMessage(content=content))
                elif role == "user":
                    langchain_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=content))
            
            # 调用LLM
            logger.info(f"[LLM] 调用OpenAI API: model={self.model}, base_url={base_url}, messages={len(langchain_messages)}")
            response = await self.openai_client.ainvoke(langchain_messages)
            return response.content
            
        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower() or "connect" in error_msg.lower():
                logger.error(f"OpenAI API连接失败: {e}\n请检查:\n1. API Key是否正确\n2. Base URL是否可访问\n3. 网络连接是否正常")
                raise ValueError(f"无法连接到LLM服务: {e}\n请检查设置页面中的LLM配置")
            logger.error(f"OpenAI API调用失败: {e}")
            raise
    
    async def _chat_chat2api(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """使用chat2api_service调用"""
        # 将消息列表合并为单个消息
        # chat2api_service目前只支持单轮对话
        combined_message = self._combine_messages(messages)

        if json_mode:
            combined_message += "\n\n请确保输出是合法的JSON格式。"

        url = f"{self.chat2api_base_url}/api/{self.provider.value}/chat"

        request_timeout = int(kwargs.get("timeout", 240))

        payload = {
            "message": combined_message,
            "timeout": request_timeout,
        }

        # 添加功能开关参数
        if self.provider == LLMProvider.YUANBAO:
            payload["enable_web_search"] = kwargs.get("enable_web_search", False)
            payload["enable_deep_think"] = kwargs.get("enable_deep_think", False)
        elif self.provider == LLMProvider.DEEPSEEK:
            payload["enable_deep_think"] = kwargs.get("enable_deep_think", False)
            payload["enable_web_search"] = kwargs.get("enable_web_search", False)
        elif self.provider == LLMProvider.KIMI:
            payload["model"] = kwargs.get("model", "k2.5")

        try:
            logger.info(f"[LLM] 调用chat2api: {self.provider.value} @ {url}")
            logger.debug(f"[LLM] 请求参数: timeout={payload.get('timeout')}")

            http_timeout = max(request_timeout + 60, 300)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=http_timeout) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("success"):
                            logger.info(f"[LLM] 调用成功: {self.provider.value}")
                            data = result.get("data", "")
                            # 记录返回数据的类型和长度
                            logger.debug(f"[LLM] 返回数据类型: {type(data).__name__}, 长度: {len(data) if isinstance(data, str) else 'N/A'}")
                            return data
                        else:
                            raise ValueError(f"chat2api调用失败: {result.get('message')}")
                    elif response.status == 401:
                        raise ValueError(f"chat2api未登录，请先登录{self.provider.value}")
                    else:
                        text = await response.text()
                        logger.error(f"[LLM] HTTP错误 {response.status}: {text}")
                        raise ValueError(f"chat2api调用失败: HTTP {response.status}, {text}")
        except asyncio.TimeoutError:
            logger.error(f"[LLM] 调用超时: {self.provider.value}")
            raise ValueError("chat2api调用超时")
        except Exception as e:
            logger.error(f"[LLM] chat2api调用失败: {e}")
            raise
    
    def _combine_messages(self, messages: List[Dict[str, str]]) -> str:
        """将消息列表合并为单个字符串"""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"【系统指令】\n{content}")
            elif role == "user":
                parts.append(f"【用户】\n{content}")
            elif role == "assistant":
                parts.append(f"【助手】\n{content}")
        return "\n\n".join(parts)
    
    async def check_chat2api_status(self) -> Dict[str, Any]:
        """检查chat2api_service状态"""
        if self.provider == LLMProvider.OPENAI:
            return {"available": True, "mode": "openai"}
        
        try:
            url = f"{self.chat2api_base_url}/api/status/{self.provider.value}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "available": result.get("is_logged_in", False),
                            "mode": "chat2api",
                            "provider": self.provider.value,
                            "message": result.get("message", ""),
                        }
                    else:
                        return {
                            "available": False,
                            "mode": "chat2api",
                            "error": f"HTTP {response.status}",
                        }
        except Exception as e:
            return {
                "available": False,
                "mode": "chat2api",
                "error": str(e),
            }
    
    @classmethod
    def from_config(cls, config: Optional[Dict] = None) -> "LLMService":
        """从配置创建LLMService实例"""
        config = config or {}
        
        # 获取提供商
        provider_str = config.get("provider", settings.LLM_PROVIDER or "openai")
        provider = LLMProvider(provider_str)
        
        return cls(
            provider=provider,
            model=config.get("model", settings.OPENAI_MODEL),
            temperature=config.get("temperature", settings.OPENAI_TEMPERATURE),
            max_tokens=config.get("max_tokens", settings.OPENAI_MAX_TOKENS),
            chat2api_base_url=config.get("chat2api_base_url", "http://localhost:8000"),
        )


# 全局LLM服务实例缓存
_llm_instances: Dict[str, LLMService] = {}
_last_config_hash: str = ""


def _get_config_hash() -> str:
    """获取配置的哈希值，用于检测配置变化"""
    config = LLMConfigManager.get_config()
    return f"{config.get('provider')}_{config.get('base_url')}_{config.get('model')}"


def get_llm_service(
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None
) -> LLMService:
    """
    获取LLM服务实例（带缓存）
    
    优先使用用户配置（通过 LLMConfigManager）
    配置变化时会自动刷新缓存
    
    Args:
        provider: 提供商，默认从配置读取
        model: 模型名称
        
    Returns:
        LLMService实例
    """
    global _last_config_hash, _llm_instances
    
    # 从配置管理器读取用户配置
    config = LLMConfigManager.get_config()
    config_provider = config.get("provider", "openai")
    
    # 检测配置是否变化
    current_hash = _get_config_hash()
    if current_hash != _last_config_hash:
        logger.info(f"[LLM] 配置变化检测到，清除旧缓存: old_hash={_last_config_hash}, new_hash={current_hash}")
        _llm_instances.clear()
        _last_config_hash = current_hash
    
    # 使用传入的参数或配置
    provider = provider or LLMProvider(config_provider)
    model = model or config.get("model") or settings.OPENAI_MODEL
    
    cache_key = f"{provider.value}_{model}"
    
    if cache_key not in _llm_instances:
        logger.info(f"[LLM] 创建新LLM服务实例: provider={provider.value}, model={model}")
        _llm_instances[cache_key] = LLMService(provider=provider, model=model)
    else:
        logger.debug(f"[LLM] 使用缓存的LLM服务实例: {cache_key}")
    
    return _llm_instances[cache_key]
