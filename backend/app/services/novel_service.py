"""
小说服务层
处理小说的业务逻辑
"""
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.models.novel import Novel, NovelStatus
from app.schemas.novel import NovelCreate, NovelUpdate


class NovelService:
    """小说服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_novel(self, novel_data: NovelCreate) -> Novel:
        """创建新小说"""
        novel = Novel(
            title=novel_data.title,
            genre=novel_data.genre,
            style_prompt=novel_data.style_prompt,
            target_chapters=novel_data.target_chapters,
            words_per_chapter=novel_data.words_per_chapter,
            status=NovelStatus.planning,
        )
        self.db.add(novel)
        await self.db.commit()
        await self.db.refresh(novel)
        logger.info(f"创建小说: {novel.title} (ID: {novel.id})")
        return novel
    
    async def get_novel(self, novel_id: int) -> Optional[Novel]:
        """获取小说详情"""
        result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id, Novel.is_deleted == False)
        )
        return result.scalar_one_or_none()
    
    async def list_novels(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[Novel], int]:
        """获取小说列表"""
        query = select(Novel).where(Novel.is_deleted == False)
        
        if status:
            query = query.where(Novel.status == status)
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # 获取分页数据
        query = query.offset(skip).limit(limit).order_by(Novel.created_at.desc())
        result = await self.db.execute(query)
        novels = result.scalars().all()
        
        return list(novels), total
    
    async def update_novel(self, novel_id: int, novel_data: NovelUpdate) -> Optional[Novel]:
        """更新小说信息"""
        novel = await self.get_novel(novel_id)
        if not novel:
            return None
        
        update_data = novel_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(novel, field, value)
        
        await self.db.commit()
        await self.db.refresh(novel)
        logger.info(f"更新小说: {novel.title} (ID: {novel.id})")
        return novel
    
    async def delete_novel(self, novel_id: int) -> bool:
        """软删除小说"""
        novel = await self.get_novel(novel_id)
        if not novel:
            return False
        
        novel.is_deleted = True
        await self.db.commit()
        logger.info(f"删除小说: {novel.title} (ID: {novel.id})")
        return True
    
    async def get_novel_stats(self, novel_id: int) -> Optional[dict]:
        """获取小说统计信息"""
        novel = await self.get_novel(novel_id)
        if not novel:
            return None
        
        from app.models.character import Character
        
        # 获取角色数量
        char_result = await self.db.execute(
            select(func.count()).where(Character.novel_id == novel_id)
        )
        character_count = char_result.scalar()
        
        # 计算完成百分比
        completion = (novel.current_chapter / novel.target_chapters * 100) if novel.target_chapters > 0 else 0
        
        # 计算平均字数
        avg_words = novel.total_words / novel.total_chapters if novel.total_chapters > 0 else 0
        
        return {
            "novel_id": novel.id,
            "title": novel.title,
            "total_chapters": novel.total_chapters,
            "total_words": novel.total_words,
            "avg_words_per_chapter": round(avg_words, 2),
            "character_count": character_count,
            "completion_percentage": round(completion, 2),
            "status": novel.status.value,
        }
    
    async def update_progress(self, novel_id: int, chapter_number: int, word_count: int):
        """更新小说进度"""
        novel = await self.get_novel(novel_id)
        if not novel:
            return
        
        novel.current_chapter = chapter_number
        novel.total_chapters = max(novel.total_chapters, chapter_number)
        novel.total_words += word_count
        
        # 自动更新状态
        if novel.current_chapter >= novel.target_chapters:
            novel.status = NovelStatus.COMPLETED
        elif novel.current_chapter > 0:
            novel.status = NovelStatus.writing
        
        await self.db.commit()
