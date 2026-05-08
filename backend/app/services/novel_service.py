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

    async def hard_delete_novel(self, novel_id: int) -> dict:
        """
        彻底删除小说及其所有关联数据。
        删除内容：
        - 数据库中小说、章节、角色、大纲记录（CASCADE）
        - 本地文件目录 output/novel_{id}/
        - Qdrant 向量库中的记忆数据
        """
        novel = await self.get_novel(novel_id)
        if not novel:
            return {"success": False, "detail": "小说不存在"}

        novel_title = novel.title
        deleted_files = []

        # 1. 删除本地文件目录
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        output_dir = project_root / "output" / f"novel_{novel_id}"
        if output_dir.exists():
            import shutil
            shutil.rmtree(output_dir)
            deleted_files.append(str(output_dir))
            logger.info(f"删除本地目录: {output_dir}")

        # 2. 删除 Qdrant 中的向量记忆
        try:
            from app.core.qdrant_client import qdrant_client
            from app.core.config import settings
            try:
                qdrant_client.delete_collection(collection_name=settings.QDRANT_COLLECTION + f"_novel_{novel_id}")
                logger.info(f"删除 Qdrant collection: novel_{novel_id}")
            except Exception as e:
                logger.warning(f"Qdrant collection 删除跳过: {e}")
        except Exception as e:
            logger.warning(f"Qdrant 连接失败，跳过向量清理: {e}")

        # 3. 数据库硬删除（会级联删除 chapters/characters/outlines）
        from app.models.chapter import Chapter
        from app.models.character import Character
        from app.models.outline import Outline
        from app.models.memory_node import MemoryNode
        from sqlalchemy import delete

        # 先删除 memory_nodes（可能不在 CASCADE 链上）
        await self.db.execute(
            delete(MemoryNode).where(MemoryNode.novel_id == novel_id)
        )

        await self.db.delete(novel)
        await self.db.commit()
        logger.info(f"彻底删除小说: {novel_title} (ID: {novel_id})")

        return {
            "success": True,
            "detail": f"小说「{novel_title}」已彻底删除",
            "deleted_files": deleted_files,
        }

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
