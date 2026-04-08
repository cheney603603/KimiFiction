"""
角色管理API
提供角色的CRUD操作
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.character_service import CharacterService
from app.workflow_engine import get_workflow_engine
from app.schemas.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterListResponse,
)

router = APIRouter()


@router.post("", response_model=CharacterResponse)
async def create_character(
    character_data: CharacterCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新角色"""
    service = CharacterService(db)
    character = await service.create_character(character_data)
    return character


@router.get("/novel/{novel_id}", response_model=CharacterListResponse)
async def list_characters(
    novel_id: int,
    role_type: Optional[str] = Query(None, description="按角色类型筛选"),
    db: AsyncSession = Depends(get_db)
):
    """获取小说的角色列表"""
    service = CharacterService(db)
    characters = await service.list_characters(novel_id, role_type)
    return {
        "items": characters,
        "total": len(characters)
    }


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取角色详情"""
    service = CharacterService(db)
    character = await service.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    return character


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: int,
    character_data: CharacterUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新角色信息"""
    service = CharacterService(db)
    character = await service.update_character(character_id, character_data)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    return character


@router.delete("/{character_id}")
async def delete_character(
    character_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除角色"""
    service = CharacterService(db)
    character = await service.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    success = await service.delete_character(character_id)

    if success:
        try:
            engine = await get_workflow_engine(character.novel_id)
            if engine.state and engine.state.characters:
                engine.state.characters = [
                    item for item in engine.state.characters
                    if item.get("id") != character_id and item.get("name") != character.name
                ]
                await engine.save_state()
        except Exception:
            pass

    return {"message": "角色已删除"}


@router.get("/{character_id}/timeline")
async def get_character_timeline(
    character_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取角色出场时间线"""
    service = CharacterService(db)
    timeline = await service.get_character_timeline(character_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return timeline
