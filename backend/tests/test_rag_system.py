"""RAG System 单元测试"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from app.rag_system import (
    ChunkType, ChunkingStrategy, HybridRetriever,
    HierarchicalRAG, TextChunk, HybridSearchResult
)


class TestChunkingStrategy:
    """测试文本分块策略"""

    def test_estimate_tokens_chinese(self):
        """测试中文token估算"""
        text = "李云站在城门口，望着远处的群山。他从未想过自己会踏上这条路。" * 10
        tokens = ChunkingStrategy.estimate_tokens(text)
        assert tokens > 0, "Token估算应该返回正数"
        # 约200字 * 1.2 = 240 tokens
        assert 150 < tokens < 400, f"200字中文约240 tokens, 实际: {tokens}"

    def test_estimate_tokens_english(self):
        """测试英文token估算"""
        text = "The quick brown fox jumps over the lazy dog. " * 50
        tokens = ChunkingStrategy.estimate_tokens(text)
        assert tokens > 0
        # 英文约0.25词/token
        assert tokens > 0

    def test_estimate_tokens_mixed(self):
        """测试中英混合token估算"""
        text = "李云说：Hello World！今天天气真好。"
        tokens = ChunkingStrategy.estimate_tokens(text)
        assert tokens > 0

    def test_chunk_text_simple(self):
        """测试简单段落分块"""
        text = """第一段内容。

第二段内容。

第三段内容。

第四段内容。

第五段内容。"""

        chunks = ChunkingStrategy.chunk_text(
            text,
            ChunkType.CHAPTER_BLOCK,
            novel_id=1,
            chapter_number=1,
        )

        assert len(chunks) > 0, "应该产生至少一个块"
        for chunk in chunks:
            assert chunk.novel_id == 1
            assert chunk.chapter_number == 1
            assert chunk.chunk_type == ChunkType.CHAPTER_BLOCK
            assert chunk.content.strip() != ""
            assert chunk.tokens > 0

    def test_chunk_text_preserves_paragraphs(self):
        """测试段落结构保留"""
        paragraphs = ["第一段内容。" * 50] * 10
        text = "\n\n".join(paragraphs)

        chunks = ChunkingStrategy.chunk_text(
            text,
            ChunkType.CHAPTER_BLOCK,
            novel_id=1,
        )

        # 每个块应该包含多个段落
        for chunk in chunks:
            assert "\n" in chunk.content or len(chunk.content) > 10

    def test_chunk_text_long_paragraph(self):
        """测试超长段落拆分"""
        # 构造一个超长段落（超过512 tokens的1.5倍）
        long_para = "这是一段非常长的文字。" * 500
        text = f"{long_para}\n\n这是下一段。"

        chunks = ChunkingStrategy.chunk_text(
            text,
            ChunkType.CHAPTER_BLOCK,
            novel_id=1,
        )

        assert len(chunks) >= 2, "超长段落应该被拆分"
        # 最后一节应该有后续段落的内容
        assert any("下一段" in c.content for c in chunks)

    def test_chunk_ids_are_unique(self):
        """测试块ID唯一性"""
        text = "测试内容一。\n\n测试内容二。"
        chunks1 = ChunkingStrategy.chunk_text(text, ChunkType.CHAPTER_BLOCK, 1, 1)
        chunks2 = ChunkingStrategy.chunk_text(text, ChunkType.CHAPTER_BLOCK, 1, 1)

        ids1 = {c.chunk_id for c in chunks1}
        ids2 = {c.chunk_id for c in chunks2}

        # 相同内容应该生成相同的ID
        assert ids1 == ids2

    def test_different_novel_ids_different_chunks(self):
        """测试不同小说ID生成不同块"""
        text = "相同的内容。" * 20
        chunks1 = ChunkingStrategy.chunk_text(text, ChunkType.CHAPTER_BLOCK, 1, 1)
        chunks2 = ChunkingStrategy.chunk_text(text, ChunkType.CHAPTER_BLOCK, 2, 1)

        # 不同novel_id的块ID应该不同
        assert chunks1[0].chunk_id != chunks2[0].chunk_id

    def test_chunk_types_respect_size_limits(self):
        """测试不同块类型遵守大小限制"""
        content = "测试内容。" * 200

        chapter_chunks = ChunkingStrategy.chunk_text(
            content, ChunkType.CHAPTER_BLOCK, 1
        )
        summary_chunks = ChunkingStrategy.chunk_text(
            content, ChunkType.PLOT_SUMMARY, 1
        )

        # 情节摘要块应该比章节块更多（因为目标更小）
        assert len(summary_chunks) >= len(chapter_chunks)


class TestHybridRetriever:
    """测试混合检索器"""

    @pytest.mark.asyncio
    async def test_retrieve_empty_query(self):
        """测试空查询处理"""
        retriever = HybridRetriever()

        result = await retriever.retrieve(
            novel_id=1,
            query="",
            top_k=5,
        )

        assert result.retrieval_method == "empty_query"
        assert len(result.chunks) == 0
        assert result.total_score == 0.0

    @pytest.mark.asyncio
    async def test_retrieve_with_mock_vector(self):
        """测试向量检索（模拟）"""
        retriever = HybridRetriever()

        with patch('app.rag_system.vector_store') as mock_vs:
            mock_vs.search = AsyncMock(return_value=[])

            result = await retriever.retrieve(
                novel_id=1,
                query="李云离别城门口",
                top_k=5,
            )

            # 验证搜索被调用
            mock_vs.search.assert_called()
            assert isinstance(result, HybridSearchResult)

    @pytest.mark.asyncio
    async def test_keyword_extraction(self):
        """测试关键词提取"""
        retriever = HybridRetriever()

        text = "李云站在城门口，望着远处的群山。他从未想过自己会踏上这条路。"
        keywords = retriever._extract_keywords(text)

        assert isinstance(keywords, list)
        # 停用词不应出现
        assert "的" not in keywords
        assert "在" not in keywords
        assert "了" not in keywords
        # 有意义词汇应该出现（单字词如"他"在停用词列表中，3字词应该出现）
        assert any(len(kw) >= 2 for kw in keywords), f"应包含多字关键词，实际: {keywords}"

    @pytest.mark.asyncio
    async def test_fuse_results(self):
        """测试结果融合"""
        retriever = HybridRetriever()

        semantic_chunks = [
            TextChunk("id1", 1, ChunkType.CHAPTER_BLOCK, "内容A", 100, 1, 1.0),
            TextChunk("id2", 1, ChunkType.CHAPTER_BLOCK, "内容B", 100, 1, 0.8),
        ]
        keyword_chunks = [
            TextChunk("id1", 1, ChunkType.CHAPTER_BLOCK, "内容A", 100, 1, 1.0),
            TextChunk("id3", 1, ChunkType.CHAPTER_BLOCK, "内容C", 100, 1, 0.9),
        ]
        semantic_chunks[0].vector_score = 0.9
        semantic_chunks[1].vector_score = 0.8
        keyword_chunks[0].vector_score = 1.0
        keyword_chunks[1].vector_score = 0.9

        fused = retriever._fuse_results(semantic_chunks, keyword_chunks)

        assert len(fused) >= 3, "融合后应有3个块"
        # id1应该在结果中（两个检索都命中）
        assert any(c.chunk_id == "id1" for c in fused)
        # 分数应该被更新
        id1_chunk = next(c for c in fused if c.chunk_id == "id1")
        assert id1_chunk.vector_score is not None
        assert id1_chunk.vector_score > 0.5, "融合分数应该较高"


class TestHierarchicalRAG:
    """测试层次化RAG"""

    @pytest.mark.asyncio
    async def test_index_chapter(self, mock_chapter_content, mock_vector_store):
        """测试章节索引"""
        with patch('app.rag_system.vector_store', mock_vector_store), \
             patch('app.services.embedding_service.EmbeddingService') as MockEmbed:

            mock_embed = MagicMock()
            mock_embed.get_embedding = AsyncMock(return_value=[0.1] * 1536)
            MockEmbed.return_value = mock_embed

            rag = HierarchicalRAG(novel_id=1)
            # 直接注入 mock embedding service
            rag.embedding_service = mock_embed

            result = await rag.index_chapter(
                chapter_number=1,
                chapter_content=mock_chapter_content,
                chapter_summary="李云离别，开始新旅程",
            )

            assert "chapter_number" in result
            assert result["chapter_number"] == 1
            assert "total_chunks" in result
            assert result["total_chunks"] >= 1
            assert "indexed_chunks" in result
            assert result["indexed_chunks"] >= 1
            assert "success" in result

    @pytest.mark.asyncio
    async def test_retrieve_for_writer(self, mock_chapter_outline, mock_vector_store):
        """测试Writer检索"""
        with patch('app.rag_system.vector_store', mock_vector_store), \
             patch('app.rag_system.EmbeddingService') as MockEmbed:

            mock_embed = MagicMock()
            mock_embed.get_embedding = AsyncMock(return_value=[0.1] * 1536)
            MockEmbed.return_value = mock_embed

            rag = HierarchicalRAG(novel_id=1)
            result = await rag.retrieve_for_writer(mock_chapter_outline, top_k=5)

            assert "chunks" in result
            assert "grouped_by_type" in result
            assert "writer_context" in result
            assert "retrieval_method" in result
            assert isinstance(result["writer_context"], str)

    @pytest.mark.asyncio
    async def test_index_memory_node(self, mock_vector_store):
        """测试记忆节点索引"""
        with patch('app.rag_system.vector_store', mock_vector_store), \
             patch('app.rag_system.EmbeddingService') as MockEmbed:

            mock_embed = MagicMock()
            mock_embed.get_embedding = AsyncMock(return_value=[0.1] * 1536)
            MockEmbed.return_value = mock_embed

            rag = HierarchicalRAG(novel_id=1)
            result = await rag.index_memory_node(
                memory_data={
                    "id": 1,
                    "content": "李云发现了重要线索",
                    "chapter_number": 5,
                },
                memory_type="mystery"
            )

            assert result is True

    def test_build_writer_context(self):
        """测试Writer上下文构建"""
        rag = HierarchicalRAG(novel_id=1)
        outline = {"summary": "测试", "key_events": ["事件A", "事件B"]}

        # 模拟检索结果分组
        grouped = {
            ChunkType.MYSTERY.value: [
                TextChunk("m1", 1, ChunkType.MYSTERY, "未解伏笔内容A", 50, 3, 0.9),
            ],
            ChunkType.CHARACTER_MOMENT.value: [
                TextChunk("c1", 1, ChunkType.CHARACTER_MOMENT, "角色关键时刻B", 50, 4, 0.8),
            ],
            ChunkType.CHAPTER_BLOCK.value: [
                TextChunk("b1", 1, ChunkType.CHAPTER_BLOCK, "前文段落C", 100, 2, 0.7),
            ],
        }

        context = rag._build_writer_context(grouped, outline)

        assert isinstance(context, str)
        assert "未解伏笔" in context
        assert "前文相关段落" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
