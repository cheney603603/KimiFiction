"""
小说管理API
提供小说的CRUD操作
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import require_auth, get_current_user
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
    """软删除小说"""
    service = NovelService(db)
    success = await service.delete_novel(novel_id)
    if not success:
        raise HTTPException(status_code=404, detail="小说不存在")
    return {"message": "小说已删除"}


@router.delete("/{novel_id}/hard")
async def hard_delete_novel(
    novel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth)
):
    """
    彻底删除小说（级联删除数据库记录、本地文件、Qdrant 向量数据）
    二级确认：前端需先弹出确认对话框再调用此接口
    """
    service = NovelService(db)
    result = await service.hard_delete_novel(novel_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["detail"])
    return result


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


@router.get("/{novel_id}/world")
async def get_novel_world(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    获取小说世界观聚合数据（实体图谱/小说地图/知识库共用）
    返回实体、角色、关系、记忆节点、大纲等全部世界设定数据
    """
    from sqlalchemy import select

    from app.models.entity import Entity, EntityRelationship
    from app.models.character import Character
    from app.models.memory_node import MemoryNode
    from app.models.outline import Outline

    def key_of(e: Entity) -> str:
        """实体类型的小写 key（兼容 CHARACTER/Skill 等历史存储大小写）"""
        raw = e.entity_type.value if hasattr(e, "entity_type") else str(getattr(e, "entity_type", ""))
        try:
            return str(getattr(e.entity_type, "value", raw)).lower()
        except Exception:
            return str(raw).lower()

    entities = (await db.execute(
        select(Entity).where(Entity.novel_id == novel_id)
    )).scalars().all()

    relationships = (await db.execute(
        select(EntityRelationship).where(EntityRelationship.novel_id == novel_id)
    )).scalars().all()

    characters = (await db.execute(
        select(Character).where(Character.novel_id == novel_id)
    )).scalars().all()

    memory_nodes = (await db.execute(
        select(MemoryNode).where(MemoryNode.novel_id == novel_id)
    )).scalars().all()

    outlines = (await db.execute(
        select(Outline).where(Outline.novel_id == novel_id).order_by(Outline.volume_number)
    )).scalars().all()

    # 从角色 profile.relationships 提取关系边（与 /characters/novel/{id}/relationships 同构）
    character_edges = []
    char_by_name = {c.name: c for c in characters}
    for c in characters:
        profile = c.profile or {}
        rels = profile.get("relationships")
        if not isinstance(rels, dict):
            continue
        for target_name, relation in rels.items():
            target = char_by_name.get(target_name)
            if target:
                character_edges.append({
                    "source": str(c.id),
                    "target": str(target.id),
                    "relation": str(relation),
                })

    counted = {"character": 0, "faction": 0, "location": 0, "item": 0, "skill": 0}
    for e in entities:
        # 统一用小写 key 归类，兼容历史以大写(CHARACTER)落库的数据，避免拆成两个桶虚增。
        k = key_of(e)
        if k in counted:
            counted[k] += 1

    # 去重：同一 canonical_name 的 character 实体可能被实体抽取重复入库。
    # 角色概览按“唯一名称”统计，避免与 characters 表角色重复计数而虚高。
    unique_char_names = {e.canonical_name for e in entities if key_of(e) == "character"}
    counted["character"] = min(counted["character"], len(unique_char_names) or counted["character"])
    if unique_char_names:
        counted["character"] = len(unique_char_names)

    return {
        "novel_id": novel_id,
        "entities": [e.to_dict() for e in entities],
        "relationships": [r.to_dict() for r in relationships],
        "characters": [c.to_dict() for c in characters],
        "character_edges": character_edges,
        "memory_nodes": [m.to_dict() for m in memory_nodes],
        "outlines": [o.to_dict() for o in outlines],
        "counts": {
            **counted,
            "characters_db": len(characters),
            "relationships": len(relationships),
            "memory_nodes": len(memory_nodes),
            "outlines": len(outlines),
        },
    }
