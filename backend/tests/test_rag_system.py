"""RAG System 鍗曞厓娴嬭瘯"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from app.rag_system import (
    ChunkType, ChunkingStrategy, HybridRetriever,
    HierarchicalRAG, TextChunk, HybridSearchResult
)


class TestChunkingStrategy:
    """娴嬭瘯鏂囨湰鍒嗗潡绛栫暐"""

    def test_estimate_tokens_chinese(self):
        """娴嬭瘯涓枃token浼扮畻"""
        text = "鏉庝簯绔欏湪鍩庨棬鍙ｏ紝鏈涚潃杩滃鐨勭兢灞便€備粬浠庢湭鎯宠繃鑷繁浼氳笍涓婅繖鏉¤矾銆? * 10
        tokens = ChunkingStrategy.estimate_tokens(text)
        assert tokens > 0, "Token浼扮畻搴旇杩斿洖姝ｆ暟"
        # 绾?00瀛?* 1.2 = 240 tokens
        assert 150 < tokens < 400, f"200瀛椾腑鏂囩害240 tokens, 瀹為檯: {tokens}"

    def test_estimate_tokens_english(self):
        """娴嬭瘯鑻辨枃token浼扮畻"""
        text = "The quick brown fox jumps over the lazy dog. " * 50
        tokens = ChunkingStrategy.estimate_tokens(text)
        assert tokens > 0
        # 鑻辨枃绾?.25璇?token
        assert tokens > 0

    def test_estimate_tokens_mixed(self):
        """娴嬭瘯涓嫳娣峰悎token浼扮畻"""
        text = "鏉庝簯璇达細Hello World锛佷粖澶╁ぉ姘旂湡濂姐€?
        tokens = ChunkingStrategy.estimate_tokens(text)
        assert tokens > 0

    def test_chunk_text_simple(self):
        """娴嬭瘯绠€鍗曟钀藉垎鍧?""
        text = """绗竴娈靛唴瀹广€?
绗簩娈靛唴瀹广€?
绗笁娈靛唴瀹广€?
绗洓娈靛唴瀹广€?
绗簲娈靛唴瀹广€?""

        chunks = ChunkingStrategy.chunk_text(
            text,
            ChunkType.CHAPTER_BLOCK,
            novel_id=1,
            chapter_number=1,
        )

        assert len(chunks) > 0, "搴旇浜х敓鑷冲皯涓€涓潡"
        for chunk in chunks:
            assert chunk.novel_id == 1
            assert chunk.chapter_number == 1
            assert chunk.chunk_type == ChunkType.CHAPTER_BLOCK
            assert chunk.content.strip() != ""
            assert chunk.tokens > 0

    def test_chunk_text_preserves_paragraphs(self):
        """娴嬭瘯娈佃惤缁撴瀯淇濈暀"""
        paragraphs = ["绗竴娈靛唴瀹广€? * 50] * 10
        text = "\n\n".join(paragraphs)

        chunks = ChunkingStrategy.chunk_text(
            text,
            ChunkType.CHAPTER_BLOCK,
            novel_id=1,
        )

        # 姣忎釜鍧楀簲璇ュ寘鍚涓钀?        for chunk in chunks:
            assert "\n" in chunk.content or len(chunk.content) > 10

    def test_chunk_text_long_paragraph(self):
        """娴嬭瘯瓒呴暱娈佃惤鎷嗗垎"""
        # 鏋勯€犱竴涓秴闀挎钀斤紙瓒呰繃512 tokens鐨?.5鍊嶏級
        long_para = "杩欐槸涓€娈甸潪甯搁暱鐨勬枃瀛椼€? * 500
        text = f"{long_para}\n\n杩欐槸涓嬩竴娈点€?

        chunks = ChunkingStrategy.chunk_text(
            text,
            ChunkType.CHAPTER_BLOCK,
            novel_id=1,
        )

        assert len(chunks) >= 2, "瓒呴暱娈佃惤搴旇琚媶鍒?
        # 鏈€鍚庝竴鑺傚簲璇ユ湁鍚庣画娈佃惤鐨勫唴瀹?        assert any("涓嬩竴娈? in c.content for c in chunks)

    def test_chunk_ids_are_unique(self):
        """娴嬭瘯鍧桰D鍞竴鎬?""
        text = "娴嬭瘯鍐呭涓€銆俓n\n娴嬭瘯鍐呭浜屻€?
        chunks1 = ChunkingStrategy.chunk_text(text, ChunkType.CHAPTER_BLOCK, 1, 1)
        chunks2 = ChunkingStrategy.chunk_text(text, ChunkType.CHAPTER_BLOCK, 1, 1)

        ids1 = {c.chunk_id for c in chunks1}
        ids2 = {c.chunk_id for c in chunks2}

        # 鐩稿悓鍐呭搴旇鐢熸垚鐩稿悓鐨処D
        assert ids1 == ids2

    def test_different_novel_ids_different_chunks(self):
        """娴嬭瘯涓嶅悓灏忚ID鐢熸垚涓嶅悓鍧?""
        text = "鐩稿悓鐨勫唴瀹广€? * 20
        chunks1 = ChunkingStrategy.chunk_text(text, ChunkType.CHAPTER_BLOCK, 1, 1)
        chunks2 = ChunkingStrategy.chunk_text(text, ChunkType.CHAPTER_BLOCK, 2, 1)

        # 涓嶅悓novel_id鐨勫潡ID搴旇涓嶅悓
        assert chunks1[0].chunk_id != chunks2[0].chunk_id

    def test_chunk_types_respect_size_limits(self):
        """娴嬭瘯涓嶅悓鍧楃被鍨嬮伒瀹堝ぇ灏忛檺鍒?""
        content = "娴嬭瘯鍐呭銆? * 200

        chapter_chunks = ChunkingStrategy.chunk_text(
            content, ChunkType.CHAPTER_BLOCK, 1
        )
        summary_chunks = ChunkingStrategy.chunk_text(
            content, ChunkType.PLOT_SUMMARY, 1
        )

        # 鎯呰妭鎽樿鍧楀簲璇ユ瘮绔犺妭鍧楁洿澶氾紙鍥犱负鐩爣鏇村皬锛?        assert len(summary_chunks) >= len(chapter_chunks)


class TestHybridRetriever:
    """娴嬭瘯娣峰悎妫€绱㈠櫒"""

    @pytest.mark.asyncio
    async def test_retrieve_empty_query(self):
        """娴嬭瘯绌烘煡璇㈠鐞?""
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
        """娴嬭瘯鍚戦噺妫€绱紙妯℃嫙锛?""
        retriever = HybridRetriever()

        with patch('app.rag_system.vector_store') as mock_vs:
            mock_vs.search = AsyncMock(return_value=[])

            result = await retriever.retrieve(
                novel_id=1,
                query="鏉庝簯绂诲埆鍩庨棬鍙?,
                top_k=5,
            )

            # 楠岃瘉鎼滅储琚皟鐢?            mock_vs.search.assert_called()
            assert isinstance(result, HybridSearchResult)

    @pytest.mark.asyncio
    async def test_keyword_extraction(self):
        """娴嬭瘯鍏抽敭璇嶆彁鍙?""
        retriever = HybridRetriever()

        text = "鏉庝簯绔欏湪鍩庨棬鍙ｏ紝鏈涚潃杩滃鐨勭兢灞便€備粬浠庢湭鎯宠繃鑷繁浼氳笍涓婅繖鏉¤矾銆?
        keywords = retriever._extract_keywords(text)

        assert isinstance(keywords, list)
        # 鍋滅敤璇嶄笉搴斿嚭鐜?        assert "鐨? not in keywords
        assert "鍦? not in keywords
        assert "浜? not in keywords
        # 鏈夋剰涔夎瘝姹囧簲璇ュ嚭鐜帮紙鍗曞瓧璇嶅"浠?鍦ㄥ仠鐢ㄨ瘝鍒楄〃涓紝3瀛楄瘝搴旇鍑虹幇锛?        assert any(len(kw) >= 2 for kw in keywords), f"搴斿寘鍚瀛楀叧閿瘝锛屽疄闄? {keywords}"

    @pytest.mark.asyncio
    async def test_fuse_results(self):
        """娴嬭瘯缁撴灉铻嶅悎"""
        retriever = HybridRetriever()

        semantic_chunks = [
            TextChunk("id1", 1, ChunkType.CHAPTER_BLOCK, "鍐呭A", 100, 1, 1.0),
            TextChunk("id2", 1, ChunkType.CHAPTER_BLOCK, "鍐呭B", 100, 1, 0.8),
        ]
        keyword_chunks = [
            TextChunk("id1", 1, ChunkType.CHAPTER_BLOCK, "鍐呭A", 100, 1, 1.0),
            TextChunk("id3", 1, ChunkType.CHAPTER_BLOCK, "鍐呭C", 100, 1, 0.9),
        ]
        semantic_chunks[0].vector_score = 0.9
        semantic_chunks[1].vector_score = 0.8
        keyword_chunks[0].vector_score = 1.0
        keyword_chunks[1].vector_score = 0.9

        fused = retriever._fuse_results(semantic_chunks, keyword_chunks)

        assert len(fused) >= 3, "铻嶅悎鍚庡簲鏈?涓潡"
        # id1搴旇鍦ㄧ粨鏋滀腑锛堜袱涓绱㈤兘鍛戒腑锛?        assert any(c.chunk_id == "id1" for c in fused)
        # 鍒嗘暟搴旇琚洿鏂?        id1_chunk = next(c for c in fused if c.chunk_id == "id1")
        assert id1_chunk.vector_score is not None
        assert id1_chunk.vector_score > 0.5, "铻嶅悎鍒嗘暟搴旇杈冮珮"


class TestHierarchicalRAG:
    """娴嬭瘯灞傛鍖朢AG"""

    @pytest.mark.asyncio
    async def test_index_chapter(self, mock_chapter_content, mock_vector_store):
        """娴嬭瘯绔犺妭绱㈠紩"""
        with patch('app.rag_system.vector_store', mock_vector_store), \
             patch('app.services.embedding_service.EmbeddingService') as MockEmbed:

            mock_embed = MagicMock()
            mock_embed.get_embedding = AsyncMock(return_value=[0.1] * 1024)
            MockEmbed.return_value = mock_embed

            rag = HierarchicalRAG(novel_id=1)
            # 鐩存帴娉ㄥ叆 mock embedding service
            rag.embedding_service = mock_embed

            result = await rag.index_chapter(
                chapter_number=1,
                chapter_content=mock_chapter_content,
                chapter_summary="鏉庝簯绂诲埆锛屽紑濮嬫柊鏃呯▼",
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
        """娴嬭瘯Writer妫€绱?""
        with patch('app.rag_system.vector_store', mock_vector_store), \
             patch('app.rag_system.EmbeddingService') as MockEmbed:

            mock_embed = MagicMock()
            mock_embed.get_embedding = AsyncMock(return_value=[0.1] * 1024)
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
        """娴嬭瘯璁板繂鑺傜偣绱㈠紩"""
        with patch('app.rag_system.vector_store', mock_vector_store), \
             patch('app.rag_system.EmbeddingService') as MockEmbed:

            mock_embed = MagicMock()
            mock_embed.get_embedding = AsyncMock(return_value=[0.1] * 1024)
            MockEmbed.return_value = mock_embed

            rag = HierarchicalRAG(novel_id=1)
            result = await rag.index_memory_node(
                memory_data={
                    "id": 1,
                    "content": "鏉庝簯鍙戠幇浜嗛噸瑕佺嚎绱?,
                    "chapter_number": 5,
                },
                memory_type="mystery"
            )

            assert result is True

    def test_build_writer_context(self):
        """娴嬭瘯Writer涓婁笅鏂囨瀯寤?""
        rag = HierarchicalRAG(novel_id=1)
        outline = {"summary": "娴嬭瘯", "key_events": ["浜嬩欢A", "浜嬩欢B"]}

        # 妯℃嫙妫€绱㈢粨鏋滃垎缁?        grouped = {
            ChunkType.MYSTERY.value: [
                TextChunk("m1", 1, ChunkType.MYSTERY, "鏈В浼忕瑪鍐呭A", 50, 3, 0.9),
            ],
            ChunkType.CHARACTER_MOMENT.value: [
                TextChunk("c1", 1, ChunkType.CHARACTER_MOMENT, "瑙掕壊鍏抽敭鏃跺埢B", 50, 4, 0.8),
            ],
            ChunkType.CHAPTER_BLOCK.value: [
                TextChunk("b1", 1, ChunkType.CHAPTER_BLOCK, "鍓嶆枃娈佃惤C", 100, 2, 0.7),
            ],
        }

        context = rag._build_writer_context(grouped, outline)

        assert isinstance(context, str)
        assert "鏈В浼忕瑪" in context
        assert "鍓嶆枃鐩稿叧娈佃惤" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

