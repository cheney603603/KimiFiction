"""
记忆管理API
提供记忆节点的CRUD和检索操作
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.memory_service import MemoryService
from app.schemas.memory import (
    MemoryNodeCreate,
    MemoryNodeUpdate,
    MemoryNodeResponse,
    MemorySearchRequest,
    MemorySearchResponse,
)

router = APIRouter()


@router.post("/nodes", response_model=MemoryNodeResponse)
async def create_memory_node(
    node_data: MemoryNodeCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建记忆节点"""
    service = MemoryService(db)
    node = await service.create_node(node_data)
    return node


@router.get("/nodes/novel/{novel_id}")
async def list_memory_nodes(
    novel_id: int,
    node_type: Optional[str] = Query(None),
    unresolved_only: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    """获取小说的记忆节点列表"""
    service = MemoryService(db)
    nodes = await service.list_nodes(novel_id, node_type, unresolved_only)
    return {"items": nodes, "total": len(nodes)}


@router.get("/nodes/{node_id}", response_model=MemoryNodeResponse)
async def get_memory_node(
    node_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取记忆节点详情"""
    service = MemoryService(db)
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="记忆节点不存在")
    return node


@router.put("/nodes/{node_id}", response_model=MemoryNodeResponse)
async def update_memory_node(
    node_id: int,
    node_data: MemoryNodeUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新记忆节点"""
    service = MemoryService(db)
    node = await service.update_node(node_id, node_data)
    if not node:
        raise HTTPException(status_code=404, detail="记忆节点不存在")
    return node


@router.delete("/nodes/{node_id}")
async def delete_memory_node(
    node_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除记忆节点"""
    service = MemoryService(db)
    success = await service.delete_node(node_id)
    if not success:
        raise HTTPException(status_code=404, detail="记忆节点不存在")
    return {"message": "记忆节点已删除"}


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(
    request: MemorySearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """语义搜索记忆节点"""
    service = MemoryService(db)
    results = await service.search_similar(request)
    return {
        "query": request.query,
        "results": results,
        "total": len(results)
    }


@router.post("/consolidate/{novel_id}")
async def consolidate_memory(
    novel_id: int,
    chapter_threshold: int = Query(50, description="章节数阈值"),
    db: AsyncSession = Depends(get_db)
):
    """整理记忆（压缩旧章节）"""
    service = MemoryService(db)
    result = await service.consolidate_memory(novel_id, chapter_threshold)
    return result


@router.get("/context/{novel_id}")
async def build_context(
    novel_id: int,
    chapter_number: int = Query(..., description="当前章节号"),
    db: AsyncSession = Depends(get_db)
):
    """构建写作上下文"""
    service = MemoryService(db)
    context = await service.build_context(novel_id, chapter_number)
    return context
