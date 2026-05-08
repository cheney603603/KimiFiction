"""
上下文融合服务 (Module D)
使用RRF（Reciprocal Rank Fusion）融合RAG结果和实体召回结果
"""
from typing import List, Dict, Any
from dataclasses import dataclass
from loguru import logger

from app.services.entity_retrieval_service import ContextChunk


@dataclass
class FusionResult:
    """融合结果项"""
    content: str
    source: str
    score: float
    metadata: Dict[str, Any]


class ContextFusionService:
    """
    上下文融合服务

    使用RRF融合：
    - RAG结果 (weight=1.0)
    - 实体召回 (weight=1.5)
    - 实体状态 (weight=2.0)
    """

    RRF_K = 60

    SOURCE_WEIGHTS = {
        "rag": 1.0,
        "rag_entity_mention": 1.5,
        "entity_rel": 1.5,
        "entity_state": 2.0,
    }

    async def fuse_contexts(
        self,
        rag_results: Dict[str, Any],
        entity_results: List[ContextChunk],
        max_chunks: int = 15
    ) -> List[str]:
        """
        融合RAG结果和实体召回结果

        Args:
            rag_results: HierarchicalRAG.retrieve_for_writer 的输出
            entity_results: EntityRetrievalService.retrieve_for_entities 的输出
            max_chunks: 最大返回chunk数

        Returns:
            融合后的上下文文本列表（已按最终排序分组）
        """
        scored_items: List[FusionResult] = []

        # 处理RAG结果
        rag_chunks = rag_results.get("chunks", [])
        for rank, chunk in enumerate(rag_chunks):
            source = chunk.get("metadata", {}).get("source", "rag")
            if source not in self.SOURCE_WEIGHTS:
                source = "rag"

            rrf_score = self._rrf_score(rank) * self.SOURCE_WEIGHTS[source]
            content = self._format_rag_chunk(chunk)
            scored_items.append(FusionResult(
                content=content,
                source=source,
                score=rrf_score,
                metadata={"chunk": chunk, "rank": rank}
            ))

        # 处理实体召回结果
        for rank, chunk in enumerate(entity_results):
            source = chunk.source
            weight = self.SOURCE_WEIGHTS.get(source, 1.0)
            rrf_score = self._rrf_score(rank) * weight

            scored_items.append(FusionResult(
                content=chunk.content,
                source=source,
                score=rrf_score,
                metadata={
                    "entity_id": chunk.entity_id,
                    "priority": chunk.priority,
                    "paragraph_id": chunk.paragraph_id
                }
            ))

        # 去重
        deduped = self._deduplicate(scored_items)

        # 按分数排序
        deduped.sort(key=lambda x: x.score, reverse=True)

        # 取top_k
        final = deduped[:max_chunks]

        logger.info(
            f"[ContextFusion] {len(rag_chunks)} RAG chunks + "
            f"{len(entity_results)} entity chunks -> {len(final)} final chunks"
        )

        return self._format_final_context(final)

    def _rrf_score(self, rank: int) -> float:
        """计算RRF分数"""
        return 1.0 / (self.RRF_K + rank + 1)

    def _deduplicate(self, items: List[FusionResult]) -> List[FusionResult]:
        """基于内容去重"""
        seen_contents = set()
        result = []
        for item in items:
            key = item.content[:80].strip()
            if key in seen_contents:
                continue
            seen_contents.add(key)
            result.append(item)
        return result

    def _format_rag_chunk(self, chunk: Dict[str, Any]) -> str:
        """格式化RAG chunk为文本"""
        chunk_type = chunk.get("chunk_type", "unknown")
        content = chunk.get("content", "")
        chapter = chunk.get("chapter_number")

        type_labels = {
            "chapter_block": "前文段落",
            "plot_summary": "情节摘要",
            "character_moment": "角色时刻",
            "world_fact": "世界观",
            "mystery": "伏笔",
            "conflict": "冲突",
            "relationship": "关系"
        }
        label = type_labels.get(chunk_type, chunk_type)

        if chapter:
            return f"[{label}-第{chapter}章] {content[:400]}"
        return f"[{label}] {content[:400]}"

    def _format_final_context(self, items: List[FusionResult]) -> List[str]:
        """格式化最终上下文，按来源分组"""
        grouped: Dict[str, List[FusionResult]] = {}
        for item in items:
            src = item.source
            if src not in grouped:
                grouped[src] = []
            grouped[src].append(item)

        source_order = ["entity_state", "entity_rel", "rag_entity_mention", "rag"]

        result = []
        for src in source_order:
            if src not in grouped:
                continue
            items_group = grouped[src]

            group_titles = {
                "entity_state": "\n=== 实体当前状态 ===\n",
                "entity_rel": "\n=== 关联实体状态 ===\n",
                "rag_entity_mention": "\n=== 实体相关历史段落 ===\n",
                "rag": "\n=== 相关上下文 ===\n"
            }
            result.append(group_titles.get(src, f"\n=== {src} ===\n"))

            for item in items_group:
                result.append(item.content)

        return result
