"""
实体状态库存储服务 (Module B)
提供实体的CRUD、状态更新、关系管理
"""
import json
import uuid
from typing import List, Dict, Any, Optional
from loguru import logger

from sqlalchemy import select, and_, or_, delete
from app.core.database import get_session
from app.models.entity import Entity, EntityRelationship, EntityType


class EntityStoreService:
    """实体状态存储服务"""

    def __init__(self, novel_id: int):
        self.novel_id = novel_id

    async def get_all_entities(self) -> List[Dict[str, Any]]:
        """获取小说所有实体"""
        async with get_session() as db:
            result = await db.execute(
                select(Entity).where(Entity.novel_id == self.novel_id)
            )
            entities = result.scalars().all()
            return [e.to_dict() for e in entities]

    async def get_entities_by_ids(self, entity_ids: List[str]) -> List[Dict[str, Any]]:
        """根据ID列表获取实体"""
        if not entity_ids:
            return []
        async with get_session() as db:
            result = await db.execute(
                select(Entity).where(
                    and_(Entity.novel_id == self.novel_id, Entity.entity_id.in_(entity_ids))
                )
            )
            entities = result.scalars().all()
            return [e.to_dict() for e in entities]

    async def get_entity_by_name(self, canonical_name: str) -> Optional[Dict[str, Any]]:
        """根据规范名称获取实体"""
        async with get_session() as db:
            result = await db.execute(
                select(Entity).where(
                    and_(
                        Entity.novel_id == self.novel_id,
                        Entity.canonical_name == canonical_name
                    )
                )
            )
            entity = result.scalar_one_or_none()
            return entity.to_dict() if entity else None

    async def find_entity_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """通过别名查找实体（模糊匹配）"""
        async with get_session() as db:
            result = await db.execute(
                select(Entity).where(
                    and_(
                        Entity.novel_id == self.novel_id,
                        Entity.canonical_name == alias
                    )
                )
            )
            entity = result.scalar_one_or_none()
            if entity:
                return entity.to_dict()

            result = await db.execute(
                select(Entity).where(Entity.novel_id == self.novel_id)
            )
            entities = result.scalars().all()
            for e in entities:
                aliases = json.loads(e.aliases) if e.aliases else []
                if alias in aliases:
                    return e.to_dict()
            return None

    async def create_or_update_entities(
        self,
        mentions,
        paragraph_id: int,
        chapter_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        根据抽取结果创建或更新实体

        Returns:
            更新后的实体列表
        """
        from app.services.entity_extraction_service import EntityMention

        updated = []
        async with get_session() as db:
            for mention in mentions:
                if not isinstance(mention, EntityMention):
                    continue

                existing = await self._find_matching_entity(db, mention)

                if existing:
                    entity = existing
                    current_aliases = json.loads(entity.aliases) if entity.aliases else []
                    new_aliases = [
                        a for a in mention.aliases
                        if a not in current_aliases and a != entity.canonical_name
                    ]
                    if new_aliases:
                        current_aliases.extend(new_aliases)
                        entity.aliases = json.dumps(current_aliases, ensure_ascii=False)

                    if mention.state_changes:
                        current_state = entity.get_state_dict()
                        current_state.update(mention.state_changes)
                        entity.set_state_dict(current_state)

                    entity.last_mentioned_paragraph_id = paragraph_id
                    if chapter_number:
                        entity.last_mentioned_chapter_number = chapter_number

                    if not entity.narrative_summary:
                        entity.narrative_summary = f"首次出现于段落#{paragraph_id}"

                    mention.entity_id = entity.entity_id
                    logger.info(
                        f"[EntityStore] 更新实体: {entity.canonical_name} ({entity.entity_id})"
                    )
                else:
                    entity_id = f"ent_{uuid.uuid4().hex[:8]}"
                    entity = Entity(
                        entity_id=entity_id,
                        novel_id=self.novel_id,
                        canonical_name=mention.canonical_name,
                        aliases=json.dumps(mention.aliases, ensure_ascii=False),
                        entity_type=EntityType(mention.entity_type),
                        state_vector=json.dumps(
                            mention.state_changes, ensure_ascii=False
                        ) if mention.state_changes else "{}",
                        narrative_summary=f"首次出现于段落#{paragraph_id}",
                        last_mentioned_paragraph_id=paragraph_id,
                        last_mentioned_chapter_number=chapter_number,
                    )
                    db.add(entity)
                    mention.entity_id = entity_id
                    logger.info(
                        f"[EntityStore] 创建新实体: {entity.canonical_name} ({entity_id})"
                    )

                updated.append(entity)

            await db.commit()
            for e in updated:
                await db.refresh(e)

            return [e.to_dict() for e in updated]

    async def _find_matching_entity(self, db, mention) -> Optional[Entity]:
        """在数据库会话中查找匹配的实体"""
        result = await db.execute(
            select(Entity).where(
                and_(
                    Entity.novel_id == self.novel_id,
                    Entity.canonical_name == mention.canonical_name
                )
            )
        )
        entity = result.scalar_one_or_none()
        if entity:
            return entity

        result = await db.execute(
            select(Entity).where(Entity.novel_id == self.novel_id)
        )
        entities = result.scalars().all()
        for e in entities:
            aliases = json.loads(e.aliases) if e.aliases else []
            if mention.canonical_name in aliases:
                return e
            for alias in mention.aliases:
                if alias == e.canonical_name or alias in aliases:
                    return e
        return None

    async def create_relationships(
        self,
        relations,
        entity_map: Dict[str, str],
        paragraph_id: Optional[int] = None,
        chapter_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """创建实体关系"""
        from app.services.entity_extraction_service import EntityRelationExtract

        created = []
        async with get_session() as db:
            for rel in relations:
                if not isinstance(rel, EntityRelationExtract):
                    continue

                source_id = entity_map.get(rel.source_name)
                target_id = entity_map.get(rel.target_name)

                if not source_id or not target_id:
                    logger.warning(
                        f"[EntityStore] 关系无法建立: {rel.source_name} -> {rel.target_name}"
                    )
                    continue

                result = await db.execute(
                    select(EntityRelationship).where(
                        and_(
                            EntityRelationship.novel_id == self.novel_id,
                            EntityRelationship.source_id == source_id,
                            EntityRelationship.target_id == target_id,
                            EntityRelationship.relation_type == rel.relation_type
                        )
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    continue

                rel_obj = EntityRelationship(
                    novel_id=self.novel_id,
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=rel.relation_type,
                    established_at_paragraph_id=paragraph_id,
                    established_at_chapter_number=chapter_number
                )
                db.add(rel_obj)
                created.append(rel_obj)

            await db.commit()
            return [r.to_dict() for r in created]

    async def get_entity_relationships(
        self, entity_id: str, hop: int = 1
    ) -> List[Dict[str, Any]]:
        """获取实体的关系邻居"""
        if hop != 1:
            raise NotImplementedError("仅支持1跳关系查询")

        async with get_session() as db:
            result = await db.execute(
                select(EntityRelationship).where(
                    and_(
                        EntityRelationship.novel_id == self.novel_id,
                        or_(
                            EntityRelationship.source_id == entity_id,
                            EntityRelationship.target_id == entity_id
                        )
                    )
                )
            )
            rels = result.scalars().all()
            return [r.to_dict() for r in rels]

    async def get_relationship_neighbors(
        self, entity_id: str
    ) -> List[Dict[str, Any]]:
        """获取关系邻居的实体状态"""
        rels = await self.get_entity_relationships(entity_id, hop=1)

        neighbor_ids = set()
        for r in rels:
            if r["source_id"] == entity_id:
                neighbor_ids.add(r["target_id"])
            else:
                neighbor_ids.add(r["source_id"])

        if not neighbor_ids:
            return []

        return await self.get_entities_by_ids(list(neighbor_ids))

    async def delete_novel_entities(self) -> bool:
        """删除小说的所有实体数据"""
        async with get_session() as db:
            await db.execute(
                delete(EntityRelationship).where(
                    EntityRelationship.novel_id == self.novel_id
                )
            )
            await db.execute(
                delete(Entity).where(Entity.novel_id == self.novel_id)
            )
            await db.commit()
            return True
