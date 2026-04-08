"""
章节管理API
提供章节的CRUD和生成操作
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.chapter_service import ChapterService
from app.schemas.chapter import (
    ChapterCreate,
    ChapterUpdate,
    ChapterResponse,
    ChapterListResponse,
    ChapterGenerateRequest,
)

router = APIRouter()


@router.post("", response_model=ChapterResponse)
async def create_chapter(
    chapter_data: ChapterCreate,
    db: AsyncSession = Depends(get_db)
):
    """手动创建章节"""
    service = ChapterService(db)
    chapter = await service.create_chapter(chapter_data)
    return chapter


@router.get("/novel/{novel_id}", response_model=ChapterListResponse)
async def list_chapters(
    novel_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """获取小说的章节列表"""
    service = ChapterService(db)
    chapters, total = await service.list_chapters(
        novel_id=novel_id, skip=skip, limit=limit, status=status
    )
    return {
        "items": chapters,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取章节详情"""
    service = ChapterService(db)
    chapter = await service.get_chapter(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    return chapter


@router.get("/novel/{novel_id}/chapter/{chapter_number}")
async def get_chapter_by_number(
    novel_id: int,
    chapter_number: int,
    db: AsyncSession = Depends(get_db)
):
    """根据序号获取章节"""
    service = ChapterService(db)
    chapter = await service.get_chapter_by_number(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    return chapter


@router.put("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: int,
    chapter_data: ChapterUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新章节"""
    service = ChapterService(db)
    chapter = await service.update_chapter(chapter_id, chapter_data)
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    return chapter


@router.delete("/{chapter_id}")
async def delete_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除章节"""
    service = ChapterService(db)
    success = await service.delete_chapter(chapter_id)
    if not success:
        raise HTTPException(status_code=404, detail="章节不存在")
    return {"message": "章节已删除"}


@router.post("/generate")
async def generate_chapter(
    request: ChapterGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """生成新章节（调用AI）"""
    service = ChapterService(db)
    # 这里会触发异步生成任务
    result = await service.start_generation(request)
    return result


@router.get("/{chapter_id}/content")
async def get_chapter_content(
    chapter_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取章节纯文本内容（用于阅读）"""
    service = ChapterService(db)
    content = await service.get_chapter_content(chapter_id)
    if content is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    return {"content": content}
