"""
LLM调用追踪器 - 自动记录每次LLM调用并创建快照

使用方式：
1. 装饰器模式: @track_llm_call(agent_name="writer")
2. 上下文管理器: with LLMCallTracker(novel_id, agent_name): ...
"""

import time
import functools
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass
from contextvars import ContextVar
from loguru import logger

from app.core.state_snapshot import (
    StateSnapshotManager, SnapshotType, LLMCallRecord
)


# 当前小说ID上下文（用于自动关联）
current_novel_id: ContextVar[Optional[int]] = ContextVar("current_novel_id", default=None)
current_chapter_number: ContextVar[Optional[int]] = ContextVar("current_chapter_number", default=None)


@dataclass
class LLMCallContext:
    """LLM调用上下文"""
    novel_id: int
    chapter_number: Optional[int]
    agent_name: str
    workflow_state: Optional[Dict] = None


def set_novel_context(novel_id: int, chapter_number: Optional[int] = None):
    """设置当前小说上下文"""
    current_novel_id.set(novel_id)
    current_chapter_number.set(chapter_number)


def clear_novel_context():
    """清除小说上下文"""
    current_novel_id.set(None)
    current_chapter_number.set(None)


def get_current_novel_id() -> Optional[int]:
    """获取当前小说ID"""
    return current_novel_id.get()


def get_current_chapter_number() -> Optional[int]:
    """获取当前章节号"""
    return current_chapter_number.get()


class LLMCallTracker:
    """LLM调用追踪器 - 上下文管理器模式"""
    
    def __init__(
        self,
        novel_id: Optional[int] = None,
        agent_name: str = "unknown",
        model: str = "unknown",
        description: str = "",
        workflow_state: Optional[Dict] = None,
        create_snapshot: bool = True
    ):
        self.novel_id = novel_id or current_novel_id.get()
        self.chapter_number = current_chapter_number.get()
        self.agent_name = agent_name
        self.model = model
        self.description = description or f"{agent_name} LLM调用"
        self.workflow_state = workflow_state
        self.create_snapshot = create_snapshot
        
        self.call_id: Optional[str] = None
        self.start_time: Optional[float] = None
        self.input_messages: Optional[List[Dict]] = None
        self.output_content: Optional[str] = None
        self.error: Optional[str] = None
        
        self._snapshot_manager: Optional[StateSnapshotManager] = None
    
    async def __aenter__(self):
        """进入上下文 - 创建快照"""
        if not self.novel_id:
            logger.warning("[LLMTracker] 未设置novel_id，跳过快照")
            return self
        
        self.start_time = time.time()
        self._snapshot_manager = StateSnapshotManager(self.novel_id)
        
        logger.debug(f"[LLMTracker] 开始追踪: {self.agent_name}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文 - 记录调用并创建快照"""
        if not self._snapshot_manager:
            return
        
        duration_ms = int((time.time() - self.start_time) * 1000) if self.start_time else None
        
        # 如果有异常，记录错误
        if exc_val:
            self.error = str(exc_val)
        
        # 构建调用记录
        call_record = LLMCallRecord(
            call_id=self._generate_call_id(),
            timestamp=self._get_timestamp(),
            agent_name=self.agent_name,
            model=self.model,
            input_messages=self.input_messages or [],
            output_content=self.output_content,
            duration_ms=duration_ms,
            error=self.error
        )
        
        # 创建工作流状态
        workflow_state = self.workflow_state or {}
        workflow_state.update({
            "agent_name": self.agent_name,
            "chapter_number": self.chapter_number,
            "call_id": call_record.call_id,
            "has_error": self.error is not None
        })
        
        # 创建快照
        if self.create_snapshot:
            try:
                snapshot = await self._snapshot_manager.create_snapshot(
                    snapshot_type=SnapshotType.LLM_CALL,
                    description=self.description,
                    llm_call=call_record,
                    workflow_state=workflow_state
                )
                logger.info(
                    f"[LLMTracker] 快照创建: {snapshot.snapshot_id} "
                    f"({self.agent_name}, {duration_ms}ms)"
                )
            except Exception as e:
                logger.error(f"[LLMTracker] 快照创建失败: {e}")
        
        # 记录调用日志
        self._log_call(call_record)
    
    def record_input(self, messages: List[Dict[str, Any]]):
        """记录输入消息"""
        self.input_messages = messages
    
    def record_output(self, content: str, tokens_used: Optional[int] = None):
        """记录输出内容"""
        self.output_content = content
        self.tokens_used = tokens_used
    
    def _generate_call_id(self) -> str:
        """生成调用ID"""
        import hashlib
        import time
        timestamp = str(time.time())
        return f"call_{hashlib.md5(timestamp.encode()).hexdigest()[:12]}"
    
    def _get_timestamp(self) -> str:
        """获取ISO格式时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _log_call(self, record: LLMCallRecord):
        """记录调用日志"""
        status = "ERROR" if record.error else "SUCCESS"
        logger.info(
            f"[LLMCall] {status} | {record.agent_name} | "
            f"{record.model} | {record.duration_ms}ms | {record.call_id}"
        )


def track_llm_call(
    agent_name: str,
    model: Optional[str] = None,
    description: Optional[str] = None,
    create_snapshot: bool = True
):
    """
    LLM调用追踪装饰器
    
    使用示例:
        @track_llm_call(agent_name="writer", model="gpt-4o")
        async def generate_chapter(self, context):
            # ... LLM调用
            return result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 尝试从参数中提取novel_id
            novel_id = _extract_novel_id(args, kwargs)
            
            # 获取模型名
            model_name = model or _extract_model_name(args)
            
            # 构建描述
            desc = description or f"{agent_name}.{func.__name__}"
            
            # 使用追踪器
            tracker = LLMCallTracker(
                novel_id=novel_id,
                agent_name=agent_name,
                model=model_name,
                description=desc,
                create_snapshot=create_snapshot
            )
            
            async with tracker:
                try:
                    # 记录输入（如果可能）
                    if "messages" in kwargs:
                        tracker.record_input(kwargs["messages"])
                    elif len(args) > 0 and isinstance(args[0], list):
                        tracker.record_input(args[0])
                    
                    # 执行函数
                    result = await func(*args, **kwargs)
                    
                    # 记录输出
                    if isinstance(result, str):
                        tracker.record_output(result)
                    elif isinstance(result, dict) and "content" in result:
                        tracker.record_output(result["content"])
                    
                    return result
                    
                except Exception as e:
                    tracker.error = str(e)
                    raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步函数不支持自动追踪，需要手动使用上下文管理器
            logger.warning(f"[LLMTracker] 同步函数不支持自动追踪: {func.__name__}")
            return func(*args, **kwargs)
        
        # 根据函数类型返回不同包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def _extract_novel_id(args, kwargs) -> Optional[int]:
    """从参数中提取novel_id"""
    # 从kwargs查找
    for key in ["novel_id", "novelId", "novelid"]:
        if key in kwargs:
            return kwargs[key]
    
    # 从args查找（假设self或第一个参数有novel_id属性）
    if args:
        first_arg = args[0]
        if hasattr(first_arg, "novel_id"):
            return first_arg.novel_id
        if isinstance(first_arg, dict):
            return first_arg.get("novel_id")
    
    # 使用上下文变量
    return current_novel_id.get()


def _extract_model_name(args) -> str:
    """从参数中提取模型名"""
    if args and hasattr(args[0], "model"):
        return getattr(args[0], "model", "unknown")
    return "unknown"


# ============ 手动追踪API ============

class ManualLLMTracker:
    """手动追踪API - 用于无法使用装饰器的场景"""
    
    def __init__(self, novel_id: int, agent_name: str):
        self.novel_id = novel_id
        self.agent_name = agent_name
        self._tracker: Optional[LLMCallTracker] = None
    
    async def start(self, description: str = "", model: str = "unknown"):
        """开始追踪"""
        self._tracker = LLMCallTracker(
            novel_id=self.novel_id,
            agent_name=self.agent_name,
            model=model,
            description=description
        )
        await self._tracker.__aenter__()
    
    def record_input(self, messages: List[Dict]):
        """记录输入"""
        if self._tracker:
            self._tracker.record_input(messages)
    
    def record_output(self, content: str, tokens_used: Optional[int] = None):
        """记录输出"""
        if self._tracker:
            self._tracker.record_output(content, tokens_used)
    
    async def end(self, error: Optional[str] = None):
        """结束追踪"""
        if self._tracker:
            if error:
                self._tracker.error = error
            await self._tracker.__aexit__(None, None, None)
            self._tracker = None


# 便捷函数
async def create_manual_snapshot(
    novel_id: int,
    description: str,
    snapshot_type: SnapshotType = SnapshotType.MANUAL,
    workflow_state: Optional[Dict] = None
) -> str:
    """
    手动创建快照
    
    Returns:
        snapshot_id
    """
    manager = StateSnapshotManager(novel_id)
    snapshot = await manager.create_snapshot(
        snapshot_type=snapshot_type,
        description=description,
        workflow_state=workflow_state
    )
    return snapshot.snapshot_id


async def get_snapshots(novel_id: int, limit: int = 50) -> List[Dict]:
    """获取快照列表"""
    manager = StateSnapshotManager(novel_id)
    return await manager.list_snapshots(limit=limit)


async def rollback_to_snapshot(novel_id: int, snapshot_id: str) -> Dict[str, Any]:
    """回滚到指定快照"""
    manager = StateSnapshotManager(novel_id)
    return await manager.rollback_to_snapshot(snapshot_id)
