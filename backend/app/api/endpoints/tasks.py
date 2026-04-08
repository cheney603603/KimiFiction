"""
任务管理API
查询任务状态和结果
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.task_queue import task_queue

router = APIRouter()


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    task = await task_queue.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 返回任务信息（不包含敏感数据）
    return {
        "task_id": task["id"],
        "type": task["type"],
        "status": task["status"],
        "created_at": task["created_at"],
        "started_at": task.get("started_at"),
        "completed_at": task.get("completed_at"),
        "result": task.get("result"),
        "error": task.get("error"),
        "retry_count": task.get("retry_count", 0),
    }
