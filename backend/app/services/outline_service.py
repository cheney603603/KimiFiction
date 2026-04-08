"""
大纲服务层
处理大纲的业务逻辑
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.models.outline import Outline
from app.schemas.outline import OutlineCreate, OutlineUpdate, OutlineGenerateRequest


class OutlineService:
    """大纲服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_outline(self, outline_data: OutlineCreate) -> Outline:
        """创建大纲"""
        outline = Outline(
            novel_id=outline_data.novel_id,
            volume_number=outline_data.volume_number,
            volume_title=outline_data.volume_title,
            arcs=outline_data.arcs or [],
            key_points=outline_data.key_points,
            target_chapters=outline_data.target_chapters,
        )
        self.db.add(outline)
        await self.db.commit()
        await self.db.refresh(outline)
        logger.info(f"创建大纲: {outline.volume_title} (小说ID: {outline.novel_id})")
        return outline
    
    async def get_outline(self, outline_id: int) -> Optional[Outline]:
        """获取大纲详情"""
        result = await self.db.execute(
            select(Outline).where(Outline.id == outline_id)
        )
        return result.scalar_one_or_none()
    
    async def list_outlines(self, novel_id: int) -> List[Outline]:
        """获取小说的大纲列表"""
        result = await self.db.execute(
            select(Outline)
            .where(Outline.novel_id == novel_id)
            .order_by(Outline.volume_number.asc())
        )
        return list(result.scalars().all())
    
    async def update_outline(self, outline_id: int, outline_data: OutlineUpdate) -> Optional[Outline]:
        """更新大纲"""
        outline = await self.get_outline(outline_id)
        if not outline:
            return None
        
        update_data = outline_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(outline, field, value)
        
        await self.db.commit()
        await self.db.refresh(outline)
        logger.info(f"更新大纲: {outline.volume_title} (ID: {outline.id})")
        return outline
    
    async def delete_outline(self, outline_id: int) -> bool:
        """删除大纲"""
        outline = await self.get_outline(outline_id)
        if not outline:
            return False
        
        await self.db.delete(outline)
        await self.db.commit()
        logger.info(f"删除大纲: ID {outline_id}")
        return True
    
    async def update_actual_chapters(self, outline_id: int, actual_count: int):
        """更新实际章节数"""
        outline = await self.get_outline(outline_id)
        if outline:
            outline.actual_chapters = actual_count
            await self.db.commit()
    
    async def generate_outline(self, request: OutlineGenerateRequest) -> dict:
        """生成大纲（调用AI）"""
        import uuid
        
        task_id = str(uuid.uuid4())
        
        # TODO: 将生成任务添加到队列
        logger.info(f"启动大纲生成任务: {task_id}, 小说ID: {request.novel_id}")
        
        return {
            "task_id": task_id,
            "status": "pending",
            "novel_id": request.novel_id,
            "message": "大纲生成任务已创建，正在排队"
        }
    
    async def get_outline_for_chapter(self, novel_id: int, chapter_number: int) -> Optional[dict]:
        """获取指定章节对应的大纲信息"""
        outlines = await self.list_outlines(novel_id)
        
        current_volume = None
        current_arc = None
        
        for outline in outlines:
            # 计算该卷的章节范围
            prev_chapters = sum(o.target_chapters for o in outlines if o.volume_number < outline.volume_number)
            start_chapter = prev_chapters + 1
            end_chapter = prev_chapters + outline.target_chapters
            
            if start_chapter <= chapter_number <= end_chapter:
                current_volume = outline
                
                # 在卷内查找对应的剧情弧
                chapter_in_volume = chapter_number - prev_chapters
                for arc in outline.arcs:
                    if arc.get('start_chapter', 0) <= chapter_in_volume <= arc.get('end_chapter', 0):
                        current_arc = arc
                        break
                break
        
        if not current_volume:
            return None
        
        return {
            "volume": {
                "number": current_volume.volume_number,
                "title": current_volume.volume_title,
                "summary": current_volume.summary,
            },
            "arc": current_arc,
            "key_points": current_volume.key_points,
        }
