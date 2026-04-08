"""
记忆服务层
处理记忆节点的业务逻辑和向量检索
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.models.memory_node import MemoryNode, NodeType
from app.models.chapter import Chapter
from app.schemas.memory import MemoryNodeCreate, MemoryNodeUpdate, MemorySearchRequest


class MemoryService:
    """记忆服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_node(self, node_data: MemoryNodeCreate) -> MemoryNode:
        """创建记忆节点"""
        import json
        
        node = MemoryNode(
            novel_id=node_data.novel_id,
            node_type=NodeType(node_data.node_type),
            title=node_data.title,
            content=node_data.content,
            chapter_range=node_data.chapter_range,
            specific_chapter=node_data.specific_chapter,
            importance_score=node_data.importance_score,
            related_characters=json.dumps(node_data.related_characters) if node_data.related_characters else "[]",
            related_locations=json.dumps(node_data.related_locations) if node_data.related_locations else "[]",
            embedding_id=node_data.embedding_id or "",
        )
        self.db.add(node)
        await self.db.commit()
        await self.db.refresh(node)
        logger.info(f"创建记忆节点: {node.title} (类型: {node.node_type.value})")
        return node
    
    async def get_node(self, node_id: int) -> Optional[MemoryNode]:
        """获取记忆节点"""
        result = await self.db.execute(
            select(MemoryNode).where(MemoryNode.id == node_id)
        )
        return result.scalar_one_or_none()
    
    async def list_nodes(
        self,
        novel_id: int,
        node_type: Optional[str] = None,
        unresolved_only: bool = False
    ) -> List[MemoryNode]:
        """获取记忆节点列表"""
        query = select(MemoryNode).where(MemoryNode.novel_id == novel_id)
        
        if node_type:
            query = query.where(MemoryNode.node_type == node_type)
        
        if unresolved_only:
            query = query.where(MemoryNode.is_resolved == False)
        
        query = query.order_by(MemoryNode.importance_score.desc(), MemoryNode.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_node(self, node_id: int, node_data: MemoryNodeUpdate) -> Optional[MemoryNode]:
        """更新记忆节点"""
        node = await self.get_node(node_id)
        if not node:
            return None
        
        update_data = node_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(node, field, value)
        
        await self.db.commit()
        await self.db.refresh(node)
        logger.info(f"更新记忆节点: {node.title} (ID: {node.id})")
        return node
    
    async def delete_node(self, node_id: int) -> bool:
        """删除记忆节点"""
        node = await self.get_node(node_id)
        if not node:
            return False
        
        await self.db.delete(node)
        await self.db.commit()
        logger.info(f"删除记忆节点: ID {node_id}")
        return True
    
    async def search_similar(self, request: MemorySearchRequest) -> List[Dict]:
        """
        语义搜索记忆节点
        TODO: 集成Qdrant向量数据库进行真正的语义搜索
        """
        # 临时实现：基于关键词的简单搜索
        nodes = await self.list_nodes(request.novel_id, request.node_type)
        
        results = []
        query_lower = request.query.lower()
        
        for node in nodes:
            # 简单相关性评分
            score = 0.0
            content_lower = node.content.lower()
            title_lower = node.title.lower()
            
            if query_lower in title_lower:
                score += 0.5
            if query_lower in content_lower:
                score += 0.3
            
            # 重要性加权
            score += node.importance_score * 0.2
            
            if score >= request.min_importance:
                results.append({
                    "node": node,
                    "similarity_score": min(score, 1.0)
                })
        
        # 按相似度排序
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:request.top_k]
    
    async def build_context(self, novel_id: int, chapter_number: int) -> Dict[str, Any]:
        """
        构建写作上下文
        包含：最近章节、相关记忆、角色状态等
        """
        from app.services.chapter_service import ChapterService
        from app.services.character_service import CharacterService
        
        chapter_service = ChapterService(self.db)
        char_service = CharacterService(self.db)
        
        # 1. 获取最近章节
        recent_chapters = await chapter_service.get_recent_chapters(novel_id, count=3)
        
        # 2. 获取中期摘要（每10章）
        mid_summary_chapter = (chapter_number // 10) * 10
        
        # 3. 获取相关记忆节点
        # 搜索与当前章节相关的记忆
        relevant_memories = await self.list_nodes(novel_id)
        
        # 4. 获取角色当前状态
        characters = await char_service.list_characters(novel_id)
        char_status = []
        for char in characters:
            status_dict = char.get_status_dict()
            char_status.append({
                "name": char.name,
                "role": char.role_type.value,
                "status": status_dict,
                "arc_progress": char.arc_progress,
            })
        
        # 5. 获取未解决的伏笔
        mysteries = await self.list_nodes(novel_id, node_type="mystery", unresolved_only=True)
        
        return {
            "current_chapter": chapter_number,
            "recent_chapters": [
                {
                    "number": ch.chapter_number,
                    "title": ch.title,
                    "summary": ch.summary,
                }
                for ch in reversed(recent_chapters)  # 按时间顺序
            ],
            "relevant_memories": [
                {
                    "type": node.node_type.value,
                    "title": node.title,
                    "content": node.content,
                }
                for node in relevant_memories[:10]
            ],
            "character_status": char_status,
            "unresolved_mysteries": [
                {
                    "title": node.title,
                    "content": node.content,
                    "chapter": node.chapter_range,
                }
                for node in mysteries[:5]
            ],
        }
    
    async def consolidate_memory(self, novel_id: int, chapter_threshold: int = 50) -> Dict:
        """
        整理记忆（压缩旧章节）
        当章节数超过阈值时，将旧章节压缩为记忆节点
        """
        from app.services.chapter_service import ChapterService
        
        chapter_service = ChapterService(self.db)
        
        # 获取章节总数
        result = await self.db.execute(
            select(func.count()).where(Chapter.novel_id == novel_id)
        )
        total_chapters = result.scalar()
        
        if total_chapters <= chapter_threshold:
            return {
                "novel_id": novel_id,
                "chapters_processed": 0,
                "nodes_created": 0,
                "message": "章节数未超过阈值，无需整理"
            }
        
        # 获取需要压缩的旧章节
        old_chapters_result = await self.db.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .where(Chapter.chapter_number <= total_chapters - chapter_threshold)
            .order_by(Chapter.chapter_number.asc())
        )
        old_chapters = old_chapters_result.scalars().all()
        
        nodes_created = 0
        
        # 为每10章创建一个摘要节点
        for i in range(0, len(old_chapters), 10):
            batch = old_chapters[i:i+10]
            if not batch:
                continue
            
            start_ch = batch[0].chapter_number
            end_ch = batch[-1].chapter_number
            
            # 合并摘要
            summaries = [ch.summary for ch in batch if ch.summary]
            combined_summary = "\n".join(summaries) if summaries else f"第{start_ch}-{end_ch}章"
            
            # 创建记忆节点
            node_data = MemoryNodeCreate(
                novel_id=novel_id,
                node_type="plot_point",
                title=f"第{start_ch}-{end_ch}章剧情摘要",
                content=combined_summary,
                chapter_range=f"{start_ch}-{end_ch}",
                importance_score=0.6,
            )
            await self.create_node(node_data)
            nodes_created += 1
        
        return {
            "novel_id": novel_id,
            "chapters_processed": len(old_chapters),
            "nodes_created": nodes_created,
            "message": f"已整理{len(old_chapters)}章，创建{nodes_created}个记忆节点"
        }
