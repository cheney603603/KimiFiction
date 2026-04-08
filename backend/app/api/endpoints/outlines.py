"""
大纲管理API
提供大纲的CRUD操作
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.outline_service import OutlineService
from app.schemas.outline import (
    OutlineCreate,
    OutlineUpdate,
    OutlineResponse,
    OutlineListResponse,
    OutlineGenerateRequest,
)

router = APIRouter()


@router.post("", response_model=OutlineResponse)
async def create_outline(
    outline_data: OutlineCreate,
    db: AsyncSession = Depends(get_db)
):
    """手动创建大纲"""
    service = OutlineService(db)
    outline = await service.create_outline(outline_data)
    return outline


@router.get("/novel/{novel_id}", response_model=OutlineListResponse)
async def list_outlines(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取小说的大纲列表"""
    service = OutlineService(db)
    outlines = await service.list_outlines(novel_id)
    return {
        "items": outlines,
        "total": len(outlines)
    }


@router.get("/{outline_id}", response_model=OutlineResponse)
async def get_outline(
    outline_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取大纲详情"""
    service = OutlineService(db)
    outline = await service.get_outline(outline_id)
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")
    return outline


@router.put("/{outline_id}", response_model=OutlineResponse)
async def update_outline(
    outline_id: int,
    outline_data: OutlineUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新大纲"""
    service = OutlineService(db)
    outline = await service.update_outline(outline_id, outline_data)
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")
    return outline


@router.delete("/{outline_id}")
async def delete_outline(
    outline_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除大纲"""
    service = OutlineService(db)
    success = await service.delete_outline(outline_id)
    if not success:
        raise HTTPException(status_code=404, detail="大纲不存在")
    return {"message": "大纲已删除"}


@router.post("/generate")
async def generate_outline(
    request: OutlineGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """生成大纲（调用AI）"""
    service = OutlineService(db)
    result = await service.generate_outline(request)
    return result
