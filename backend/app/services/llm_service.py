"""
LLM服务客户端
支持多种调用方式：
1. OpenAI API（直接调用）
2. DeepSeek API（直接调用，推荐）
3. Kimi/Yuanbao（通过chat2api本地服务）
4. 本地Llama模型（通过Ollama或直接加载）

支持外部注入API Key，无需硬编码
"""
import json
import asyncio
import os
import re
import time
from typing import Optional, Dict, Any, List, AsyncGenerator
from enum import Enum
from loguru import logger
import aiohttp

from app.core.config import settings
from app.core.llm_config_manager import llm_config, LLMConfigManager

# P0-2: DeepSeek json_object 支持探测标志（None=未知，True=支持，False=网关不支持已降级）
_deepseek_json_mode_supported: Optional[bool] = None


async def _record_llm_usage(
    *,
    model: str = "",
    provider: str = "",
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: int = 0,
    status: str = "success",
    retry_count: int = 0,
    error: str = "",
) -> None:
    """写入一条 LLM 用量记录（尽力而为，失败静默）。

    归属字段来自上下文：user_id(user_context)、novel/chapter/agent(llm_call_tracker)。
    """
    try:
        from app.core.database import get_session
        from app.core.user_context import get_current_user_id
        from app.core.llm_call_tracker import (
            get_current_novel_id, get_current_chapter_number,
            get_current_agent_name, get_current_phase,
        )
        from app.services.llm_usage_service import LLMUsageService

        async with get_session() as db:
            await LLMUsageService(db).record(
                user_id=get_current_user_id(),
                novel_id=get_current_novel_id(),
                chapter_number=get_current_chapter_number(),
                phase=get_current_phase(),
                agent_name=get_current_agent_name() or "",
                model=model,
                provider=provider,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                duration_ms=duration_ms,
                status=status,
                retry_count=retry_count,
                error=error[:500],
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[LLM usage] 记录用量失败(静默): {type(e).__name__}: {e}")


class LLMProvider(str, Enum):
    """LLM提供商"""
    OPENAI = "openai"
    KIMI = "kimi"
    DEEPSEEK = "deepseek"
    YUANBAO = "yuanbao"
    LOCAL_LLAMA = "local_llama"  # 本地Llama（Ollama/LlamaIndex）
    LOCAL_QWEN = "local_qwen"    # 本地Qwen（llama.cpp）


class LLMService:
    """
    LLM服务客户端
    
    支持模式：
    - openai: 直接调用OpenAI API
    - deepseek: 直接调用DeepSeek API（推荐）
    - kimi/yuanbao: 调用本地chat2api_service服务
    - local_llama: 调用本地Ollama服务或直接加载模型
    """
    
    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        chat2api_base_url: Optional[str] = None
    ):
        # 从配置管理器读取配置
        config = LLMConfigManager.get_config()
        
        # 确定提供商
        if provider:
            self.provider = provider
        else:
            provider_str = config.get("provider", settings.LLM_PROVIDER)
            self.provider = LLMProvider(provider_str)
        
        self.model = model or config.get("model") or settings.OPENAI_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 确定基础URL
        if chat2api_base_url:
            self.chat2api_base_url = chat2api_base_url
        else:
            self.chat2api_base_url = config.get("base_url") or settings.CHAT2API_BASE_URL
        
        # 初始化各类型客户端
        self._init_client(config)
    
    def _init_client(self, config: Dict[str, Any]):
        """根据provider类型初始化对应客户端"""
        
        if self.provider == LLMProvider.OPENAI:
            self._init_openai_client(config)
        elif self.provider == LLMProvider.DEEPSEEK:
            self._init_deepseek_client(config)
        elif self.provider == LLMProvider.LOCAL_LLAMA:
            self._init_local_llama_client(config)
        elif self.provider == LLMProvider.LOCAL_QWEN:
            self._init_local_qwen_client(config)
        else:
            # kimi/yuanbao 走chat2api
            self.openai_client = None
            self.deepseek_client = None
            self.local_llama_client = None
            logger.info(f"LLMService初始化: chat2api模式, provider={self.provider.value}, base_url={self.chat2api_base_url}")
    
    def _init_openai_client(self, config: Dict[str, Any]):
        """初始化OpenAI客户端"""
        try:
            from langchain_openai import ChatOpenAI
            # 优先使用有效配置（含用户 BYOK），回落环境变量/默认
            api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY") or settings.OPENAI_API_KEY
            base_url = config.get("base_url") or os.environ.get("OPENAI_BASE_URL") or settings.OPENAI_BASE_URL
            
            self.openai_client = ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
                base_url=base_url,
            )
            self.deepseek_client = None
            self.local_llama_client = None
            logger.info(f"LLMService初始化: OpenAI模式, model={self.model}, base_url={base_url}")
        except Exception as e:
            logger.error(f"OpenAI客户端初始化失败: {e}")
            self.openai_client = None
    
    def _init_deepseek_client(self, config: Dict[str, Any]):
        """初始化DeepSeek客户端（直接调用API）"""
        try:
            from langchain_openai import ChatOpenAI

            # 优先使用有效配置（含用户 BYOK 的 key/base_url），回落环境变量/默认
            api_key = (
                config.get("api_key")
                or os.environ.get("DEEPSEEK_API_KEY")
                or os.environ.get("LLM_API_KEY")
                or settings.DEEPSEEK_API_KEY
            )
            base_url = (
                config.get("base_url")
                or os.environ.get("DEEPSEEK_BASE_URL")
                or settings.DEEPSEEK_BASE_URL
            )

            if not api_key:
                logger.warning("DeepSeek API Key未配置!")
            
            self.openai_client = ChatOpenAI(
                model=self.model or settings.DEEPSEEK_MODEL,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
                base_url=base_url,
            )
            self.deepseek_client = self.openai_client
            self.local_llama_client = None
            logger.info(f"LLMService初始化: DeepSeek模式, model={self.model or settings.DEEPSEEK_MODEL}, base_url={base_url}")
        except Exception as e:
            logger.error(f"DeepSeek客户端初始化失败: {e}")
            self.openai_client = None
            self.deepseek_client = None
    
    def _init_local_llama_client(self, config: Dict[str, Any]):
        """初始化本地Llama客户端"""
        self.ollama_base_url = os.environ.get("OLLAMA_BASE_URL") or settings.OLLAMA_BASE_URL
        self.llama_model_path = os.environ.get("LOCAL_LLAMA_MODEL_PATH") or settings.LOCAL_LLAMA_MODEL_PATH
        
        self.openai_client = None
        self.deepseek_client = None
        self.local_llama_client = "ollama"
        self.local_qwen_client = None
        logger.info(f"LLMService初始化: Local Llama模式, ollama={self.ollama_base_url}, model_path={self.llama_model_path}")
    
    def _init_local_qwen_client(self, config: Dict[str, Any]):
        """初始化本地Qwen客户端（llama.cpp）"""
        from app.core.local_llm import create_local_llm_service, list_available_models
        
        # 获取模型配置
        model_id = config.get("local_model_id", "qwen-2b")
        n_ctx = config.get("local_n_ctx", 4096)
        n_gpu_layers = config.get("local_n_gpu_layers", 0)
        
        # 检查可用模型
        available_models = list_available_models()
        logger.info(f"[LLMService] 可用本地模型: {list(available_models.keys())}")
        
        self.openai_client = None
        self.deepseek_client = None
        self.local_llama_client = None
        self.local_qwen_client = create_local_llm_service(
            model_id=model_id,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
        )
        logger.info(f"LLMService初始化: Local Qwen模式, model_id={model_id}, model_path={self.local_qwen_client.config.model_path}")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """发送聊天消息（全局 RPM 限速入口）"""
        from app.core.llm_rate_limiter import llm_rate_limiter
        await llm_rate_limiter.acquire()
        if self.provider == LLMProvider.OPENAI:
            return await self._chat_openai(messages, json_mode, **kwargs)
        elif self.provider == LLMProvider.DEEPSEEK:
            return await self._chat_deepseek(messages, json_mode, **kwargs)
        elif self.provider == LLMProvider.LOCAL_LLAMA:
            return await self._chat_local_llama(messages, json_mode, **kwargs)
        elif self.provider == LLMProvider.LOCAL_QWEN:
            return await self._chat_local_qwen(messages, json_mode, **kwargs)
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
        api_key = os.environ.get("OPENAI_API_KEY") or config.get("api_key") or settings.OPENAI_API_KEY
        base_url = config.get("base_url") or settings.OPENAI_BASE_URL
        
        if not api_key:
            raise ValueError("未配置有效的OpenAI API Key")
        
        if not self.openai_client:
            try:
                from langchain_openai import ChatOpenAI
                self.openai_client = ChatOpenAI(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    api_key=api_key,
                    base_url=base_url,
                )
            except Exception as init_err:
                raise ValueError(f"OpenAI客户端初始化失败: {init_err}")
        
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

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

            logger.info(f"[LLM] 调用OpenAI API: model={self.model}, messages={len(langchain_messages)}, json_mode={json_mode}")
            # P0-2: json_mode 时显式声明 response_format，避免依赖模型自觉
            if json_mode:
                bound_client = self.openai_client.bind(response_format={"type": "json_object"})
            else:
                bound_client = self.openai_client
            start_time = time.monotonic()
            response = await bound_client.ainvoke(langchain_messages)
            content = response.content or ""
            usage_in = sum(len(m.get("content", "")) for m in messages)
            usage_out = len(content)
            try:
                meta = response.response_metadata or {}
                if meta.get("token_usage"):
                    usage_in = int(meta["token_usage"].get("prompt_tokens", usage_in))
                    usage_out = int(meta["token_usage"].get("completion_tokens", usage_out))
            except Exception:
                pass
            await _record_llm_usage(
                model=self.model, provider="openai",
                tokens_in=usage_in, tokens_out=usage_out,
                duration_ms=int((time.monotonic() - start_time) * 1000),
                status="success", retry_count=0,
            )
            return content
        except Exception as e:
            await _record_llm_usage(
                model=self.model, provider="openai", tokens_in=0, tokens_out=0,
                duration_ms=0, status="error", error=str(e)[:500],
            )
            logger.error(f"OpenAI API调用失败: {e}")
            raise
    
    async def _chat_deepseek(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """使用DeepSeek API调用（直接调用，不需要chat2api）

        联影 AI Infra 网关对非流式请求有 ~1000 字节的请求体上限，
        因此这里始终以流式(stream=true)方式调用，再聚合结果。
        """
        import httpx

        class _RetryableLLMError(Exception):
            pass

        config = LLMConfigManager.get_config()

        # BYOK：优先使用有效配置（含用户自己的 Key/BaseURL），回落环境变量/默认
        api_key = (
            config.get("api_key")
            or os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("LLM_API_KEY")
            or settings.DEEPSEEK_API_KEY
        )
        base_url = (
            config.get("base_url")
            or os.environ.get("DEEPSEEK_BASE_URL")
            or settings.DEEPSEEK_BASE_URL
        )

        if not api_key:
            raise ValueError("未配置DeepSeek API Key! 请设置DEEPSEEK_API_KEY环境变量")

        model = self.model or settings.DEEPSEEK_MODEL
        timeout = config.get("timeout") or 120
        provider = "deepseek"

        logger.info(f"[LLM] 调用DeepSeek API(流式): model={model}, base_url={base_url}, json_mode={bool(json_mode)}")
        # 对网关限流/过载(429/5xx)做指数退避重试，保证长时间批量生成稳定。
        # 收紧默认值以便快速失败（联影网关不稳定时避免一次调用卡数小时）。
        retries = int(os.environ.get("LLM_RETRIES", "4"))
        backoff_max = int(os.environ.get("LLM_RETRY_BACKOFF_MAX", "60"))

        # P0-2: json_mode 时附加 response_format；网关不支持则探测后降级为 prompt 约束（仅记录，不阻塞）
        global _deepseek_json_mode_supported
        want_json_mode = bool(json_mode)
        if want_json_mode and _deepseek_json_mode_supported is False:
            want_json_mode = False

        start_time = time.monotonic()
        last_error = ""
        for attempt in range(1, retries + 1):
            payload = {
                "model": model,
                "messages": [
                    {"role": m.get("role", "user"), "content": m.get("content", "")}
                    for m in messages
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if want_json_mode:
                payload["response_format"] = {"type": "json_object"}
            try:
                async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                    async with client.stream(
                        "POST", f"{base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json=payload,
                    ) as resp:
                        if resp.status_code != 200:
                            body = (await resp.aread()).decode("utf-8", "replace")
                            if want_json_mode and resp.status_code in (400, 422):
                                _deepseek_json_mode_supported = False
                                logger.warning(
                                    f"[LLM] DeepSeek json_object 不被网关支持(HTTP {resp.status_code}: {body[:150]})，"
                                    f"降级为 prompt 约束"
                                )
                                want_json_mode = False
                                continue
                            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                                raise _RetryableLLMError(body[:200])
                            raise RuntimeError(
                                f"DeepSeek API 返回 HTTP {resp.status_code}: {body[:300]}"
                            )
                        content = ""
                        usage_in = 0
                        usage_out = 0
                        async for line in resp.aiter_lines():
                            if not line or not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            choices = chunk.get("choices", [{}])
                            if chunk.get("usage"):
                                usage_in = int(chunk["usage"].get("prompt_tokens", 0))
                                usage_out = int(chunk["usage"].get("completion_tokens", 0))
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {}).get("content")
                            if delta:
                                content += delta
                if want_json_mode and _deepseek_json_mode_supported is None:
                    _deepseek_json_mode_supported = True
                # 用量估算：网关未返回 usage 时按字符粗估
                if not usage_out:
                    usage_in = sum(len(m.get("content", "")) for m in messages)
                    usage_out = len(content)
                await _record_llm_usage(
                    model=model, provider=provider,
                    tokens_in=usage_in, tokens_out=usage_out,
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                    status="success", retry_count=attempt - 1,
                )
                return content.strip()
            except _RetryableLLMError as e:
                backoff = min(2 ** attempt, backoff_max)
                last_error = str(e)[:300]
                logger.warning(f"[LLM] 网关过载({e})，{backoff}s后重试 ({attempt}/{retries})")
                await asyncio.sleep(backoff)
                continue
            except httpx.HTTPStatusError:
                raise
            except (httpx.TransportError, httpx.TimeoutException, httpx.ConnectError):
                last_error = str(e)[:300]
                if attempt >= retries:
                    break
                await asyncio.sleep(min(2 ** attempt, 60))
                continue
        await _record_llm_usage(
            model=model, provider=provider,
            tokens_in=0, tokens_out=0,
            duration_ms=int((time.monotonic() - start_time) * 1000),
            status="error", retry_count=retries, error=last_error or "重试均失败",
        )
        raise RuntimeError("DeepSeek API 重试均失败")
    
    async def _chat_local_qwen(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """使用本地Qwen模型（llama.cpp）"""
        try:
            if not self.local_qwen_client:
                from app.core.local_llm import get_local_llm_service
                self.local_qwen_client = get_local_llm_service()
            
            result = await self.local_qwen_client.chat(
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens)
            )
            
            # 如果要求JSON模式，尝试提取JSON
            if json_mode and result:
                from app.core.json_utils import extract_json_from_response
                json_result, _ = extract_json_from_response(result)
                if json_result:
                    import json
                    return json.dumps(json_result, ensure_ascii=False)
            
            return result
            
        except Exception as e:
            logger.error(f"[LLM] 本地Qwen调用失败: {e}")
            raise
    
    async def _chat_local_llama(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """使用本地Llama模型（通过Ollama）"""
        try:
            url = f"{self.ollama_base_url}/api/chat"
            
            user_msg = ""
            system_msg = ""
            for msg in messages:
                if msg.get("role") == "user":
                    user_msg = msg.get("content", "")
                elif msg.get("role") == "system":
                    system_msg = msg.get("content", "")
            
            if not user_msg and messages:
                user_msg = messages[-1].get("content", "")
            
            payload = {
                "model": self.model or "llama2",
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                "stream": False,
                "think": False,  # 禁用思考过程，只输出正文（对deepseek-r1等推理模型有效）
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                }
            }
            
            logger.info(f"[LLM] 调用本地Ollama: model={payload['model']}, url={url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=min(self.max_tokens * 2, 600))) as response:
                    if response.status == 200:
                        result = await response.json()
                        raw = result.get("message", {}).get("content", "")
                        # 过滤掉思考标签（deepseek-r1等推理模型）
                        # Ollama deepseek-r1 格式: <think><think>...content...</think><answer>
                        # 用 split 分离：['content', '<think>', 'thinking...', '</think>', 'answer']
                        parts = re.split(r'(<think>|</think>)', raw)
                        if len(parts) >= 3:
                            # 实际回复 = 最后一个 part 的第一行非空内容
                            for part in reversed(parts):
                                cleaned = part.strip()
                                if cleaned:
                                    return cleaned
                        return raw.strip()
                    else:
                        text = await response.text()
                        raise ValueError(f"Ollama调用失败: HTTP {response.status}, {text}")
        except aiohttp.ClientConnectorError:
            logger.warning("Ollama未运行，尝试使用LlamaIndex直接加载模型")
            return await self._chat_llamaindex(messages, json_mode, **kwargs)
        except Exception as e:
            logger.error(f"本地Llama调用失败: {e}")
            raise
    
    async def _chat_llamaindex(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """使用LlamaIndex直接加载本地模型（无Ollama时）"""
        try:
            from llama_index.llms.ollama import Ollama
            
            system_msg = ""
            user_msg = ""
            for msg in messages:
                if msg.get("role") == "system":
                    system_msg = msg.get("content", "")
                elif msg.get("role") == "user":
                    user_msg = msg.get("content", "")
            
            llm = Ollama(
                model=self.model or "llama2",
                temperature=self.temperature,
                request_timeout=kwargs.get("timeout", 300),
            )
            
            logger.info(f"[LLM] 使用LlamaIndex调用本地模型: {self.model or 'llama2'}")
            full_prompt = f"{system_msg}\n\n{user_msg}" if system_msg else user_msg
            response = llm.complete(full_prompt)
            return response.text
        except ImportError:
            raise ImportError("请安装llama-index: pip install llama-index llama-index-llms-ollama")
        except Exception as e:
            logger.error(f"LlamaIndex调用失败: {e}")
            raise
    
    async def _chat_chat2api(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """使用chat2api_service调用（Kimi/Yuanbao）"""
        combined_message = self._combine_messages(messages)

        if json_mode:
            combined_message += "\n\n请确保输出是合法的JSON格式。"

        url = f"{self.chat2api_base_url}/api/{self.provider.value}/chat"
        request_timeout = int(kwargs.get("timeout", 240))

        payload = {
            "message": combined_message,
            "timeout": request_timeout,
        }

        if self.provider == LLMProvider.YUANBAO:
            payload["enable_web_search"] = kwargs.get("enable_web_search", False)
            payload["enable_deep_think"] = kwargs.get("enable_deep_think", False)
        elif self.provider == LLMProvider.KIMI:
            payload["model"] = kwargs.get("model", "k2.5")

        try:
            logger.info(f"[LLM] 调用chat2api: {self.provider.value} @ {url}")
            http_timeout = max(request_timeout + 60, 300)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=http_timeout) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("success"):
                            logger.info(f"[LLM] 调用成功: {self.provider.value}")
                            return result.get("data", "")
                        else:
                            raise ValueError(f"chat2api调用失败: {result.get('message')}")
                    elif response.status == 401:
                        raise ValueError(f"chat2api未登录，请先登录{self.provider.value}")
                    else:
                        text = await response.text()
                        raise ValueError(f"chat2api调用失败: HTTP {response.status}, {text}")
        except asyncio.TimeoutError:
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
                parts.append(f"【系统】\n{content}")
            elif role == "user":
                parts.append(f"【用户】\n{content}")
            elif role == "assistant":
                parts.append(f"【助手】\n{content}")
        return "\n\n".join(parts)
    
    async def check_status(self) -> Dict[str, Any]:
        """检查LLM服务状态"""
        if self.provider == LLMProvider.OPENAI:
            return {"available": True, "mode": "openai", "model": self.model}
        elif self.provider == LLMProvider.DEEPSEEK:
            return {"available": True, "mode": "deepseek", "model": self.model or settings.DEEPSEEK_MODEL}
        elif self.provider == LLMProvider.LOCAL_LLAMA:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.ollama_base_url}/api/tags", timeout=5) as resp:
                        if resp.status == 200:
                            return {"available": True, "mode": "ollama", "url": self.ollama_base_url}
            except:
                pass
            return {"available": False, "mode": "local_llama", "error": "Ollama未运行"}
        elif self.provider == LLMProvider.LOCAL_QWEN:
            try:
                from app.core.local_llm import check_local_model
                return await check_local_model()
            except Exception as e:
                return {"available": False, "mode": "local_qwen", "error": str(e)}
        else:
            try:
                url = f"{self.chat2api_base_url}/api/status/{self.provider.value}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            result = await response.json()
                            return {"available": result.get("is_logged_in", False), "mode": "chat2api", "provider": self.provider.value}
            except:
                pass
            return {"available": False, "mode": "chat2api", "error": "连接失败"}
    
    @classmethod
    def from_config(cls, config: Optional[Dict] = None) -> "LLMService":
        """从配置创建LLMService实例"""
        config = config or {}
        provider_str = config.get("provider", settings.LLM_PROVIDER)
        provider = LLMProvider(provider_str)
        return cls(
            provider=provider,
            model=config.get("model", settings.OPENAI_MODEL),
            temperature=config.get("temperature", settings.OPENAI_TEMPERATURE),
            max_tokens=config.get("max_tokens", settings.OPENAI_MAX_TOKENS),
            chat2api_base_url=config.get("chat2api_base_url", settings.CHAT2API_BASE_URL),
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
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> LLMService:
    """获取LLM服务实例（带缓存）"""
    global _last_config_hash, _llm_instances

    config = LLMConfigManager.get_config()
    config_provider = config.get("provider", settings.LLM_PROVIDER)

    current_hash = _get_config_hash()
    if current_hash != _last_config_hash:
        logger.info(f"[LLM] 配置变化检测到，清除旧缓存")
        _llm_instances.clear()
        _last_config_hash = current_hash

    provider = provider or LLMProvider(config_provider)
    model = model or config.get("model") or settings.OPENAI_MODEL
    max_tokens = max_tokens or settings.OPENAI_MAX_TOKENS

    cache_key = f"{provider.value}_{model}_{max_tokens}"

    if cache_key not in _llm_instances:
        logger.info(f"[LLM] 创建新的LLM服务实例: provider={provider.value}, model={model}, max_tokens={max_tokens}")
        _llm_instances[cache_key] = LLMService(provider=provider, model=model, max_tokens=max_tokens)

    return _llm_instances[cache_key]
