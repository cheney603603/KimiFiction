"""
小说管理API
提供小说的CRUD操作
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.novel_service import NovelService
from app.schemas.novel import (
    NovelCreate,
    NovelUpdate,
    NovelResponse,
    NovelListResponse,
    NovelDetailResponse,
)

router = APIRouter()


@router.post("", response_model=NovelResponse)
async def create_novel(
    novel_data: NovelCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新小说项目"""
    service = NovelService(db)
    novel = await service.create_novel(novel_data)
    return novel


@router.get("", response_model=NovelListResponse)
async def list_novels(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取小说列表"""
    service = NovelService(db)
    novels, total = await service.list_novels(skip=skip, limit=limit, status=status)
    return {
        "items": novels,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{novel_id}", response_model=NovelDetailResponse)
async def get_novel(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取小说详情"""
    service = NovelService(db)
    novel = await service.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    return novel


@router.put("/{novel_id}", response_model=NovelResponse)
async def update_novel(
    novel_id: int,
    novel_data: NovelUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新小说信息"""
    service = NovelService(db)
    novel = await service.update_novel(novel_id, novel_data)
    if not novel:
        raise HTTPException(status_code=404, detail="小说不存在")
    return novel


@router.delete("/{novel_id}")
async def delete_novel(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除小说（软删除）"""
    service = NovelService(db)
    success = await service.delete_novel(novel_id)
    if not success:
        raise HTTPException(status_code=404, detail="小说不存在")
    return {"message": "小说已删除"}


@router.get("/{novel_id}/stats")
async def get_novel_stats(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取小说统计信息"""
    service = NovelService(db)
    stats = await service.get_novel_stats(novel_id)
    if not stats:
        raise HTTPException(status_code=404, detail="小说不存在")
    return stats
