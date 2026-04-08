"""
工作流任务处理器
处理后台异步任务
"""
from loguru import logger

from app.core.task_queue import task_handler
from app.core.database import get_session
from app.core.websocket import WebSocketNotifier
from app.services.chapter_service import ChapterService
from app.services.novel_service import NovelService
from app.services.memory_service import MemoryService


@task_handler("generate_chapter")
async def handle_generate_chapter(payload: dict) -> dict:
    """
    处理章节生成任务
    
    Args:
        payload: 包含 novel_id, chapter_number, outline 等
        
    Returns:
        生成结果
    """
    novel_id = payload.get("novel_id")
    chapter_number = payload.get("chapter_number")
    
    logger.info(f"开始生成章节: novel_id={novel_id}, chapter={chapter_number}")
    
    try:
        async with get_session() as db:
            # 获取服务实例
            chapter_service = ChapterService(db)
            novel_service = NovelService(db)
            memory_service = MemoryService(db)
            
            # 构建上下文
            context = await memory_service.build_context(novel_id, chapter_number)
            
            # TODO: 调用章节撰写Agent生成内容
            # 这里使用模拟数据，实际使用时接入真实Agent
            chapter_data = {
                "novel_id": novel_id,
                "chapter_number": chapter_number,
                "title": f"第{chapter_number}章 新的篇章",
                "content": f"这是第{chapter_number}章的内容。\n\n（此处为模拟内容，实际使用时将由AI生成）\n\n在这一章中，故事继续发展...",
                "summary": f"第{chapter_number}章故事发展",
                "key_events": ["事件1", "事件2"],
                "characters_present": ["主角"],
            }
            
            # 创建章节
            from app.schemas.chapter import ChapterCreate
            chapter = await chapter_service.create_chapter(
                ChapterCreate(**chapter_data)
            )
            
            # 更新小说进度
            await novel_service.update_progress(
                novel_id,
                chapter_number,
                chapter.word_count
            )
            
            # 通知客户端
            await WebSocketNotifier.notify_chapter_generated(
                novel_id,
                chapter.to_dict()
            )
            
            logger.info(f"章节生成完成: {chapter.id}")
            
            return {
                "success": True,
                "chapter_id": chapter.id,
                "chapter_number": chapter_number,
                "word_count": chapter.word_count
            }
            
    except Exception as e:
        logger.error(f"章节生成失败: {e}")
        raise


@task_handler("generate_outline")
async def handle_generate_outline(payload: dict) -> dict:
    """
    处理大纲生成任务
    
    Args:
        payload: 包含 novel_id, genre, characters 等
        
    Returns:
        生成结果
    """
    novel_id = payload.get("novel_id")
    
    logger.info(f"开始生成大纲: novel_id={novel_id}")
    
    try:
        async with get_session() as db:
            from app.services.outline_service import OutlineService
            
            outline_service = OutlineService(db)
            
            # TODO: 调用大纲生成Agent
            # 这里使用模拟数据
            volumes = [
                {
                    "volume_number": 1,
                    "volume_title": "初入江湖",
                    "arcs": [
                        {
                            "arc_id": "arc_1",
                            "title": "觉醒篇",
                            "description": "主角发现自身特殊能力",
                            "start_chapter": 1,
                            "end_chapter": 30,
                            "key_events": ["觉醒", "试炼", "突破"],
                        }
                    ],
                    "target_chapters": 100,
                },
                {
                    "volume_number": 2,
                    "volume_title": "成长之路",
                    "arcs": [],
                    "target_chapters": 100,
                },
                {
                    "volume_number": 3,
                    "volume_title": "巅峰对决",
                    "arcs": [],
                    "target_chapters": 100,
                }
            ]
            
            # 创建大纲记录
            from app.schemas.outline import OutlineCreate
            for volume in volumes:
                await outline_service.create_outline(
                    OutlineCreate(
                        novel_id=novel_id,
                        volume_number=volume["volume_number"],
                        volume_title=volume["volume_title"],
                        arcs=volume.get("arcs", []),
                        target_chapters=volume["target_chapters"],
                    )
                )
            
            # 通知客户端
            await WebSocketNotifier.notify_state_update(
                novel_id,
                {
                    "message": "大纲生成完成",
                    "volumes_count": len(volumes)
                }
            )
            
            logger.info(f"大纲生成完成: {len(volumes)}卷")
            
            return {
                "success": True,
                "volumes_count": len(volumes)
            }
            
    except Exception as e:
        logger.error(f"大纲生成失败: {e}")
        raise


@task_handler("consolidate_memory")
async def handle_consolidate_memory(payload: dict) -> dict:
    """
    处理记忆整理任务
    
    Args:
        payload: 包含 novel_id, chapter_threshold 等
        
    Returns:
        整理结果
    """
    novel_id = payload.get("novel_id")
    chapter_threshold = payload.get("chapter_threshold", 50)
    
    logger.info(f"开始整理记忆: novel_id={novel_id}")
    
    try:
        async with get_session() as db:
            from app.services.memory_service import MemoryService
            
            memory_service = MemoryService(db)
            result = await memory_service.consolidate_memory(
                novel_id,
                chapter_threshold
            )
            
            logger.info(f"记忆整理完成: {result}")
            
            return result
            
    except Exception as e:
        logger.error(f"记忆整理失败: {e}")
        raise
