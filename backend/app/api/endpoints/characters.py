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


@router.get("/novel/{novel_id}/relationships")
async def get_character_relationships(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取角色关系图谱数据
    返回节点和边的数据，用于可视化
    """
    service = CharacterService(db)
    characters = await service.list_characters(novel_id)
    
    # 构建节点和边
    nodes = []
    edges = []
    role_colors = {
        "protagonist": "#F59E0B",  # 黄色 - 主角
        "antagonist": "#EF4444",   # 红色 - 反派
        "supporting": "#3B82F6",   # 蓝色 - 配角
        "minor": "#6B7280",        # 灰色 - 龙套
    }
    
    # 创建节点
    for char in characters:
        nodes.append({
            "id": str(char.id),
            "name": char.name,
            "role": char.role_type.value if char.role_type else "minor",
            "color": role_colors.get(char.role_type.value if char.role_type else "minor", "#6B7280"),
            "firstAppearance": char.first_appearance,
            "profile": char.profile or {},
        })
        
        # 从profile中提取关系
        if char.profile and isinstance(char.profile, dict):
            relationships = char.profile.get("relationships", {})
            if isinstance(relationships, dict):
                for target_name, relation_type in relationships.items():
                    # 找到目标角色
                    target = next((c for c in characters if c.name == target_name), None)
                    if target:
                        edges.append({
                            "source": str(char.id),
                            "target": str(target.id),
                            "relation": relation_type,
                        })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total": len(nodes),
            "protagonist": len([n for n in nodes if n["role"] == "protagonist"]),
            "antagonist": len([n for n in nodes if n["role"] == "antagonist"]),
            "supporting": len([n for n in nodes if n["role"] == "supporting"]),
            "minor": len([n for n in nodes if n["role"] == "minor"]),
        }
    }
