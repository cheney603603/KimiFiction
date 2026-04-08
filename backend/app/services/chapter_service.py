"""
章节服务层
处理章节的业务逻辑和生成
"""
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.models.chapter import Chapter, ChapterStatus
from app.models.novel import Novel
from app.schemas.chapter import ChapterCreate, ChapterUpdate, ChapterGenerateRequest
from app.services.novel_service import NovelService


class ChapterService:
    """章节服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _count_words(self, text: str) -> int:
        """统计字数（中文字符+英文单词）"""
        import re
        # 中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 英文单词
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words
    
    async def create_chapter(self, chapter_data: ChapterCreate) -> Chapter:
        """创建章节"""
        word_count = self._count_words(chapter_data.content)
        
        chapter = Chapter(
            novel_id=chapter_data.novel_id,
            chapter_number=chapter_data.chapter_number,
            title=chapter_data.title,
            content=chapter_data.content,
            summary=chapter_data.summary,
            key_events=chapter_data.key_events or [],
            characters_present=chapter_data.characters_present or [],
            word_count=word_count,
            status=ChapterStatus.DRAFT,
        )
        self.db.add(chapter)
        await self.db.commit()
        await self.db.refresh(chapter)
        
        # 更新小说进度
        novel_service = NovelService(self.db)
        await novel_service.update_progress(
            chapter_data.novel_id,
            chapter_data.chapter_number,
            word_count
        )
        
        logger.info(f"创建章节: {chapter.title} (小说ID: {chapter.novel_id})")
        return chapter
    
    async def get_chapter(self, chapter_id: int) -> Optional[Chapter]:
        """获取章节详情"""
        result = await self.db.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        return result.scalar_one_or_none()
    
    async def get_chapter_by_number(self, novel_id: int, chapter_number: int) -> Optional[Chapter]:
        """根据序号获取章节"""
        result = await self.db.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number
            )
        )
        return result.scalar_one_or_none()
    
    async def list_chapters(
        self,
        novel_id: int,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None
    ) -> Tuple[List[Chapter], int]:
        """获取章节列表"""
        query = select(Chapter).where(Chapter.novel_id == novel_id)
        
        if status:
            query = query.where(Chapter.status == status)
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # 获取分页数据
        query = query.offset(skip).limit(limit).order_by(Chapter.chapter_number.asc())
        result = await self.db.execute(query)
        chapters = result.scalars().all()
        
        return list(chapters), total
    
    async def update_chapter(self, chapter_id: int, chapter_data: ChapterUpdate) -> Optional[Chapter]:
        """更新章节"""
        chapter = await self.get_chapter(chapter_id)
        if not chapter:
            return None
        
        update_data = chapter_data.model_dump(exclude_unset=True)
        
        # 如果更新了内容，重新计算字数
        if 'content' in update_data:
            update_data['word_count'] = self._count_words(update_data['content'])
        
        for field, value in update_data.items():
            setattr(chapter, field, value)
        
        await self.db.commit()
        await self.db.refresh(chapter)
        logger.info(f"更新章节: {chapter.title} (ID: {chapter.id})")
        return chapter
    
    async def delete_chapter(self, chapter_id: int) -> bool:
        """删除章节"""
        chapter = await self.get_chapter(chapter_id)
        if not chapter:
            return False
        
        await self.db.delete(chapter)
        await self.db.commit()
        logger.info(f"删除章节: ID {chapter_id}")
        return True
    
    async def get_chapter_content(self, chapter_id: int) -> Optional[str]:
        """获取章节内容"""
        chapter = await self.get_chapter(chapter_id)
        return chapter.content if chapter else None
    
    async def get_recent_chapters(self, novel_id: int, count: int = 3) -> List[Chapter]:
        """获取最近N章"""
        result = await self.db.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_number.desc())
            .limit(count)
        )
        return list(result.scalars().all())
    
    async def start_generation(self, request: ChapterGenerateRequest) -> dict:
        """启动章节生成任务"""
        from app.core.task_queue import task_queue, TaskPriority
        
        # 确定章节号
        chapter_number = request.chapter_number
        if chapter_number is None:
            # 自动续写下一章
            novel_result = await self.db.execute(
                select(func.max(Chapter.chapter_number)).where(
                    Chapter.novel_id == request.novel_id
                )
            )
            max_chapter = novel_result.scalar() or 0
            chapter_number = max_chapter + 1
        
        # 将生成任务添加到队列
        task_id = await task_queue.enqueue(
            task_type="generate_chapter",
            payload={
                "novel_id": request.novel_id,
                "chapter_number": chapter_number,
                "outline_guidance": request.outline_guidance,
                "temperature": request.temperature,
            },
            priority=TaskPriority.NORMAL
        )
        
        logger.info(f"启动章节生成任务: {task_id}, 小说ID: {request.novel_id}, 章节: {chapter_number}")
        
        return {
            "task_id": task_id,
            "status": "pending",
            "novel_id": request.novel_id,
            "chapter_number": chapter_number,
            "message": "生成任务已创建，正在排队"
        }
