"""
进度追踪系统
用于跟踪工作流执行进度，支持WebSocket推送和前端轮询
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from loguru import logger

from app.core.redis_client import RedisCache


class ProgressStatus(str, Enum):
    """进度状态"""
    PENDING = "pending"          # 等待执行
    RUNNING = "running"          # 执行中
    LLM_CALLING = "llm_calling"  # 调用LLM中
    LLM_RESPONDED = "llm_responded"  # LLM已响应
    PROCESSING = "processing"    # 处理结果中
    COMPLETED = "completed"      # 完成
    FAILED = "failed"            # 失败
    TIMEOUT = "timeout"          # 超时


class ProgressStep:
    """进度步骤"""
    def __init__(
        self,
        step_id: str,
        name: str,
        description: str = "",
        total_substeps: int = 1
    ):
        self.step_id = step_id
        self.name = name
        self.description = description
        self.status = ProgressStatus.PENDING
        self.current_substep = 0
        self.total_substeps = total_substeps
        self.logs: List[Dict[str, Any]] = []
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "progress": f"{self.current_substep}/{self.total_substeps}",
            "progress_percent": int((self.current_substep / self.total_substeps) * 100) if self.total_substeps > 0 else 0,
            "logs": self.logs[-10:],  # 只保留最近10条日志
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }
    
    def start(self):
        """开始步骤"""
        self.status = ProgressStatus.RUNNING
        self.started_at = datetime.now()
        self.add_log("开始执行", "info")
    
    def set_status(self, status: ProgressStatus, message: str = ""):
        """设置状态"""
        self.status = status
        if message:
            self.add_log(message, "info")
    
    def update_substep(self, current: int, message: str = ""):
        """更新子步骤进度"""
        self.current_substep = current
        if message:
            self.add_log(message, "info")
    
    def add_log(self, message: str, level: str = "info", details: Dict = None):
        """添加日志"""
        self.logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "details": details or {}
        })
        # 同时输出到系统日志
        log_func = getattr(logger, level, logger.info)
        log_func(f"[{self.name}] {message}")
    
    def complete(self, message: str = "完成"):
        """完成步骤"""
        self.status = ProgressStatus.COMPLETED
        self.completed_at = datetime.now()
        self.add_log(message, "success")
    
    def fail(self, error: str):
        """失败"""
        self.status = ProgressStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()
        self.add_log(f"失败: {error}", "error")


class ProgressTracker:
    """进度追踪器"""
    
    def __init__(self, task_id: str, expire: int = 3600):
        self.task_id = task_id
        self.expire = expire
        self.steps: Dict[str, ProgressStep] = {}
        self.current_step_id: Optional[str] = None
        self._callbacks: List[Callable] = []
    
    def _get_key(self) -> str:
        return f"progress:{self.task_id}"
    
    async def _save(self):
        """保存到Redis"""
        data = self.to_dict()
        await RedisCache.set(self._get_key(), data, expire=self.expire)
    
    def add_step(
        self,
        step_id: str,
        name: str,
        description: str = "",
        total_substeps: int = 1
    ) -> ProgressStep:
        """添加步骤"""
        step = ProgressStep(step_id, name, description, total_substeps)
        self.steps[step_id] = step
        return step
    
    def get_step(self, step_id: str) -> Optional[ProgressStep]:
        """获取步骤"""
        return self.steps.get(step_id)
    
    def set_current_step(self, step_id: str):
        """设置当前步骤"""
        self.current_step_id = step_id
        if step_id in self.steps:
            self.steps[step_id].start()
    
    async def update_step_status(
        self,
        step_id: str,
        status: ProgressStatus,
        message: str = ""
    ):
        """更新步骤状态"""
        step = self.steps.get(step_id)
        if step:
            step.set_status(status, message)
            await self._save()
            await self._notify()
    
    async def update_substep(
        self,
        step_id: str,
        current: int,
        message: str = ""
    ):
        """更新子步骤"""
        step = self.steps.get(step_id)
        if step:
            step.update_substep(current, message)
            await self._save()
            await self._notify()
    
    async def add_log(
        self,
        step_id: str,
        message: str,
        level: str = "info",
        details: Dict = None
    ):
        """添加日志"""
        step = self.steps.get(step_id)
        if step:
            step.add_log(message, level, details)
            await self._save()
            await self._notify()
    
    async def complete_step(self, step_id: str, message: str = ""):
        """完成步骤"""
        step = self.steps.get(step_id)
        if step:
            step.complete(message)
            await self._save()
            await self._notify()
    
    async def fail_step(self, step_id: str, error: str):
        """步骤失败"""
        step = self.steps.get(step_id)
        if step:
            step.fail(error)
            await self._save()
            await self._notify()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "current_step": self.current_step_id,
            "steps": {k: v.to_dict() for k, v in self.steps.items()},
            "updated_at": datetime.now().isoformat(),
        }
    
    async def _notify(self):
        """通知所有回调"""
        data = self.to_dict()
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"进度通知失败: {e}")
    
    def on_update(self, callback: Callable):
        """注册更新回调"""
        self._callbacks.append(callback)
    
    @classmethod
    async def get_progress(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """从Redis获取进度"""
        key = f"progress:{task_id}"
        return await RedisCache.get(key)


# 全局进度追踪器缓存
_progress_trackers: Dict[str, ProgressTracker] = {}


def get_progress_tracker(task_id: str) -> ProgressTracker:
    """获取或创建进度追踪器"""
    if task_id not in _progress_trackers:
        _progress_trackers[task_id] = ProgressTracker(task_id)
    return _progress_trackers[task_id]


def remove_progress_tracker(task_id: str):
    """移除进度追踪器"""
    if task_id in _progress_trackers:
        del _progress_trackers[task_id]
