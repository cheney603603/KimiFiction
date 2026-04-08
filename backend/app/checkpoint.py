"""
LangGraph Checkpoint 持久化系统
基于 Redis 实现工作流状态的断点续写
"""
from typing import Any, Dict, Optional
from loguru import logger

try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph import StateGraph, END
    from langgraph.types import Command, Interrupt
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    BaseCheckpointSaver = Any
    MemorySaver = Any
    logger.warning("LangGraph not available, using in-memory checkpoint only")


class RedisCheckpointSaver(BaseCheckpointSaver if LANGGRAPH_AVAILABLE else object):
    """
    Redis Checkpoint 持久化器
    
    包装 langgraph 的 MemorySaver，将其状态同时写入 Redis，
    实现跨进程、跨会话的持久化。
    
    使用场景：
    - 服务重启后恢复工作流状态
    - 断电后继续长篇小说写作
    - 多实例部署时的状态同步
    """
    
    def __init__(self, redis_client=None):
        self._memory_saver = MemorySaver() if LANGGRAPH_AVAILABLE else None
        self._redis = redis_client
        self._prefix = "lg_checkpoint:"
        self._ttl = 7 * 24 * 3600  # 7天过期
        logger.info("[RedisCheckpoint] 初始化完成（Redis+Memory双写）")
    
    async def _get_redis(self):
        """懒加载 Redis 连接"""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                from app.core.config import settings
                self._redis = aioredis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("[RedisCheckpoint] Redis连接已建立")
            except Exception as e:
                logger.warning(f"[RedisCheckpoint] Redis连接失败，将使用纯内存模式: {e}")
                self._redis = None
        return self._redis
    
    def _make_key(self, thread_id: str) -> str:
        return f"{self._prefix}{thread_id}"
    
    async def get(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        获取指定 thread_id 的 checkpoint
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None
        
        # 先尝试从 Redis 读取
        redis = await self._get_redis()
        if redis:
            try:
                key = self._make_key(thread_id)
                data = await redis.get(key)
                if data:
                    import json
                    checkpoint = json.loads(data)
                    logger.debug(f"[RedisCheckpoint] 命中Redis: thread={thread_id}")
                    return checkpoint
            except Exception as e:
                logger.warning(f"[RedisCheckpoint] Redis读取失败: {e}")
        
        # 降级到 MemorySaver
        if self._memory_saver:
            return await self._memory_saver.get(config)
        return None
    
    async def put(
        self,
        config: Dict[str, Any],
        checkpoint: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        保存 checkpoint（Redis + Memory 双写）
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        
        # 写入 MemorySaver
        if self._memory_saver:
            saved = await self._memory_saver.put(config, checkpoint, metadata)
        else:
            saved = checkpoint
        
        # 同时写入 Redis（异步，不阻塞主流程）
        redis = await self._get_redis()
        if redis:
            try:
                import json
                key = self._make_key(thread_id)
                data = json.dumps(checkpoint, ensure_ascii=False, default=str)
                await redis.set(key, data, ex=self._ttl)
                logger.debug(f"[RedisCheckpoint] 已写入Redis: thread={thread_id}, ttl={self._ttl}s")
            except Exception as e:
                logger.warning(f"[RedisCheckpoint] Redis写入失败（非阻塞）: {e}")
        
        return saved
    
    async def list(
        self,
        config: Dict[str, Any],
        limit: int = 10,
        before: Optional[Dict[str, Any]] = None
    ) -> list:
        """列出可用的 checkpoint"""
        if self._memory_saver:
            return await self._memory_saver.list(config, limit, before)
        return []
    
    async def delete(self, config: Dict[str, Any]) -> bool:
        """删除 checkpoint"""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return False
        
        if self._memory_saver:
            await self._memory_saver.delete(config)
        
        redis = await self._get_redis()
        if redis:
            try:
                key = self._make_key(thread_id)
                await redis.delete(key)
                logger.info(f"[RedisCheckpoint] 已删除: thread={thread_id}")
                return True
            except Exception as e:
                logger.warning(f"[RedisCheckpoint] Redis删除失败: {e}")
        return False
    
    async def get_all_threads(self) -> list:
        """获取所有保存的 thread_id"""
        redis = await self._get_redis()
        if not redis:
            return []
        try:
            keys = []
            async for key in redis.scan_iter(match=f"{self._prefix}*", count=100):
                thread_id = key[len(self._prefix):]
                keys.append(thread_id)
            return keys
        except Exception as e:
            logger.error(f"[RedisCheckpoint] 获取线程列表失败: {e}")
            return []


# 全局 checkpoint saver 实例
_checkpointer: Optional[RedisCheckpointSaver] = None


def get_checkpointer() -> Any:
    """获取全局 checkpointer"""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = RedisCheckpointSaver()
    return _checkpointer


def reset_checkpointer() -> None:
    """重置 checkpointer（用于测试）"""
    global _checkpointer
    _checkpointer = None
