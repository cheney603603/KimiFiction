"""
文本嵌入服务 - 支持BGE-large-zh模型
提供文本向量化和语义搜索功能
"""
import hashlib
import os
from typing import List, Dict, Any, Optional
from functools import lru_cache
from loguru import logger

from app.core.vector_store import vector_store, VectorSearchResult
from app.core.config import settings


class BGEEmbeddingProvider:
    """
    BGE-large-zh 嵌入模型提供者
    
    使用BAAI/bge-large-zh-v1.5模型，支持中英文语义理解
    模型维度: 1024
    支持的最大序列长度: 512 tokens
    """
    
    _instance = None
    _model = None
    _tokenizer = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.model_name = "BAAI/bge-large-zh-v1.5"
        self.vector_dim = settings.VECTOR_DIM  # 从配置读取，确保与 VectorStore 一致
        self.max_seq_length = 512
        self._load_model()
    
    def _load_model(self):
        """懒加载模型"""
        if BGEEmbeddingProvider._model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            # 检查本地缓存目录
            cache_dir = os.path.join(os.getcwd(), "models", "embeddings")
            os.makedirs(cache_dir, exist_ok=True)
            
            logger.info(f"[BGEEmbedding] 正在加载模型: {self.model_name}")
            
            # 加载模型，使用本地缓存
            BGEEmbeddingProvider._model = SentenceTransformer(
                self.model_name,
                cache_folder=cache_dir,
                device="cpu"  # 可以根据环境切换到cuda
            )
            
            logger.info(f"[BGEEmbedding] 模型加载完成，维度: {self.vector_dim}")
            
        except ImportError:
            logger.error("[BGEEmbedding] sentence-transformers未安装，使用mock向量")
            BGEEmbeddingProvider._model = None
        except Exception as e:
            logger.error(f"[BGEEmbedding] 模型加载失败: {e}")
            BGEEmbeddingProvider._model = None
    
    def encode(self, text: str) -> List[float]:
        """
        将文本编码为向量
        
        Args:
            text: 输入文本
            
        Returns:
            1024维向量
        """
        if BGEEmbeddingProvider._model is None:
            return self._mock_encode(text)
        
        try:
            # BGE模型需要在文本前添加指令前缀以获得最佳效果
            instruction = "为这个句子生成表示以用于检索相关文章："
            formatted_text = f"{instruction}{text}"
            
            # 编码
            embedding = BGEEmbeddingProvider._model.encode(
                formatted_text,
                normalize_embeddings=True,  # 归一化向量
                show_progress_bar=False
            )
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"[BGEEmbedding] 编码失败: {e}")
            return self._mock_encode(text)
    
    def encode_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        批量编码文本
        
        Args:
            texts: 文本列表
            batch_size: 批处理大小
            
        Returns:
            向量列表
        """
        if BGEEmbeddingProvider._model is None:
            return [self._mock_encode(text) for text in texts]
        
        try:
            instruction = "为这个句子生成表示以用于检索相关文章："
            formatted_texts = [f"{instruction}{text}" for text in texts]
            
            embeddings = BGEEmbeddingProvider._model.encode(
                formatted_texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"[BGEEmbedding] 批量编码失败: {e}")
            return [self._mock_encode(text) for text in texts]
    
    def _mock_encode(self, text: str) -> List[float]:
        """
        模拟编码（fallback）
        使用文本哈希生成伪随机但一致的向量
        """
        hash_val = hashlib.md5(text.encode()).hexdigest()
        vector = []
        for i in range(self.vector_dim):
            idx = (i * 2) % 32
            val = int(hash_val[idx:idx+2], 16) / 128 - 1
            vector.append(val)
        return vector
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_name": self.model_name,
            "vector_dim": self.vector_dim,
            "max_seq_length": self.max_seq_length,
            "loaded": BGEEmbeddingProvider._model is not None
        }


class EmbeddingService:
    """文本嵌入服务 - 统一接口"""
    
    def __init__(self, use_bge: bool = True):
        self.provider = BGEEmbeddingProvider() if use_bge else None
        self._mock_mode = self.provider is None or self.provider._model is None
        
        if self._mock_mode:
            logger.warning("[EmbeddingService] 使用mock向量模式")
        else:
            logger.info("[EmbeddingService] 使用BGE-large-zh嵌入模型")
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的向量表示
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表 (1024维 for BGE-large-zh)
        """
        if not text or not text.strip():
            # 返回零向量
            dim = settings.VECTOR_DIM
            return [0.0] * dim
        
        try:
            # 截断过长文本
            text = text[:2000]  # 粗略字符限制
            
            if self.provider:
                return self.provider.encode(text)
            else:
                return self._mock_embedding(text)
                
        except Exception as e:
            logger.error(f"[EmbeddingService] 获取嵌入失败: {e}")
            return self._mock_embedding(text)
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取文本向量
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        if not texts:
            return []
        
        try:
            if self.provider:
                return self.provider.encode_batch(texts)
            else:
                return [self._mock_embedding(text) for text in texts]
        except Exception as e:
            logger.error(f"[EmbeddingService] 批量获取嵌入失败: {e}")
            return [self._mock_embedding(text) for text in texts]
    
    def _mock_embedding(self, text: str) -> List[float]:
        """模拟向量生成（fallback），维度与配置一致"""
        dim = settings.VECTOR_DIM
        hash_val = hashlib.md5(text.encode()).hexdigest()
        vector = []
        for i in range(dim):
            idx = (i * 2) % 32
            val = int(hash_val[idx:idx+2], 16) / 128 - 1
            vector.append(val)
        return vector
    
    async def store_memory(
        self,
        novel_id: int,
        node_id: str,
        content: str,
        node_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        存储记忆节点到向量数据库
        
        Args:
            novel_id: 小说ID
            node_id: 节点ID
            content: 节点内容
            node_type: 节点类型
            metadata: 附加元数据
            
        Returns:
            是否成功
        """
        try:
            vector = await self.get_embedding(content)
            
            payload = {
                "novel_id": novel_id,
                "node_id": node_id,
                "content": content,
                "node_type": node_type,
                **(metadata or {})
            }
            
            doc_id = f"{novel_id}_{node_id}"
            success = await vector_store.add_document(doc_id, vector, payload)
            
            if success:
                logger.debug(f"[EmbeddingService] 记忆节点已存储: {node_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"[EmbeddingService] 存储记忆失败: {e}")
            return False
    
    async def search_memories(
        self,
        novel_id: int,
        query: str,
        top_k: int = 5,
        node_type: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        搜索相关记忆
        
        Args:
            novel_id: 小说ID
            query: 查询文本
            top_k: 返回结果数
            node_type: 按类型筛选
            min_score: 最小相似度分数
            
        Returns:
            相关记忆列表
        """
        try:
            query_vector = await self.get_embedding(query)
            
            filters = {"novel_id": novel_id}
            if node_type:
                filters["node_type"] = node_type
            
            results = await vector_store.search(
                query_vector=query_vector,
                top_k=top_k,
                filters=filters
            )
            
            filtered_results = [
                {
                    "id": r.id,
                    "score": r.score,
                    **r.payload
                }
                for r in results
                if r.score >= min_score
            ]
            
            logger.debug(f"[EmbeddingService] 记忆搜索完成: '{query[:30]}...', 找到{len(filtered_results)}条结果")
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"[EmbeddingService] 记忆搜索失败: {e}")
            return []
    
    async def search_similar_memories(
        self,
        novel_id: int,
        content: str,
        top_k: int = 3,
        exclude_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索与给定内容相似的记忆
        
        Args:
            novel_id: 小说ID
            content: 参考内容
            top_k: 返回结果数
            exclude_id: 要排除的节点ID
            
        Returns:
            相似记忆列表
        """
        results = await self.search_memories(novel_id, content, top_k=top_k + 1)
        
        if exclude_id:
            results = [r for r in results if r.get("node_id") != exclude_id]
        
        return results[:top_k]
    
    async def delete_novel_memories(self, novel_id: int) -> bool:
        """
        删除小说的所有记忆
        
        Args:
            novel_id: 小说ID
            
        Returns:
            是否成功
        """
        try:
            success = await vector_store.delete_by_filter({"novel_id": novel_id})
            if success:
                logger.info(f"[EmbeddingService] 已删除小说{novel_id}的所有向量记忆")
            return success
        except Exception as e:
            logger.error(f"[EmbeddingService] 删除小说记忆失败: {e}")
            return False
    
    async def get_memory_stats(self, novel_id: int) -> Dict[str, Any]:
        """
        获取记忆统计信息
        
        Args:
            novel_id: 小说ID
            
        Returns:
            统计信息
        """
        try:
            total_count = await vector_store.count_documents({"novel_id": novel_id})
            
            type_counts = {}
            for node_type in ["plot_point", "character_moment", "world_building", "mystery", "conflict", "relationship"]:
                count = await vector_store.count_documents({
                    "novel_id": novel_id,
                    "node_type": node_type
                })
                if count > 0:
                    type_counts[node_type] = count
            
            return {
                "novel_id": novel_id,
                "total_memories": total_count,
                "type_distribution": type_counts,
                "embedding_model": self.get_model_info()
            }
            
        except Exception as e:
            logger.error(f"[EmbeddingService] 获取记忆统计失败: {e}")
            return {"novel_id": novel_id, "total_memories": 0, "type_distribution": {}}
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取当前使用的模型信息"""
        if self.provider:
            return self.provider.get_model_info()
        return {"model_name": "mock", "vector_dim": settings.VECTOR_DIM, "loaded": False}


# 全局嵌入服务实例
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """获取全局嵌入服务实例"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(use_bge=True)
    return _embedding_service


def reset_embedding_service():
    """重置嵌入服务实例（用于测试）"""
    global _embedding_service
    _embedding_service = None
