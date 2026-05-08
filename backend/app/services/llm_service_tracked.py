"""
增强版LLM服务 - 集成调用追踪和快照功能

使用方式与原版LLMService相同，但会自动：
1. 记录每次LLM调用的输入输出
2. 创建系统状态快照
3. 支持从前端查看和回滚
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from app.services.llm_service import LLMService, LLMProvider
from app.core.llm_call_tracker import LLMCallTracker, current_novel_id


class TrackedLLMService(LLMService):
    """
    带追踪功能的LLM服务
    
    自动记录每次调用并创建快照，支持：
    - 查看调用历史
    - 对比输入输出
    - 回滚到任意状态
    """
    
    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        chat2api_base_url: Optional[str] = None,
        novel_id: Optional[int] = None,
        agent_name: str = "unknown",
        auto_track: bool = True
    ):
        super().__init__(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            chat2api_base_url=chat2api_base_url
        )
        
        self.novel_id = novel_id or current_novel_id.get()
        self.agent_name = agent_name
        self.auto_track = auto_track
        self._tracker: Optional[LLMCallTracker] = None
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ) -> str:
        """
        发送聊天消息（带追踪）
        
        如果设置了novel_id和auto_track=True，会自动：
        1. 创建调用前快照
        2. 记录输入消息
        3. 执行LLM调用
        4. 记录输出结果
        5. 保存完整调用记录
        """
        if not self.auto_track or not self.novel_id:
            # 不追踪，直接调用父类
            return await super().chat(messages, json_mode, **kwargs)
        
        # 使用追踪器
        description = kwargs.get("description", f"{self.agent_name} 生成内容")
        
        async with LLMCallTracker(
            novel_id=self.novel_id,
            agent_name=self.agent_name,
            model=self.model or "unknown",
            description=description,
            workflow_state=kwargs.get("workflow_state")
        ) as tracker:
            try:
                # 记录输入
                tracker.record_input(messages)
                
                # 执行调用
                result = await super().chat(messages, json_mode, **kwargs)
                
                # 记录输出
                tracker.record_output(result)
                
                return result
                
            except Exception as e:
                tracker.error = str(e)
                raise
    
    async def chat_with_stream(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = False,
        **kwargs
    ):
        """
        流式聊天（带追踪）
        
        注意：流式调用会在结束时创建快照，而不是开始时
        """
        if not self.auto_track or not self.novel_id:
            async for chunk in super().chat_stream(messages, json_mode, **kwargs):
                yield chunk
            return
        
        # 手动追踪（因为流式需要等结束才能记录输出）
        tracker = LLMCallTracker(
            novel_id=self.novel_id,
            agent_name=self.agent_name,
            model=self.model or "unknown",
            description=kwargs.get("description", f"{self.agent_name} 流式生成")
        )
        
        await tracker.__aenter__()
        tracker.record_input(messages)
        
        full_content = []
        error = None
        
        try:
            async for chunk in super().chat_stream(messages, json_mode, **kwargs):
                full_content.append(chunk)
                yield chunk
            
            # 记录完整输出
            tracker.record_output("".join(full_content))
            
        except Exception as e:
            error = e
            tracker.error = str(e)
        finally:
            await tracker.__aexit__(
                type(error) if error else None,
                error,
                None
            )
    
    def with_context(self, novel_id: int, agent_name: Optional[str] = None) -> "TrackedLLMService":
        """
        创建带上下文的新实例
        
        使用示例：
            llm = TrackedLLMService()
            writer_llm = llm.with_context(novel_id=1, agent_name="writer")
            result = await writer_llm.chat(messages)
        """
        return TrackedLLMService(
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            chat2api_base_url=getattr(self, "chat2api_base_url", None),
            novel_id=novel_id,
            agent_name=agent_name or self.agent_name,
            auto_track=self.auto_track
        )


# 便捷创建函数
def create_tracked_llm(
    agent_name: str,
    novel_id: Optional[int] = None,
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
    **kwargs
) -> TrackedLLMService:
    """
    创建带追踪的LLM服务
    
    使用示例：
        llm = create_tracked_llm(
            agent_name="writer",
            novel_id=1,
            provider=LLMProvider.DEEPSEEK
        )
        result = await llm.chat(messages)
    """
    return TrackedLLMService(
        agent_name=agent_name,
        novel_id=novel_id,
        provider=provider,
        model=model,
        **kwargs
    )
