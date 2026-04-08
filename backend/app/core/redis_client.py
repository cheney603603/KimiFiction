"""
Redis客户端管理模块
用于会话状态缓存和临时数据存储
"""
import json
import pickle
from datetime import datetime, date
from typing import Optional, Any, Union, List, Dict
import redis.asyncio as redis
from loguru import logger

from app.core.config import settings


class JSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理datetime等特殊类型"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)

# 全局Redis连接池
_redis_pool: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """获取Redis连接"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info(f"Redis连接已创建: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    return _redis_pool


async def close_redis():
    """关闭Redis连接"""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis连接已关闭")


class RedisCache:
    """Redis缓存操作类"""
    
    @staticmethod
    async def set(
        key: str,
        value: Union[str, dict, list],
        expire: int = 3600,
        use_json: bool = True
    ) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间(秒)，默认1小时
            use_json: 是否使用JSON序列化
        """
        try:
            r = await get_redis()
            if use_json and isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, cls=JSONEncoder)
            await r.setex(key, expire, value)
            return True
        except Exception as e:
            logger.error(f"Redis设置缓存失败: {e}")
            return False
    
    @staticmethod
    async def get(key: str, use_json: bool = True) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            use_json: 是否使用JSON反序列化
        """
        try:
            r = await get_redis()
            value = await r.get(key)
            if value is None:
                return None
            if use_json:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            logger.error(f"Redis获取缓存失败: {e}")
            return None
    
    @staticmethod
    async def delete(key: str) -> bool:
        """删除缓存"""
        try:
            r = await get_redis()
            await r.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis删除缓存失败: {e}")
            return False
    
    @staticmethod
    async def exists(key: str) -> bool:
        """检查键是否存在"""
        try:
            r = await get_redis()
            return await r.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis检查键失败: {e}")
            return False
    
    @staticmethod
    async def set_object(key: str, obj: Any, expire: int = 3600) -> bool:
        """使用pickle序列化存储Python对象"""
        try:
            r = await get_redis()
            # 使用不同的连接（decode_responses=False）来存储二进制数据
            r_binary = redis.from_url(settings.redis_url, decode_responses=False)
            pickled = pickle.dumps(obj)
            await r_binary.setex(key, expire, pickled)
            await r_binary.close()
            return True
        except Exception as e:
            logger.error(f"Redis存储对象失败: {e}")
            return False
    
    @staticmethod
    async def get_object(key: str) -> Optional[Any]:
        """使用pickle反序列化获取Python对象"""
        try:
            r_binary = redis.from_url(settings.redis_url, decode_responses=False)
            value = await r_binary.get(key)
            await r_binary.close()
            if value is None:
                return None
            return pickle.loads(value)
        except Exception as e:
            logger.error(f"Redis获取对象失败: {e}")
            return None


# 会话状态管理
class SessionManager:
    """会话状态管理器"""
    
    SESSION_PREFIX = "novel:session:"
    SESSION_EXPIRE = 86400 * 7  # 7天
    
    @classmethod
    def _make_key(cls, session_id: str) -> str:
        return f"{cls.SESSION_PREFIX}{session_id}"
    
    @classmethod
    async def save_state(cls, session_id: str, state: dict) -> bool:
        """保存会话状态"""
        key = cls._make_key(session_id)
        return await RedisCache.set(key, state, expire=cls.SESSION_EXPIRE)
    
    @classmethod
    async def get_state(cls, session_id: str) -> Optional[dict]:
        """获取会话状态"""
        key = cls._make_key(session_id)
        return await RedisCache.get(key)
    
    @classmethod
    async def delete_state(cls, session_id: str) -> bool:
        """删除会话状态"""
        key = cls._make_key(session_id)
        return await RedisCache.delete(key)


# ===== 工作流状态管理增强 =====

class WorkflowStateManager:
    """
    工作流状态管理器
    提供工作流级别的状态持久化和恢复
    """
    
    WORKFLOW_PREFIX = "workflow:state:"
    WORKFLOW_EXPIRE = 86400 * 30  # 30天
    
    # 快照保留数量
    SNAPSHOT_LIMIT = 10
    
    @classmethod
    def _make_key(cls, workflow_id: str) -> str:
        return f"{cls.WORKFLOW_PREFIX}{workflow_id}"
    
    @classmethod
    def _snapshot_key(cls, workflow_id: str, snapshot_id: str) -> str:
        return f"{cls.WORKFLOW_PREFIX}{workflow_id}:snapshot:{snapshot_id}"
    
    @classmethod
    async def save_state(cls, workflow_id: str, state: dict) -> bool:
        """
        保存工作流状态
        
        Args:
            workflow_id: 工作流ID
            state: 状态字典
            
        Returns:
            是否成功
        """
        key = cls._make_key(workflow_id)
        
        # 添加元数据
        state["_saved_at"] = str(__import__('datetime').datetime.now().isoformat())
        
        return await RedisCache.set(key, state, expire=cls.WORKFLOW_EXPIRE)
    
    @classmethod
    async def get_state(cls, workflow_id: str) -> Optional[dict]:
        """
        获取工作流状态
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            状态字典
        """
        key = cls._make_key(workflow_id)
        return await RedisCache.get(key)
    
    @classmethod
    async def create_snapshot(cls, workflow_id: str, reason: str = "manual") -> Optional[str]:
        """
        创建状态快照
        
        用于错误恢复前的备份
        
        Args:
            workflow_id: 工作流ID
            reason: 快照原因
            
        Returns:
            快照ID
        """
        state = await cls.get_state(workflow_id)
        if not state:
            return None
        
        import time
        snapshot_id = f"{int(time.time())}_{reason}"
        key = cls._snapshot_key(workflow_id, snapshot_id)
        
        state["_snapshot_id"] = snapshot_id
        state["_snapshot_reason"] = reason
        
        # 使用更长的过期时间
        await RedisCache.set(key, state, expire=cls.WORKFLOW_EXPIRE * 2)
        
        # 清理旧快照
        await cls._cleanup_snapshots(workflow_id)
        
        logger.info(f"创建工作流快照: {workflow_id}, id={snapshot_id}")
        return snapshot_id
    
    @classmethod
    async def restore_snapshot(cls, workflow_id: str, snapshot_id: str) -> bool:
        """
        从快照恢复
        
        Args:
            workflow_id: 工作流ID
            snapshot_id: 快照ID
            
        Returns:
            是否成功
        """
        key = cls._snapshot_key(workflow_id, snapshot_id)
        snapshot = await RedisCache.get(key)
        
        if not snapshot:
            logger.warning(f"快照不存在: {workflow_id}, {snapshot_id}")
            return False
        
        # 恢复状态（移除快照元数据）
        state = {k: v for k, v in snapshot.items() if not k.startswith("_snapshot")}
        await cls.save_state(workflow_id, state)
        
        logger.info(f"恢复工作流快照: {workflow_id}, id={snapshot_id}")
        return True
    
    @classmethod
    async def list_snapshots(cls, workflow_id: str) -> List[dict]:
        """列出所有快照"""
        r = await get_redis()
        pattern = f"{cls.WORKFLOW_PREFIX}{workflow_id}:snapshot:*"
        
        try:
            keys = await r.keys(pattern)
            snapshots = []
            
            for key in keys:
                # 从key中提取snapshot_id
                parts = key.split(":")
                if len(parts) >= 4:
                    snapshot_id = ":".join(parts[3:])  # 处理包含冒号的ID
                    snapshot = {
                        "snapshot_id": snapshot_id,
                        "key": key,
                    }
                    snapshots.append(snapshot)
            
            # 按时间排序（新的在前）
            snapshots.sort(key=lambda x: x["snapshot_id"], reverse=True)
            return snapshots
            
        except Exception as e:
            logger.error(f"列出快照失败: {e}")
            return []
    
    @classmethod
    async def _cleanup_snapshots(cls, workflow_id: str) -> None:
        """清理旧快照"""
        snapshots = await cls.list_snapshots(workflow_id)
        
        if len(snapshots) > cls.SNAPSHOT_LIMIT:
            # 删除最旧的
            to_delete = snapshots[cls.SNAPSHOT_LIMIT:]
            r = await get_redis()
            
            for snapshot in to_delete:
                await r.delete(snapshot["key"])
            
            logger.info(f"清理旧快照: {workflow_id}, 删除{len(to_delete)}个")
    
    @classmethod
    async def delete_workflow(cls, workflow_id: str) -> bool:
        """删除工作流及其所有快照"""
        r = await get_redis()
        
        # 删除主状态
        main_key = cls._make_key(workflow_id)
        await r.delete(main_key)
        
        # 删除所有快照
        pattern = f"{cls.WORKFLOW_PREFIX}{workflow_id}:snapshot:*"
        keys = await r.keys(pattern)
        if keys:
            await r.delete(*keys)
        
        logger.info(f"删除工作流: {workflow_id}")
        return True
    
    @classmethod
    async def get_workflow_list(cls) -> List[dict]:
        """获取所有工作流列表"""
        r = await get_redis()
        pattern = f"{cls.WORKFLOW_PREFIX}*"
        
        try:
            keys = await r.keys(pattern)
            workflows = []
            
            for key in keys:
                if ":snapshot:" not in key:
                    state = await RedisCache.get(key.replace(cls.WORKFLOW_PREFIX, ""))
                    if state:
                        workflows.append({
                            "workflow_id": key.replace(cls.WORKFLOW_PREFIX, ""),
                            "phase": state.get("current_phase", "unknown"),
                            "updated_at": state.get("_saved_at", ""),
                        })
            
            return workflows
            
        except Exception as e:
            logger.error(f"获取工作流列表失败: {e}")
            return []


class WorkflowLogsManager:
    """
    工作流执行日志管理器
    存储在Redis中，支持实时推送和历史查询
    """
    LOG_PREFIX = "workflow_logs:"
    MAX_LOGS = 100  # 每个工作流最多保留100条日志

    @classmethod
    def _log_key(cls, workflow_id: str) -> str:
        return f"{cls.LOG_PREFIX}{workflow_id}"

    @classmethod
    async def add_log(
        cls,
        workflow_id: str,
        level: str,  # info, warning, error, success
        message: str,
        step: str = "",
        extra: Optional[dict] = None
    ) -> None:
        """
        添加一条日志
        
        Args:
            workflow_id: 工作流ID
            level: 日志级别 (info, warning, error, success)
            message: 日志消息
            step: 当前步骤
            extra: 额外数据
        """
        import time
        log_entry = {
            "timestamp": time.time(),
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
            "step": step,
            "extra": extra or {},
        }
        
        try:
            r = await get_redis()
            key = cls._log_key(workflow_id)
            await r.lpush(key, json.dumps(log_entry, ensure_ascii=False))
            await r.ltrim(key, 0, cls.MAX_LOGS - 1)
            await r.expire(key, 7 * 24 * 3600)
            
            # 打印到控制台
            level_prefix = {"info": "💬", "warning": "⚠️", "error": "❌", "success": "✅"}.get(level, "📝")
            step_str = f"[{step}] " if step else ""
            logger.info(f"{level_prefix} {step_str}{message}")
            
        except Exception as e:
            logger.error(f"保存工作流日志失败: {e}")

    @classmethod
    async def get_logs(cls, workflow_id: str, limit: int = 50) -> List[dict]:
        """获取日志列表"""
        try:
            r = await get_redis()
            key = cls._log_key(workflow_id)
            raw_logs = await r.lrange(key, 0, limit - 1)
            return [json.loads(log) for log in raw_logs]
        except Exception as e:
            logger.error(f"读取工作流日志失败: {e}")
            return []

    @classmethod
    async def clear_logs(cls, workflow_id: str) -> None:
        """清空日志"""
        try:
            r = await get_redis()
            await r.delete(cls._log_key(workflow_id))
        except Exception as e:
            logger.error(f"清空工作流日志失败: {e}")

