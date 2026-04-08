"""
向量数据库管理模块
使用Qdrant存储和检索语义记忆
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from loguru import logger

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        Filter, FieldCondition, MatchValue, Range
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("Qdrant client not available, vector store will use mock mode")

from app.core.config import settings


@dataclass
class VectorSearchResult:
    """向量搜索结果"""
    id: str
    score: float
    payload: Dict[str, Any]


class VectorStore:
    """向量存储管理器"""
    
    COLLECTION_NAME = settings.QDRANT_COLLECTION
    VECTOR_SIZE = 1536  # OpenAI text-embedding-ada-002 的维度
    
    def __init__(self):
        self.client: Optional[QdrantClient] = None
        self._mock_mode = not QDRANT_AVAILABLE
        
        if not self._mock_mode:
            try:
                self.client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    api_key=settings.QDRANT_API_KEY,
                )
                self._ensure_collection()
                logger.info(f"向量存储已连接: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
            except Exception as e:
                logger.error(f"连接Qdrant失败: {e}，将使用模拟模式")
                self._mock_mode = True
                self.client = None
        else:
            logger.info("向量存储运行在模拟模式")
    
    def _ensure_collection(self):
        """确保集合存在"""
        if self._mock_mode:
            return
        
        try:
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.COLLECTION_NAME not in collection_names:
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"创建向量集合: {self.COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"创建集合失败: {e}")
            raise
    
    async def add_document(
        self,
        doc_id: str,
        vector: List[float],
        payload: Dict[str, Any]
    ) -> bool:
        """
        添加文档到向量存储
        
        Args:
            doc_id: 文档唯一ID
            vector: 向量数据
            payload: 附加数据
            
        Returns:
            是否成功
        """
        if self._mock_mode:
            logger.debug(f"模拟模式: 添加文档 {doc_id}")
            return True
        
        try:
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=doc_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            logger.debug(f"添加向量文档: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"添加向量文档失败: {e}")
            return False
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> bool:
        """
        批量添加文档
        
        Args:
            documents: 文档列表，每个包含id, vector, payload
            
        Returns:
            是否成功
        """
        if self._mock_mode:
            logger.debug(f"模拟模式: 批量添加 {len(documents)} 个文档")
            return True
        
        try:
            points = [
                PointStruct(
                    id=doc["id"],
                    vector=doc["vector"],
                    payload=doc.get("payload", {})
                )
                for doc in documents
            ]
            
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=points
            )
            logger.debug(f"批量添加向量文档: {len(documents)} 个")
            return True
        except Exception as e:
            logger.error(f"批量添加向量文档失败: {e}")
            return False
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """
        向量相似度搜索
        
        Args:
            query_vector: 查询向量
            top_k: 返回结果数
            filters: 过滤条件
            
        Returns:
            搜索结果列表
        """
        if self._mock_mode:
            logger.debug(f"模拟模式: 搜索返回空结果")
            return []
        
        try:
            # 构建过滤条件
            search_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, (str, int, bool)):
                        conditions.append(
                            FieldCondition(
                                key=key,
                                match=MatchValue(value=value)
                            )
                        )
                if conditions:
                    search_filter = Filter(must=conditions)
            
            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=top_k,
                query_filter=search_filter
            )
            
            return [
                VectorSearchResult(
                    id=str(r.id),
                    score=r.score,
                    payload=r.payload
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        if self._mock_mode:
            logger.debug(f"模拟模式: 删除文档 {doc_id}")
            return True
        
        try:
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=[doc_id]
            )
            logger.debug(f"删除向量文档: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"删除向量文档失败: {e}")
            return False
    
    async def delete_by_filter(self, filters: Dict[str, Any]) -> bool:
        """根据条件删除文档"""
        if self._mock_mode:
            logger.debug(f"模拟模式: 根据条件删除文档")
            return True
        
        try:
            conditions = []
            for key, value in filters.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=Filter(must=conditions)
            )
            logger.debug(f"根据条件删除向量文档")
            return True
        except Exception as e:
            logger.error(f"删除向量文档失败: {e}")
            return False
    
    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取单个文档"""
        if self._mock_mode:
            return None
        
        try:
            results = self.client.retrieve(
                collection_name=self.COLLECTION_NAME,
                ids=[doc_id],
                with_payload=True,
                with_vectors=False
            )
            
            if results:
                return {
                    "id": str(results[0].id),
                    "payload": results[0].payload
                }
            return None
        except Exception as e:
            logger.error(f"获取向量文档失败: {e}")
            return None
    
    async def count_documents(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """统计文档数量"""
        if self._mock_mode:
            return 0
        
        try:
            search_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                search_filter = Filter(must=conditions)
            
            result = self.client.count(
                collection_name=self.COLLECTION_NAME,
                count_filter=search_filter
            )
            return result.count
        except Exception as e:
            logger.error(f"统计向量文档失败: {e}")
            return 0


# 全局向量存储实例
vector_store = VectorStore()
