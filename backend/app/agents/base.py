"""
智能体基类
所有智能体的抽象基类
"""
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Tuple
from loguru import logger

from app.core.config import settings
from app.core.llm_config_manager import LLMConfigManager
from app.services.llm_service import LLMService, LLMProvider, get_llm_service
from app.core.json_utils import extract_json_from_response
from app.core.agent_logging import log_agent_dialogue, log_agent_trace, log_agent_workflow


class BaseAgent(ABC):
    """
    智能体基类
    
    所有智能体都应该继承此类，并实现process方法
    """
    
    def __init__(
        self,
        name: str,
        system_prompt: str,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None
    ):
        self.name = name
        self.system_prompt = system_prompt
        self._provider = provider  # 保存传入的provider参数
        self._model = model        # 保存传入的model参数
        
        # 使用新的LLM服务（每次调用时动态获取，确保使用最新配置）
        # 注意：不再在初始化时获取llm_service，而是在call_llm时动态获取
        self._llm_service = None
        
        logger.info(f"初始化智能体: {name}, provider参数: {provider}, model参数: {model}")
    
    @property
    def llm_service(self) -> LLMService:
        """
        动态获取LLM服务
        
        每次访问时都从配置管理器获取最新的配置，
        确保Agent始终使用用户在前端配置的LLM设置
        """
        # 每次调用时重新获取配置，确保使用最新的配置
        config = LLMConfigManager.get_config()
        provider_str = self._provider or config.get("provider", "openai")
        model = self._model or config.get("model") or settings.OPENAI_MODEL
        
        # 调试日志：记录当前使用的配置
        logger.debug(f"[{self.name}] 获取LLM服务 - 配置provider={config.get('provider')}, 实际使用={provider_str}, model={model}")
        
        # 强制使用配置管理器获取最新的LLM服务实例
        # 这会触发配置变化检测，清除旧缓存
        service = get_llm_service(
            provider=LLMProvider(provider_str) if isinstance(provider_str, str) else provider_str,
            model=model
        )
        
        # 记录实际获取到的服务的provider
        logger.debug(f"[{self.name}] LLM服务已获取: 实际provider={service.provider.value}, model={service.model}, base_url={service.chat2api_base_url}")
        
        return service
    
    async def call_llm(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """
        调用LLM
        
        Args:
            prompt: 用户提示词
            temperature: 可选的温度覆盖（仅OpenAI模式有效）
            json_mode: 是否要求JSON输出
            **kwargs: 额外参数（如enable_web_search等）
            
        Returns:
            LLM的响应文本
        """
        log_context = kwargs.pop("log_context", None)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # 如果指定了温度且是OpenAI模式，创建临时实例
            if temperature is not None and self.llm_service.provider == LLMProvider.OPENAI:
                temp_service = LLMService(
                    provider=self.llm_service.provider,
                    model=self.llm_service.model,
                    temperature=temperature,
                    max_tokens=self.llm_service.max_tokens,
                )
                result = await temp_service.chat(messages, json_mode=json_mode, **kwargs)
            else:
                result = await self.llm_service.chat(messages, json_mode=json_mode, **kwargs)

            log_agent_dialogue(
                self.name,
                prompt=prompt,
                response=result,
                context=log_context,
                metadata={
                    "temperature": temperature,
                    "json_mode": json_mode,
                },
            )
            logger.debug(f"{self.name} LLM响应: {result[:200]}...")
            return result
            
        except Exception as e:
            logger.error(f"{self.name} LLM调用失败: {e}")
            raise
    
    async def call_llm_with_history(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """
        调用LLM（带完整对话历史）
        
        Args:
            messages: 完整的消息列表
            json_mode: 是否要求JSON输出
            **kwargs: 额外参数
            
        Returns:
            LLM的响应文本
        """
        log_context = kwargs.pop("log_context", None)
        # 在消息列表开头添加系统提示
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        
        try:
            result = await self.llm_service.chat(full_messages, json_mode=json_mode, **kwargs)
            log_agent_dialogue(
                self.name,
                prompt=json.dumps(messages, ensure_ascii=False),
                response=result,
                context=log_context,
                metadata={"json_mode": json_mode, "mode": "history"},
            )
            logger.debug(f"{self.name} LLM响应: {result[:200]}...")
            return result
            
        except Exception as e:
            logger.error(f"{self.name} LLM调用失败: {e}")
            raise

    def get_react_max_steps(self, context: Optional[Dict[str, Any]] = None) -> int:
        """返回当前Agent的循环步数。

        优先级：
        1. context["agent_loop_steps"]（运行时传入）
        2. Agent 子类的 DEFAULT_REACT_MAX_STEPS（类级别配置）
        3. 全局 AGENT_STEP_CONFIG 中的默认值
        """
        context = context or {}
        if "agent_loop_steps" in context:
            return int(context["agent_loop_steps"])

        # 尝试从类名获取特定配置
        agent_name = self.__class__.__name__
        from app.agents.step_config import AGENT_STEP_CONFIG
        return int(AGENT_STEP_CONFIG.get(agent_name, self.DEFAULT_REACT_MAX_STEPS))

    def _stringify_react_payload(self, payload: Any) -> str:
        if payload is None:
            return ""
        if isinstance(payload, str):
            return payload
        try:
            return json.dumps(payload, ensure_ascii=False)
        except TypeError:
            return str(payload)

    def _build_react_prompt(
        self,
        task_prompt: str,
        step: int,
        max_steps: int,
        trace: List[Dict[str, Any]],
        output_format: str,
    ) -> str:
        trace_text = "无"
        if trace:
            trace_lines = []
            for idx, item in enumerate(trace, 1):
                trace_lines.append(
                    f"第{idx}轮 thought={item.get('thought','')[:120]} | "
                    f"action={item.get('action','')} | "
                    f"observation={item.get('observation','')[:160]}"
                )
            trace_text = "\n".join(trace_lines)

        final_format_hint = (
            "final_answer 必须是合法JSON对象/数组"
            if output_format == "json"
            else "final_answer 必须是最终要返回给下游的纯文本内容"
        )

        return f"""你正在执行一个 ReAct Agent Loop。

任务目标：
{task_prompt}

当前轮次：{step}/{max_steps}
已有观察：
{trace_text}

请严格输出 JSON，包含以下字段：
{{
  "thought": "你当前的判断与计划，简洁明确",
  "action": "analyze|reflect|revise|finish",
  "observation": "本轮得到的新观察、检查结论或修订方向",
  "final_answer": null
}}

规则：
1. 在未准备好最终答案前，action 使用 analyze/reflect/revise，final_answer 设为 null。
2. 当你已经可以给出高质量最终答案时，action 必须为 finish。
3. {final_format_hint}
4. 不要输出除 JSON 之外的任何内容。"""

    async def run_react_loop(
        self,
        task_prompt: str,
        *,
        context: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        output_format: str = "json",
        **kwargs,
    ) -> Dict[str, Any]:
        """执行统一的 ReAct + Agent Loop。"""
        context = context or {}
        max_steps = max(1, self.get_react_max_steps(context))
        trace: List[Dict[str, Any]] = []
        last_payload: Any = None
        last_response = ""

        for step in range(1, max_steps + 1):
            react_prompt = self._build_react_prompt(
                task_prompt=task_prompt,
                step=step,
                max_steps=max_steps,
                trace=trace,
                output_format=output_format,
            )
            response = await self.call_llm(
                react_prompt,
                temperature=temperature,
                json_mode=True,
                log_context=context,
                **kwargs,
            )
            last_response = response
            envelope, parse_message = extract_json_from_response(response)
            if envelope is None:
                envelope = {
                    "thought": "模型未返回合法JSON，进入容错处理",
                    "action": "finish" if step == max_steps else "reflect",
                    "observation": f"JSON解析失败: {parse_message}",
                    "final_answer": response if step == max_steps else None,
                }

            trace.append({
                "step": step,
                "thought": envelope.get("thought", ""),
                "action": envelope.get("action", "analyze"),
                "observation": envelope.get("observation", ""),
            })
            log_agent_workflow(
                self.name,
                "react_step",
                context=context,
                details={
                    "step": step,
                    "max_steps": max_steps,
                    "action": envelope.get("action", "analyze"),
                    "thought": envelope.get("thought", ""),
                    "observation": envelope.get("observation", ""),
                },
            )

            final_answer = envelope.get("final_answer")
            if final_answer is not None:
                last_payload = final_answer

            if envelope.get("action") == "finish" and final_answer is not None:
                break

        result = {
            "trace": trace,
            "final_payload": last_payload,
            "final_text": self._stringify_react_payload(last_payload),
            "raw_response": last_response,
        }
        log_agent_trace(self.name, trace, context=context)
        return result
    
    @abstractmethod
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理输入并返回结果
        
        Args:
            context: 包含所有必要信息的上下文字典
            
        Returns:
            处理结果字典
        """
        pass
    
    def log_action(self, action: str, details: Optional[Dict] = None):
        """记录智能体动作"""
        log_agent_workflow(self.name, action, details=details)
        logger.info(f"[{self.name}] {action}", extra=details or {})
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        if self.llm_service.provider == LLMProvider.OPENAI:
            return {
                "status": "ok",
                "provider": "openai",
                "model": self.llm_service.model,
            }
        else:
            status = await self.llm_service.check_chat2api_status()
            return {
                "status": "ok" if status.get("available") else "error",
                "provider": self.llm_service.provider.value,
                "chat2api_status": status,
            }
    DEFAULT_REACT_MAX_STEPS = 3
