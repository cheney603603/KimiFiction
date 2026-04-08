"""
文本嵌入服务
提供文本向量化和语义搜索功能
"""
import hashlib
from typing import List, Dict, Any, Optional
from loguru import logger

from app.core.vector_store import vector_store, VectorSearchResult


class EmbeddingService:
    """文本嵌入服务"""
    
    def __init__(self):
        self._mock_vectors = True  # 模拟模式，实际使用时接入真实嵌入模型
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的向量表示
        
        注意：这是模拟实现，实际使用时需要接入OpenAI或其他嵌入模型
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表
        """
        if self._mock_vectors:
            # 模拟向量：使用文本哈希生成伪随机但一致的向量
            # 实际使用时替换为真实嵌入模型调用
            hash_val = hashlib.md5(text.encode()).hexdigest()
            vector = []
            for i in range(1536):
                # 使用哈希值生成-1到1之间的伪随机数
                idx = (i * 2) % 32
                val = int(hash_val[idx:idx+2], 16) / 128 - 1
                vector.append(val)
            return vector
        
        # TODO: 接入真实嵌入模型
        # from langchain_openai import OpenAIEmbeddings
        # embeddings = OpenAIEmbeddings()
        # return await embeddings.aembed_query(text)
        return []
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量获取文本向量"""
        return [await self.get_embedding(text) for text in texts]
    
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
            # 获取向量
            vector = await self.get_embedding(content)
            
            # 构建payload
            payload = {
                "novel_id": novel_id,
                "node_id": node_id,
                "content": content,
                "node_type": node_type,
                **(metadata or {})
            }
            
            # 存储到向量数据库
            doc_id = f"{novel_id}_{node_id}"
            success = await vector_store.add_document(doc_id, vector, payload)
            
            if success:
                logger.info(f"记忆节点已存储到向量库: {node_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"存储记忆节点失败: {e}")
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
            # 获取查询向量
            query_vector = await self.get_embedding(query)
            
            # 构建过滤条件
            filters = {"novel_id": novel_id}
            if node_type:
                filters["node_type"] = node_type
            
            # 执行搜索
            results = await vector_store.search(
                query_vector=query_vector,
                top_k=top_k,
                filters=filters
            )
            
            # 过滤低分结果
            filtered_results = [
                {
                    "id": r.id,
                    "score": r.score,
                    **r.payload
                }
                for r in results
                if r.score >= min_score
            ]
            
            logger.info(f"记忆搜索完成: 查询'{query[:30]}...', 找到{len(filtered_results)}条结果")
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"记忆搜索失败: {e}")
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
        
        # 排除指定ID
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
                logger.info(f"已删除小说{novel_id}的所有向量记忆")
            return success
        except Exception as e:
            logger.error(f"删除小说记忆失败: {e}")
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
            
            # 按类型统计
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
                "type_distribution": type_counts
            }
            
        except Exception as e:
            logger.error(f"获取记忆统计失败: {e}")
            return {"novel_id": novel_id, "total_memories": 0, "type_distribution": {}}


# 全局嵌入服务实例
embedding_service = EmbeddingService()
