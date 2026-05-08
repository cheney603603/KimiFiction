"""
实体召回引擎 (Module C)
根据当前段落涉及的实体，召回状态卡片、关系邻居、最近提及段落
"""
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass
from loguru import logger

from app.services.entity_store_service import EntityStoreService
from app.rag_system import HierarchicalRAG
from app.core.vector_store import vector_store


@dataclass
class ContextChunk:
    """上下文块"""
    content: str
    source: Literal["entity_state", "entity_rel", "rag_entity_mention"]
    priority: int
    paragraph_id: Optional[int] = None
    chapter_number: Optional[int] = None
    entity_id: Optional[str] = None


class EntityRetrievalService:
    """实体召回服务"""

    def __init__(self, novel_id: int):
        self.novel_id = novel_id
        self.store = EntityStoreService(novel_id)
        self.rag = HierarchicalRAG(novel_id)

    async def retrieve_for_entities(
        self,
        current_paragraph: str,
        active_entities: List[str],
        paragraph_id: Optional[int] = None,
        top_k_per_entity: int = 3
    ) -> List[ContextChunk]:
        """
        为当前段落涉及的实体召回上下文

        召回策略（按优先级）：
        1. 实体当前状态卡片（最高优先级 priority=1）
        2. 1跳关系邻居的当前状态（priority=2）
        3. 该实体在RAG库中最近提及的段落（priority=3）
        """
        chunks: List[ContextChunk] = []

        if not active_entities:
            active_entities = await self._detect_entities_in_paragraph(
                current_paragraph
            )

        for entity_id in active_entities:
            entity_data = await self._get_entity_data(entity_id)
            if not entity_data:
                continue

            # 1. 实体当前状态卡片
            state_card = self._build_state_card(entity_data)
            if state_card:
                chunks.append(ContextChunk(
                    content=state_card,
                    source="entity_state",
                    priority=1,
                    paragraph_id=entity_data.get("last_mentioned_paragraph_id"),
                    chapter_number=entity_data.get("last_mentioned_chapter_number"),
                    entity_id=entity_id
                ))

            # 2. 1跳关系邻居
            neighbors = await self.store.get_relationship_neighbors(entity_id)
            for neighbor in neighbors:
                neighbor_card = self._build_state_card(
                    neighbor,
                    is_neighbor=True,
                    relation_to=entity_data.get("canonical_name")
                )
                if neighbor_card:
                    chunks.append(ContextChunk(
                        content=neighbor_card,
                        source="entity_rel",
                        priority=2,
                        paragraph_id=neighbor.get("last_mentioned_paragraph_id"),
                        chapter_number=neighbor.get("last_mentioned_chapter_number"),
                        entity_id=neighbor.get("entity_id")
                    ))

            # 3. RAG中最近提及的段落
            rag_mentions = await self._retrieve_rag_mentions(
                entity_name=entity_data.get("canonical_name", ""),
                aliases=entity_data.get("aliases", []),
                top_k=top_k_per_entity
            )
            for mention in rag_mentions:
                mention_text = mention.get("content", "")
                if mention_text:
                    annotated = self._annotate_with_state_warning(
                        mention_text,
                        mention.get("metadata", {}),
                        entity_data
                    )
                    chunks.append(ContextChunk(
                        content=annotated,
                        source="rag_entity_mention",
                        priority=3,
                        paragraph_id=mention.get("paragraph_id"),
                        chapter_number=mention.get("chapter_number"),
                        entity_id=entity_id
                    ))

        chunks.sort(key=lambda x: x.priority)
        return chunks

    async def _detect_entities_in_paragraph(self, paragraph: str) -> List[str]:
        """从段落中检测涉及的实体ID（简单关键词匹配）"""
        entities = await self.store.get_all_entities()
        matched = []
        for e in entities:
            name = e.get("canonical_name", "")
            aliases = e.get("aliases", [])
            all_names = [name] + aliases
            for n in all_names:
                if n and n in paragraph:
                    matched.append(e.get("entity_id"))
                    break
        return matched

    async def _get_entity_data(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """获取实体数据"""
        entities = await self.store.get_entities_by_ids([entity_id])
        return entities[0] if entities else None

    def _build_state_card(
        self,
        entity_data: Dict[str, Any],
        is_neighbor: bool = False,
        relation_to: Optional[str] = None
    ) -> Optional[str]:
        """构建实体状态卡片文本"""
        name = entity_data.get("canonical_name", "未知")
        entity_type = entity_data.get("entity_type", "unknown")
        state = entity_data.get("state_vector", {})
        summary = entity_data.get("narrative_summary", "")

        if not state and not summary:
            return None

        type_label = {
            "character": "角色",
            "faction": "势力",
            "skill": "功法",
            "item": "物品",
            "location": "地点"
        }.get(entity_type, entity_type)

        header = f"【{type_label}】{name}"
        if is_neighbor and relation_to:
            header += f" (与 {relation_to} 有关联)"

        parts = [header]
        if state:
            parts.append("状态:")
            for k, v in state.items():
                parts.append(f"  - {k}: {v}")

        if summary:
            parts.append(f"摘要: {summary}")

        last_ch = entity_data.get("last_mentioned_chapter_number")
        if last_ch:
            parts.append(f"(最后提及: 第{last_ch}章)")

        return "\n".join(parts)

    async def _retrieve_rag_mentions(
        self,
        entity_name: str,
        aliases: List[str],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """从RAG库中检索最近提及该实体的段落"""
        try:
            from app.services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService()

            query_vector = await embedding_service.get_embedding(entity_name)
            if not query_vector:
                return []

            filters = {"novel_id": self.novel_id}
            results = await vector_store.search(
                query_vector=query_vector,
                top_k=top_k * 3,
                filters=filters
            )

            mentions = []
            all_names = set([entity_name] + [a for a in aliases if a])

            for r in results:
                payload = r.payload
                content = payload.get("content", "")
                contains_entity = any(name in content for name in all_names)
                if not contains_entity:
                    continue

                mentions.append({
                    "content": content,
                    "score": r.score,
                    "metadata": payload.get("metadata", {}),
                    "chapter_number": payload.get("chapter_number"),
                    "paragraph_id": payload.get("metadata", {}).get("paragraph_id")
                })

                if len(mentions) >= top_k:
                    break

            return mentions

        except Exception as e:
            logger.error(f"[EntityRetrieval] RAG search failed: {e}")
            return []

    def _annotate_with_state_warning(
        self,
        mention_text: str,
        mention_metadata: Dict[str, Any],
        current_entity_data: Dict[str, Any]
    ) -> str:
        """
        如果RAG段落中的实体状态与当前状态冲突，添加标注
        """
        mention_chapter = mention_metadata.get("chapter_number")
        current_chapter = current_entity_data.get("last_mentioned_chapter_number")

        if mention_chapter and current_chapter and mention_chapter < current_chapter:
            name = current_entity_data.get("canonical_name", "")
            current_state = current_entity_data.get("state_vector", {})
            current_state_str = ", ".join(
                [f"{k}={v}" for k, v in list(current_state.items())[:3]]
            )
            warning = (
                f"[历史段落-注意：此处\"{name}\"状态可能为旧状态"
                f"（段落章节#{mention_chapter}），"
                f"当前最新状态为{current_state_str}（第{current_chapter}章）]\n"
            )
            return warning + mention_text

        return mention_text
