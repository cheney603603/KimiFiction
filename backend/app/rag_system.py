"""
Hierarchical RAG System - 层次化RAG系统
为Writer Agent提供精准的上下文检索和召回能力

核心设计：
- 底层：章节级文本块（~512 tokens）
- 上层：情节摘要向量（BGE-large-zh）
- 融合检索：语义相似度 + 关键词匹配，支持多跳推理
"""
import json
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from loguru import logger

from app.core.vector_store import vector_store
from app.core.database import get_session
from app.services.embedding_service import EmbeddingService


class ChunkType(str, Enum):
    CHAPTER_BLOCK = "chapter_block"       # 章节正文块
    PLOT_SUMMARY = "plot_summary"          # 情节摘要
    CHARACTER_MOMENT = "character_moment"  # 角色关键时刻
    WORLD_FACT = "world_fact"              # 世界观事实
    MYSTERY = "mystery"                    # 伏笔/悬念
    CONFLICT = "conflict"                  # 冲突事件
    RELATIONSHIP = "relationship"          # 关系动态


@dataclass
class TextChunk:
    """文本块定义"""
    chunk_id: str
    novel_id: int
    chunk_type: ChunkType
    content: str
    tokens: int
    chapter_number: Optional[int] = None
    importance: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 向量相关
    vector_id: Optional[str] = None
    vector_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TextChunk":
        if isinstance(d.get("chunk_type"), str):
            d["chunk_type"] = ChunkType(d["chunk_type"])
        return cls(**d)


@dataclass
class HybridSearchResult:
    """混合检索结果"""
    chunks: List[TextChunk]
    total_score: float
    retrieval_method: str  # "semantic_only" | "keyword_only" | "hybrid"
    query: str


class ChunkingStrategy:
    """文本分块策略"""
    
    # 按类型设置目标块大小（tokens）
    CHUNK_SIZES = {
        ChunkType.CHAPTER_BLOCK: 512,
        ChunkType.PLOT_SUMMARY: 256,
        ChunkType.CHARACTER_MOMENT: 200,
        ChunkType.WORLD_FACT: 150,
        ChunkType.MYSTERY: 200,
        ChunkType.CONFLICT: 200,
        ChunkType.RELATIONSHIP: 200,
    }
    
    # 块之间重叠的tokens数
    OVERLAP_TOKENS = 50
    
    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """估算中文字符串的token数（粗略）"""
        chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
        english = len(re.findall(r'[a-zA-Z]+', text))
        punctuation = len(re.findall(r'[，。！？；：、""''（）《》【】]', text))
        return int(chinese * 1.2 + english * 0.25 + punctuation * 0.5)
    
    @classmethod
    def chunk_text(
        cls,
        text: str,
        chunk_type: ChunkType,
        novel_id: int,
        chapter_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[TextChunk]:
        """
        将文本按策略分块
        """
        target_tokens = cls.CHUNK_SIZES.get(chunk_type, 512)
        chunks = []
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if not paragraphs:
            return chunks
        
        current_chunk_text = ""
        current_tokens = 0
        chunk_index = 0
        
        for para in paragraphs:
            para_tokens = cls.estimate_tokens(para)
            
            if para_tokens > target_tokens * 1.5:
                if current_chunk_text:
                    chunks.append(cls._make_chunk(
                        current_chunk_text, current_tokens,
                        chunk_type, novel_id, chapter_number, metadata, chunk_index
                    ))
                    chunk_index += 1
                    current_chunk_text = ""
                    current_tokens = 0
                
                sentences = re.split(r'([。！？])', para)
                for i in range(0, len(sentences) - 1, 2):
                    sent = sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else "")
                    sent_tokens = cls.estimate_tokens(sent)
                    if current_tokens + sent_tokens <= target_tokens:
                        current_chunk_text += sent + ""
                        current_tokens += sent_tokens
                    else:
                        if current_chunk_text:
                            chunks.append(cls._make_chunk(
                                current_chunk_text, current_tokens,
                                chunk_type, novel_id, chapter_number, metadata, chunk_index
                            ))
                            chunk_index += 1
                        current_chunk_text = sent + ""
                        current_tokens = sent_tokens
                        
            elif current_tokens + para_tokens <= target_tokens:
                current_chunk_text += para + "\n"
                current_tokens += para_tokens
            else:
                chunks.append(cls._make_chunk(
                    current_chunk_text, current_tokens,
                    chunk_type, novel_id, chapter_number, metadata, chunk_index
                ))
                chunk_index += 1
                if cls.OVERLAP_TOKENS > 0 and current_chunk_text:
                    overlap_text = cls._get_overlap_text(current_chunk_text, cls.OVERLAP_TOKENS)
                    current_chunk_text = overlap_text + para + "\n"
                    current_tokens = cls.estimate_tokens(current_chunk_text)
                else:
                    current_chunk_text = para + "\n"
                    current_tokens = para_tokens
        
        if current_chunk_text.strip():
            chunks.append(cls._make_chunk(
                current_chunk_text, current_tokens,
                chunk_type, novel_id, chapter_number, metadata, chunk_index
            ))
        
        return chunks
    
    @classmethod
    def _make_chunk(
        cls,
        content: str,
        tokens: int,
        chunk_type: ChunkType,
        novel_id: int,
        chapter_number: Optional[int],
        metadata: Optional[Dict[str, Any]],
        index: int
    ) -> TextChunk:
        chunk_id = hashlib.sha256(
            f"{novel_id}_{chapter_number}_{chunk_type.value}_{index}_{content[:100]}".encode()
        ).hexdigest()[:16]
        return TextChunk(
            chunk_id=chunk_id,
            novel_id=novel_id,
            chunk_type=chunk_type,
            content=content.strip(),
            tokens=tokens,
            chapter_number=chapter_number,
            importance=1.0,
            metadata=metadata or {}
        )
    
    @classmethod
    def _get_overlap_text(cls, text: str, overlap_tokens: int) -> str:
        target_chars = int(overlap_tokens * 0.8)
        search_start = max(0, len(text) - target_chars - 50)
        search_text = text[search_start:]
        for sep in ["。", "！", "？", "；", "，", "\n"]:
            pos = search_text.rfind(sep)
            if pos > 0:
                return search_text[pos + 1:]
        return search_text[-target_chars:]


class HybridRetriever:
    """
    混合检索器
    融合语义相似度和关键词匹配，支持多跳推理
    """
    
    SEMANTIC_WEIGHT = 0.6
    KEYWORD_WEIGHT = 0.4
    
    def __init__(self):
        self.retriever.embedding_service = EmbeddingService()
    
    async def retrieve(
        self,
        novel_id: int,
        query: str,
        top_k: int = 8,
        chunk_types: Optional[List[ChunkType]] = None,
        chapter_range: Optional[Tuple[int, int]] = None,
        min_score: float = 0.3,
        multi_hop: bool = True,
    ) -> HybridSearchResult:
        if not query or not query.strip():
            return HybridSearchResult(chunks=[], total_score=0.0, retrieval_method="empty_query", query=query)
        
        filters = {"novel_id": novel_id}
        if chunk_types:
            filters["chunk_type"] = [ct.value for ct in chunk_types]
        
        semantic_chunks = await self._semantic_search(query, filters, top_k * 2)
        keyword_chunks = await self._keyword_search(query, filters, top_k * 2)
        fused = self._fuse_results(semantic_chunks, keyword_chunks)
        
        if multi_hop and fused:
            extended = await self._multi_hop_expand(novel_id, fused[:3], filters, top_k // 2)
            all_chunks = {c.chunk_id: c for c in fused}
            for c in extended:
                if c.chunk_id not in all_chunks:
                    all_chunks[c.chunk_id] = c
            fused = list(all_chunks.values())
        
        results = [c for c in fused if c.vector_score and c.vector_score >= min_score][:top_k]
        total_score = sum(c.vector_score or 0 for c in results)
        
        method = "hybrid"
        if not semantic_chunks and keyword_chunks:
            method = "keyword_only"
        elif not keyword_chunks and semantic_chunks:
            method = "semantic_only"
        
        return HybridSearchResult(
            chunks=results,
            total_score=total_score,
            retrieval_method=method,
            query=query
        )
    
    async def _semantic_search(
        self,
        query: str,
        filters: Dict[str, Any],
        top_k: int
    ) -> List[TextChunk]:
        try:
            query_vector = await self.retriever.embedding_service.get_embedding(query)
            if not query_vector:
                return []
            
            search_results = await vector_store.search(
                query_vector=query_vector,
                top_k=top_k,
                filters=filters
            )
            
            chunks = []
            for r in search_results:
                payload = r.payload
                chunk = TextChunk(
                    chunk_id=payload.get("chunk_id", r.id),
                    novel_id=payload.get("novel_id", 0),
                    chunk_type=ChunkType(payload.get("chunk_type", "chapter_block")),
                    content=payload.get("content", ""),
                    tokens=payload.get("tokens", 0),
                    chapter_number=payload.get("chapter_number"),
                    importance=payload.get("importance", 1.0),
                    metadata=payload.get("metadata", {}),
                    vector_id=r.id,
                    vector_score=r.score,
                )
                chunks.append(chunk)
            return chunks
        except Exception as e:
            logger.error(f"语义检索失败: {e}")
            return []
    
    async def _keyword_search(
        self,
        query: str,
        filters: Dict[str, Any],
        top_k: int
    ) -> List[TextChunk]:
        keywords = self._extract_keywords(query)
        if not keywords:
            return []
        
        try:
            async with get_session() as db:
                from app.services.memory_service import MemoryService
                memory_service = MemoryService(db)
                nodes = await memory_service.list_nodes(
                    novel_id=filters.get("novel_id", 0),
                    node_type=filters.get("chunk_type"),
                )
                scored = []
                for node in nodes:
                    content = node.content.lower()
                    score = sum(1 for kw in keywords if kw.lower() in content)
                    if score > 0:
                        normalized = score / max(len(keywords), 1)
                        chunk = TextChunk(
                            chunk_id=f"mem_{node.id}",
                            novel_id=node.novel_id,
                            chunk_type=ChunkType(
                                node.node_type.value if hasattr(node.node_type, 'value') else str(node.node_type)
                            ),
                            content=node.content,
                            tokens=ChunkingStrategy.estimate_tokens(node.content),
                            chapter_number=node.specific_chapter,
                            importance=node.importance_score,
                            vector_score=normalized,
                        )
                        scored.append(chunk)
                scored.sort(key=lambda x: x.vector_score or 0, reverse=True)
                return scored[:top_k]
        except Exception as e:
            logger.error(f"关键词检索失败: {e}")
            return []
    
    def _extract_keywords(self, text: str) -> List[str]:
        stop_words = {
            "的", "一", "个", "是", "在", "了", "和", "也", "而", "所",
            "不", "上", "下", "中", "内", "这", "那", "这个", "那个",
            "the", "a", "an", "and", "or", "but", "in", "on", "at",
            "我", "你", "他", "她", "它", "我们", "你们", "他们"
        }
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        english_words = re.findall(r'[a-zA-Z]{3,}', text.lower())
        keywords = [w for w in chinese_words if w not in stop_words][:20]
        keywords += [w for w in english_words if w not in stop_words][:10]
        return keywords
    
    def _fuse_results(
        self,
        semantic: List[TextChunk],
        keyword: List[TextChunk]
    ) -> List[TextChunk]:
        score_map: Dict[str, Tuple[float, TextChunk]] = {}
        max_semantic = max((c.vector_score or 0) for c in semantic) if semantic else 1.0
        for c in semantic:
            norm_score = (c.vector_score or 0) / max_semantic
            score_map[c.chunk_id] = (norm_score * self.SEMANTIC_WEIGHT, c)
        
        max_keyword = max((c.vector_score or 0) for c in keyword) if keyword else 1.0
        for c in keyword:
            norm_score = (c.vector_score or 0) / max_keyword
            if c.chunk_id in score_map:
                old_score, _ = score_map[c.chunk_id]
                score_map[c.chunk_id] = (old_score + norm_score * self.KEYWORD_WEIGHT, c)
            else:
                score_map[c.chunk_id] = (norm_score * self.KEYWORD_WEIGHT, c)
        
        sorted_chunks = sorted(score_map.values(), key=lambda x: x[0], reverse=True)
        result = []
        for score, chunk in sorted_chunks:
            chunk.vector_score = score
            result.append(chunk)
        return result
    
    async def _multi_hop_expand(
        self,
        novel_id: int,
        seed_chunks: List[TextChunk],
        filters: Dict[str, Any],
        top_k: int
    ) -> List[TextChunk]:
        if not seed_chunks:
            return []
        expansion_text = "".join(c.content[:300] for c in seed_chunks[:3])
        expansion_keywords = self._extract_keywords(expansion_text)
        expansion_query = " ".join(expansion_keywords[:10])
        if expansion_query.strip():
            return await self._semantic_search(expansion_query, filters, top_k)
        return []


class HierarchicalRAG:
    """
    层次化RAG系统
    使用 Parent Document Retrieval 策略：
    - 底层：细粒度块（512 tokens）用于精准匹配
    - 上层：情节摘要向量用于语义检索
    - 召回时自动注入完整上下文
    """
    
    def __init__(self, novel_id: int):
        self.novel_id = novel_id
        self.retriever = HybridRetriever()
        self.chunker = ChunkingStrategy()
    
    async def index_chapter(
        self,
        chapter_number: int,
        chapter_content: str,
        chapter_summary: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        将章节内容索引到RAG系统
        """
        metadata = metadata or {}
        metadata["chapter_number"] = chapter_number
        total_chunks = 0
        indexed_chunks = 0
        
        blocks = self.chunker.chunk_text(
            chapter_content,
            ChunkType.CHAPTER_BLOCK,
            self.novel_id,
            chapter_number,
            metadata
        )
        total_chunks += len(blocks)
        for chunk in blocks:
            success = await self._index_chunk(chunk)
            if success:
                indexed_chunks += 1
        
        if chapter_summary:
            summary_chunks = self.chunker.chunk_text(
                chapter_summary,
                ChunkType.PLOT_SUMMARY,
                self.novel_id,
                chapter_number,
                {**metadata, "is_summary": True}
            )
            total_chunks += len(summary_chunks)
            for chunk in summary_chunks:
                if await self._index_chunk(chunk):
                    indexed_chunks += 1
        
        logger.info(
            f"[HierarchicalRAG] 章节{chapter_number}索引完成: "
            f"{indexed_chunks}/{total_chunks}块"
        )
        return {
            "chapter_number": chapter_number,
            "total_chunks": total_chunks,
            "indexed_chunks": indexed_chunks,
            "success": indexed_chunks == total_chunks
        }
    
    async def index_memory_node(
        self,
        memory_data: Dict[str, Any],
        memory_type: str
    ) -> bool:
        """将记忆节点索引到RAG系统"""
        try:
            chunk_type_map = {
                "character": ChunkType.CHARACTER_MOMENT,
                "mystery": ChunkType.MYSTERY,
                "conflict": ChunkType.CONFLICT,
                "relationship": ChunkType.RELATIONSHIP,
                "plot_point": ChunkType.PLOT_SUMMARY,
                "world_building": ChunkType.WORLD_FACT,
            }
            chunk_type = chunk_type_map.get(memory_type, ChunkType.PLOT_SUMMARY)
            content = memory_data.get("content", "")
            if not content:
                return False
            chunks = self.chunker.chunk_text(
                content,
                chunk_type,
                self.novel_id,
                chapter_number=memory_data.get("chapter_number"),
                metadata={"memory_id": memory_data.get("id"), "memory_type": memory_type}
            )
            for chunk in chunks:
                await self._index_chunk(chunk)
            return True
        except Exception as e:
            logger.error(f"记忆节点索引失败: {e}")
            return False
    
    async def _index_chunk(self, chunk: TextChunk) -> bool:
        try:
            vector = await self.retriever.embedding_service.get_embedding(chunk.content)
            if not vector:
                logger.warning(f"无法生成向量，跳过chunk: {chunk.chunk_id}")
                return False
            payload = {
                "chunk_id": chunk.chunk_id,
                "novel_id": chunk.novel_id,
                "chunk_type": chunk.chunk_type.value,
                "content": chunk.content,
                "tokens": chunk.tokens,
                "chapter_number": chunk.chapter_number,
                "importance": chunk.importance,
                "metadata": chunk.metadata,
            }
            doc_id = f"{self.novel_id}_{chunk.chunk_id}"
            success = await vector_store.add_document(doc_id, vector, payload)
            if success:
                chunk.vector_id = doc_id
            return success
        except Exception as e:
            logger.error(f"索引块失败: {e}")
            return False
    
    async def retrieve_for_writer(
        self,
        chapter_outline: Dict[str, Any],
        top_k: int = 8
    ) -> Dict[str, Any]:
        """
        为Writer Agent检索相关上下文
        """
        query_parts = []
        if outline_summary := chapter_outline.get("summary", ""):
            query_parts.append(outline_summary)
        if key_events := chapter_outline.get("key_events", []):
            query_parts.append(" ".join(key_events[:3]))
        if characters := chapter_outline.get("characters", []):
            char_names = " ".join([c.get("name", "") for c in characters[:5]])
            query_parts.append(char_names)
        query = " ".join(query_parts)
        
        result = await self.retriever.retrieve(
            novel_id=self.novel_id,
            query=query,
            top_k=top_k,
            multi_hop=True,
            min_score=0.25,
        )
        
        grouped: Dict[str, List[TextChunk]] = {}
        for chunk in result.chunks:
            ct = chunk.chunk_type.value
            if ct not in grouped:
                grouped[ct] = []
            grouped[ct].append(chunk)
        
        writer_context = self._build_writer_context(grouped, chapter_outline)
        
        return {
            "chunks": [c.to_dict() for c in result.chunks],
            "grouped_by_type": {
                ct: [c.to_dict() for c in chunks]
                for ct, chunks in grouped.items()
            },
            "writer_context": writer_context,
            "retrieval_method": result.retrieval_method,
            "total_score": result.total_score,
            "query_used": query,
        }
    
    def _build_writer_context(
        self,
        grouped: Dict[str, List[TextChunk]],
        outline: Dict[str, Any]
    ) -> str:
        parts = []
        if mysteries := grouped.get(ChunkType.MYSTERY.value, []):
            parts.append("【未解伏笔】（本章或后续需处理）")
            for m in mysteries[:3]:
                parts.append(f"- {m.content[:200]}")
        if moments := grouped.get(ChunkType.CHARACTER_MOMENT.value, []):
            parts.append("\n【角色相关】")
            for m in moments[:3]:
                parts.append(f"- {m.content[:200]}")
        if conflicts := grouped.get(ChunkType.CONFLICT.value, []):
            parts.append("\n【冲突动态】")
            for c in conflicts[:3]:
                parts.append(f"- {c.content[:200]}")
        if relationships := grouped.get(ChunkType.RELATIONSHIP.value, []):
            parts.append("\n【人物关系】")
            for r in relationships[:3]:
                parts.append(f"- {r.content[:200]}")
        if blocks := grouped.get(ChunkType.CHAPTER_BLOCK.value, []):
            parts.append("\n【前文相关段落】（上下文衔接参考）")
            for b in blocks[:5]:
                ch = b.chapter_number
                snippet = b.content[:300] + ("..." if len(b.content) > 300 else "")
                parts.append(f"[第{ch}章] {snippet}")
        return "\n".join(parts) if parts else ""
    
    async def retrieve_world_facts(
        self,
        query: str,
        top_k: int = 5
    ) -> List[TextChunk]:
        result = await self.retriever.retrieve(
            novel_id=self.novel_id,
            query=query,
            top_k=top_k,
            chunk_types=[ChunkType.WORLD_FACT, ChunkType.PLOT_SUMMARY],
            min_score=0.3,
            multi_hop=False,
        )
        return result.chunks
    
    async def delete_novel_index(self) -> bool:
        try:
            success = await vector_store.delete_by_filter({"novel_id": self.novel_id})
            if success:
                logger.info(f"[HierarchicalRAG] 小说{self.novel_id}的全部索引已删除")
            return success
        except Exception as e:
            logger.error(f"删除RAG索引失败: {e}")
            return False
    
    async def get_index_stats(self) -> Dict[str, Any]:
        total = await vector_store.count_documents({"novel_id": self.novel_id})
        type_counts = {}
        for ct in ChunkType:
            count = await vector_store.count_documents({
                "novel_id": self.novel_id,
                "chunk_type": ct.value
            })
            if count > 0:
                type_counts[ct.value] = count
        return {
            "novel_id": self.novel_id,
            "total_chunks": total,
            "by_type": type_counts,
        }
