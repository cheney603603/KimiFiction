"""
实体管理API
提供小说世界实体的CRUD操作
支持类型：character(角色), faction(势力), skill(功法), item(物品), location(地点)
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete

from app.core.database import get_db
from app.models.entity import Entity, EntityType, EntityRelationship
from app.schemas.entity import (
    EntityCreate,
    EntityUpdate,
    EntityResponse,
    EntityListResponse,
    EntityRelationshipCreate,
    EntityRelationshipResponse,
)

router = APIRouter()


@router.post("", response_model=EntityResponse)
async def create_entity(
    entity_data: EntityCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新实体"""
    import uuid
    import json

    entity_id = f"ent_{uuid.uuid4().hex[:8]}"
    entity = Entity(
        entity_id=entity_id,
        novel_id=entity_data.novel_id,
        canonical_name=entity_data.canonical_name,
        aliases=json.dumps(entity_data.aliases or [], ensure_ascii=False),
        entity_type=EntityType(entity_data.entity_type),
        state_vector=json.dumps(entity_data.state_vector or {}, ensure_ascii=False),
        narrative_summary=entity_data.narrative_summary,
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return entity.to_dict()


@router.get("/novel/{novel_id}", response_model=EntityListResponse)
async def list_entities(
    novel_id: int,
    entity_type: Optional[str] = Query(None, description="按实体类型筛选: character, faction, skill, item, location"),
    db: AsyncSession = Depends(get_db)
):
    """获取小说的实体列表"""
    query = select(Entity).where(Entity.novel_id == novel_id)
    if entity_type:
        query = query.where(Entity.entity_type == EntityType(entity_type))

    result = await db.execute(query)
    entities = result.scalars().all()
    return {
        "items": [e.to_dict() for e in entities],
        "total": len(entities)
    }


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取实体详情"""
    result = await db.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")
    return entity.to_dict()


@router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: str,
    entity_data: EntityUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新实体信息"""
    import json

    result = await db.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")

    if entity_data.canonical_name is not None:
        entity.canonical_name = entity_data.canonical_name
    if entity_data.aliases is not None:
        entity.aliases = json.dumps(entity_data.aliases, ensure_ascii=False)
    if entity_data.entity_type is not None:
        entity.entity_type = EntityType(entity_data.entity_type)
    if entity_data.state_vector is not None:
        entity.state_vector = json.dumps(entity_data.state_vector, ensure_ascii=False)
    if entity_data.narrative_summary is not None:
        entity.narrative_summary = entity_data.narrative_summary

    await db.commit()
    await db.refresh(entity)
    return entity.to_dict()


@router.delete("/batch")
async def batch_delete_entities(
    ids: str = Query(..., description="逗号分隔的实体ID列表，如: ent_abc123,ent_def456"),
    db: AsyncSession = Depends(get_db)
):
    """批量删除实体"""
    import json

    entity_id_list = [eid.strip() for eid in ids.split(",") if eid.strip()]
    if not entity_id_list:
        raise HTTPException(status_code=400, detail="未提供有效的实体ID列表")

    #获取所有实体所属novel_id并删除关系
    for eid in entity_id_list:
        result = await db.execute(select(Entity).where(Entity.entity_id == eid))
        entity = result.scalar_one_or_none()
        if entity:
            await db.execute(
                delete(EntityRelationship).where(
                    and_(
                        (EntityRelationship.source_id == eid) | (EntityRelationship.target_id == eid)
                    )
                )
            )

    await db.execute(
        delete(Entity).where(Entity.entity_id.in_(entity_id_list))
    )
    await db.commit()
    return {"message": f"已删除 {len(entity_id_list)} 个实体", "deleted_ids": entity_id_list}


@router.delete("/{entity_id}")
async def delete_entity(
    entity_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除实体及其关系"""
    result = await db.execute(
        select(Entity).where(Entity.entity_id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")

    # 删除相关关系
    await db.execute(
        delete(EntityRelationship).where(
            and_(
                EntityRelationship.novel_id == entity.novel_id,
                (EntityRelationship.source_id == entity_id) | (EntityRelationship.target_id == entity_id)
            )
        )
    )

    await db.delete(entity)
    await db.commit()
    return {"message": "实体已删除"}


# ===== 实体关系API =====

@router.post("/relationships", response_model=EntityRelationshipResponse)
async def create_relationship(
    rel_data: EntityRelationshipCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建实体关系"""
    rel = EntityRelationship(
        novel_id=rel_data.novel_id,
        source_id=rel_data.source_id,
        target_id=rel_data.target_id,
        relation_type=rel_data.relation_type,
    )
    db.add(rel)
    await db.commit()
    await db.refresh(rel)
    return rel.to_dict()


@router.get("/novel/{novel_id}/relationships")
async def list_relationships(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取小说的所有实体关系"""
    result = await db.execute(
        select(EntityRelationship).where(EntityRelationship.novel_id == novel_id)
    )
    rels = result.scalars().all()
    return {"items": [r.to_dict() for r in rels], "total": len(rels)}
