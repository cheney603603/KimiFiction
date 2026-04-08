"""
任务队列管理模块
使用Redis作为消息队列，支持后台异步任务
"""
import json
import asyncio
from typing import Optional, Callable, Any
from datetime import datetime
from enum import Enum
from loguru import logger

from app.core.redis_client import get_redis


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskQueue:
    """任务队列管理器"""
    
    QUEUE_KEY = "novel:task_queue"
    TASK_PREFIX = "novel:task:"
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
    
    async def enqueue(
        self,
        task_type: str,
        payload: dict,
        priority: TaskPriority = TaskPriority.NORMAL,
        delay: int = 0
    ) -> str:
        """
        添加任务到队列
        
        Args:
            task_type: 任务类型
            payload: 任务数据
            priority: 优先级
            delay: 延迟执行秒数
            
        Returns:
            任务ID
        """
        import uuid
        
        task_id = str(uuid.uuid4())
        task_data = {
            "id": task_id,
            "type": task_type,
            "payload": payload,
            "priority": priority.value,
            "status": TaskStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "retry_count": 0,
        }
        
        redis = await get_redis()
        
        # 存储任务详情
        await redis.setex(
            f"{self.TASK_PREFIX}{task_id}",
            86400 * 7,  # 7天过期
            json.dumps(task_data)
        )
        
        # 添加到队列（使用优先级分数）
        score = priority.value * 1000000000
        if delay > 0:
            score += delay
        
        await redis.zadd(self.QUEUE_KEY, {task_id: score})
        
        logger.info(f"任务已加入队列: {task_id}, 类型: {task_type}, 优先级: {priority.name}")
        
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务详情"""
        redis = await get_redis()
        data = await redis.get(f"{self.TASK_PREFIX}{task_id}")
        if data:
            return json.loads(data)
        return None
    
    async def update_task(self, task_id: str, updates: dict):
        """更新任务状态"""
        task = await self.get_task(task_id)
        if not task:
            return False
        
        task.update(updates)
        
        redis = await get_redis()
        await redis.setex(
            f"{self.TASK_PREFIX}{task_id}",
            86400 * 7,
            json.dumps(task)
        )
        return True
    
    async def dequeue(self) -> Optional[dict]:
        """从队列取出一个任务"""
        redis = await get_redis()
        
        # 获取最高优先级的任务
        result = await redis.zpopmax(self.QUEUE_KEY, count=1)
        if not result:
            return None
        
        task_id = result[0][0]
        task = await self.get_task(task_id)
        
        if task and task["status"] == TaskStatus.PENDING.value:
            return task
        
        return None
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._handlers[task_type] = handler
        logger.info(f"注册任务处理器: {task_type}")
    
    async def start_worker(self, concurrency: int = 2):
        """启动工作进程"""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop(concurrency))
        logger.info(f"任务队列工作进程已启动，并发数: {concurrency}")
    
    async def stop_worker(self):
        """停止工作进程"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("任务队列工作进程已停止")
    
    async def _worker_loop(self, concurrency: int):
        """工作进程主循环"""
        semaphore = asyncio.Semaphore(concurrency)
        
        while self._running:
            try:
                task = await self.dequeue()
                if not task:
                    await asyncio.sleep(1)
                    continue
                
                # 使用信号量限制并发
                asyncio.create_task(self._process_task_with_semaphore(task, semaphore))
                
            except Exception as e:
                logger.error(f"工作进程错误: {e}")
                await asyncio.sleep(1)
    
    async def _process_task_with_semaphore(self, task: dict, semaphore: asyncio.Semaphore):
        """使用信号量处理任务"""
        async with semaphore:
            await self._process_task(task)
    
    async def _process_task(self, task: dict):
        """处理单个任务"""
        task_id = task["id"]
        task_type = task["type"]
        
        handler = self._handlers.get(task_type)
        if not handler:
            logger.error(f"未找到任务处理器: {task_type}")
            await self.update_task(task_id, {
                "status": TaskStatus.FAILED.value,
                "error": f"Unknown task type: {task_type}",
                "completed_at": datetime.now().isoformat()
            })
            return
        
        # 更新状态为运行中
        await self.update_task(task_id, {
            "status": TaskStatus.RUNNING.value,
            "started_at": datetime.now().isoformat()
        })
        
        try:
            # 执行处理器
            result = await handler(task["payload"])
            
            # 更新为完成状态
            await self.update_task(task_id, {
                "status": TaskStatus.COMPLETED.value,
                "completed_at": datetime.now().isoformat(),
                "result": result
            })
            
            logger.info(f"任务完成: {task_id}")
            
        except Exception as e:
            logger.error(f"任务执行失败: {task_id}, 错误: {e}")
            
            # 检查是否需要重试
            retry_count = task.get("retry_count", 0)
            if retry_count < 3:
                await self.update_task(task_id, {
                    "status": TaskStatus.PENDING.value,
                    "retry_count": retry_count + 1,
                    "error": str(e)
                })
                # 重新加入队列，延迟5秒
                redis = await get_redis()
                await redis.zadd(self.QUEUE_KEY, {task_id: TaskPriority.NORMAL.value * 1000000000 + 5})
            else:
                await self.update_task(task_id, {
                    "status": TaskStatus.FAILED.value,
                    "completed_at": datetime.now().isoformat(),
                    "error": str(e)
                })


# 全局任务队列实例
task_queue = TaskQueue()


# 任务处理器注册装饰器
def task_handler(task_type: str):
    """任务处理器装饰器"""
    def decorator(func: Callable):
        task_queue.register_handler(task_type, func)
        return func
    return decorator
