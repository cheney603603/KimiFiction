"""
快照管理API - 支持查看LLM调用历史和系统回滚
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.state_snapshot import (
    StateSnapshotManager, SnapshotType, get_snapshot_manager
)
from app.core.security import get_current_user
from app.models.user import User


router = APIRouter(prefix="/snapshots", tags=["snapshots"])


# ============ 请求/响应模型 ============

class SnapshotListItem(BaseModel):
    """快照列表项"""
    snapshot_id: str
    type: str
    created_at: str
    description: str
    has_llm_call: bool


class LLMCallInfo(BaseModel):
    """LLM调用信息"""
    call_id: str
    timestamp: str
    agent_name: str
    model: str
    input_preview: str
    output_preview: str
    tokens_used: Optional[int]
    duration_ms: Optional[int]
    error: Optional[str]


class DatabaseStateInfo(BaseModel):
    """数据库状态信息"""
    chapter_count: int
    entity_count: int
    latest_chapter_number: Optional[int]


class SnapshotDetail(BaseModel):
    """快照详情"""
    snapshot_id: str
    novel_id: int
    type: str
    created_at: str
    description: str
    llm_call: Optional[LLMCallInfo]
    database_state: Optional[DatabaseStateInfo]
    git_commit: Optional[str]
    git_dirty_files: List[str]
    workflow_state: Optional[dict]


class RollbackRequest(BaseModel):
    """回滚请求"""
    snapshot_id: str
    confirm: bool = False  # 需要显式确认


class RollbackResponse(BaseModel):
    """回滚响应"""
    success: bool
    message: str
    details: dict


class CompareSnapshotsRequest(BaseModel):
    """对比快照请求"""
    snapshot_id_1: str
    snapshot_id_2: str


class CompareSnapshotsResponse(BaseModel):
    """对比快照响应"""
    snapshot_1: SnapshotDetail
    snapshot_2: SnapshotDetail
    differences: dict


# ============ API端点 ============

@router.get("/novel/{novel_id}", response_model=List[SnapshotListItem])
async def list_snapshots(
    novel_id: int,
    snapshot_type: Optional[str] = Query(None, description="快照类型过滤"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user)
):
    """
    获取小说的快照列表
    
    支持按类型过滤：llm_call, chapter_start, chapter_end, manual, auto
    """
    manager = get_snapshot_manager(novel_id)
    
    type_filter = None
    if snapshot_type:
        try:
            type_filter = SnapshotType(snapshot_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的快照类型: {snapshot_type}")
    
    snapshots = await manager.list_snapshots(
        snapshot_type=type_filter,
        limit=limit
    )
    
    return [
        SnapshotListItem(
            snapshot_id=s["snapshot_id"],
            type=s["type"],
            created_at=s["created_at"],
            description=s["description"],
            has_llm_call=s.get("has_llm_call", False)
        )
        for s in snapshots
    ]


@router.get("/novel/{novel_id}/{snapshot_id}", response_model=SnapshotDetail)
async def get_snapshot_detail(
    novel_id: int,
    snapshot_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取快照详情"""
    manager = get_snapshot_manager(novel_id)
    snapshot = await manager.get_snapshot(snapshot_id)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")
    
    # 构建LLM调用信息
    llm_call_info = None
    if snapshot.llm_call:
        call = snapshot.llm_call
        input_preview = ""
        if call.input_messages:
            # 提取最后一条用户消息作为预览
            for msg in reversed(call.input_messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    input_preview = content[:200] + "..." if len(content) > 200 else content
                    break
        
        output_preview = ""
        if call.output_content:
            output_preview = call.output_content[:300] + "..." if len(call.output_content) > 300 else call.output_content
        
        llm_call_info = LLMCallInfo(
            call_id=call.call_id,
            timestamp=call.timestamp,
            agent_name=call.agent_name,
            model=call.model,
            input_preview=input_preview,
            output_preview=output_preview,
            tokens_used=call.tokens_used,
            duration_ms=call.duration_ms,
            error=call.error
        )
    
    # 构建数据库状态信息
    db_state_info = None
    if snapshot.database_state:
        db = snapshot.database_state
        db_state_info = DatabaseStateInfo(
            chapter_count=db.chapter_count,
            entity_count=db.entity_count,
            latest_chapter_number=db.latest_chapter_number
        )
    
    return SnapshotDetail(
        snapshot_id=snapshot.snapshot_id,
        novel_id=snapshot.novel_id,
        type=snapshot.type,
        created_at=snapshot.created_at,
        description=snapshot.description,
        llm_call=llm_call_info,
        database_state=db_state_info,
        git_commit=snapshot.git_commit,
        git_dirty_files=snapshot.git_dirty_files,
        workflow_state=snapshot.workflow_state
    )


@router.get("/novel/{novel_id}/{snapshot_id}/llm-call/full")
async def get_llm_call_full(
    novel_id: int,
    snapshot_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取LLM调用的完整输入输出
    
    用于前端展示完整的prompt和response
    """
    manager = get_snapshot_manager(novel_id)
    snapshot = await manager.get_snapshot(snapshot_id)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")
    
    if not snapshot.llm_call:
        raise HTTPException(status_code=404, detail="该快照不包含LLM调用记录")
    
    call = snapshot.llm_call
    return {
        "call_id": call.call_id,
        "timestamp": call.timestamp,
        "agent_name": call.agent_name,
        "model": call.model,
        "input_messages": call.input_messages,
        "output_content": call.output_content,
        "tokens_used": call.tokens_used,
        "duration_ms": call.duration_ms,
        "error": call.error
    }


@router.post("/novel/{novel_id}/rollback", response_model=RollbackResponse)
async def rollback_to_snapshot(
    novel_id: int,
    request: RollbackRequest,
    current_user: User = Depends(get_current_user)
):
    """
    回滚到指定快照
    
    ⚠️ 危险操作：会删除快照之后创建的所有章节和数据
    需要设置 confirm=true 才会真正执行
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="回滚是危险操作，请设置 confirm=true 确认执行"
        )
    
    manager = get_snapshot_manager(novel_id)
    
    # 检查快照是否存在
    snapshot = await manager.get_snapshot(request.snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在")
    
    # 执行回滚
    result = await manager.rollback_to_snapshot(request.snapshot_id)
    
    return RollbackResponse(
        success=result["success"],
        message=result["message"],
        details=result["details"]
    )


@router.post("/novel/{novel_id}/compare", response_model=CompareSnapshotsResponse)
async def compare_snapshots(
    novel_id: int,
    request: CompareSnapshotsRequest,
    current_user: User = Depends(get_current_user)
):
    """对比两个快照的差异"""
    manager = get_snapshot_manager(novel_id)
    
    snapshot1 = await manager.get_snapshot(request.snapshot_id_1)
    snapshot2 = await manager.get_snapshot(request.snapshot_id_2)
    
    if not snapshot1 or not snapshot2:
        raise HTTPException(status_code=404, detail="快照不存在")
    
    # 计算差异
    differences = {
        "chapter_diff": 0,
        "entity_diff": 0,
        "time_diff_seconds": 0,
        "llm_calls_between": 0
    }
    
    if snapshot1.database_state and snapshot2.database_state:
        differences["chapter_diff"] = (
            snapshot2.database_state.chapter_count - 
            snapshot1.database_state.chapter_count
        )
        differences["entity_diff"] = (
            snapshot2.database_state.entity_count - 
            snapshot1.database_state.entity_count
        )
    
    # 时间差
    from datetime import datetime
    try:
        t1 = datetime.fromisoformat(snapshot1.created_at)
        t2 = datetime.fromisoformat(snapshot2.created_at)
        differences["time_diff_seconds"] = abs((t2 - t1).total_seconds())
    except:
        pass
    
    # 获取两个快照之间的LLM调用数
    all_snapshots = await manager.list_snapshots(limit=1000)
    llm_calls_between = 0
    in_range = False
    for s in sorted(all_snapshots, key=lambda x: x["created_at"]):
        if s["snapshot_id"] == request.snapshot_id_1:
            in_range = True
        elif s["snapshot_id"] == request.snapshot_id_2:
            break
        elif in_range and s["type"] == SnapshotType.LLM_CALL.value:
            llm_calls_between += 1
    
    differences["llm_calls_between"] = llm_calls_between
    
    # 构建详情
    def build_detail(snapshot):
        return SnapshotDetail(
            snapshot_id=snapshot.snapshot_id,
            novel_id=snapshot.novel_id,
            type=snapshot.type,
            created_at=snapshot.created_at,
            description=snapshot.description,
            llm_call=None,  # 简化版不返回完整LLM调用
            database_state=DatabaseStateInfo(
                chapter_count=snapshot.database_state.chapter_count,
                entity_count=snapshot.database_state.entity_count,
                latest_chapter_number=snapshot.database_state.latest_chapter_number
            ) if snapshot.database_state else None,
            git_commit=snapshot.git_commit,
            git_dirty_files=snapshot.git_dirty_files,
            workflow_state=None
        )
    
    return CompareSnapshotsResponse(
        snapshot_1=build_detail(snapshot1),
        snapshot_2=build_detail(snapshot2),
        differences=differences
    )


@router.delete("/novel/{novel_id}/{snapshot_id}")
async def delete_snapshot(
    novel_id: int,
    snapshot_id: str,
    current_user: User = Depends(get_current_user)
):
    """删除快照"""
    manager = get_snapshot_manager(novel_id)
    
    success = await manager.delete_snapshot(snapshot_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")
    
    return {"success": True, "message": f"快照 {snapshot_id} 已删除"}


@router.post("/novel/{novel_id}/manual")
async def create_manual_snapshot(
    novel_id: int,
    description: str = Query(..., description="快照描述"),
    current_user: User = Depends(get_current_user)
):
    """手动创建快照"""
    from app.core.state_snapshot import SnapshotType
    
    manager = get_snapshot_manager(novel_id)
    
    snapshot = await manager.create_snapshot(
        snapshot_type=SnapshotType.MANUAL,
        description=description,
        workflow_state={"created_by": current_user.username}
    )
    
    return {
        "success": True,
        "snapshot_id": snapshot.snapshot_id,
        "created_at": snapshot.created_at
    }
