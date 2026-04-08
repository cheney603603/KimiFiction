"""
工作流控制API
支持新版多Agent协作工作流
"""
import asyncio
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db
from app.core.websocket import websocket_manager
from app.core.redis_client import WorkflowLogsManager
from app.core.progress_tracker import (
    get_progress_tracker, 
    ProgressTracker, 
    ProgressStatus,
    remove_progress_tracker
)
from app.core.llm_config_manager import llm_config
from app.services.workflow_service import WorkflowService
from app.workflow_engine import get_workflow_engine, WorkflowPhase
from app.schemas.workflow import (
    # 新版请求/响应
    WorkflowPhaseRequest,
    WorkflowProgressResponse,
    TaskResultResponse,
    ChapterWriteRequest,
    ChapterRevisionRequest,
    WorkflowSnapshotResponse,
    ConfirmRequest,
    # 兼容旧版
    WorkflowStartRequest,
    WorkflowResponse,
    UserInputRequest,
    GenreAnalysisRequest,
    GenreAnalysisResponse,
)

router = APIRouter()


# ===== 新版工作流API =====

@router.get("/progress/{novel_id}", response_model=WorkflowProgressResponse)
async def get_workflow_progress(novel_id: int):
    """获取工作流进度"""
    try:
        engine = await get_workflow_engine(novel_id)
        return engine.get_progress()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/phase-result/{novel_id}/{phase}")
async def get_phase_result(novel_id: int, phase: str):
    """获取指定阶段的结果数据"""
    try:
        engine = await get_workflow_engine(novel_id)
        
        if not engine.state:
            raise HTTPException(status_code=404, detail="工作流状态不存在")
        
        # 根据阶段返回对应的数据
        phase_data_map = {
            "demand_analysis": engine.state.demand_analysis,
            "world_building": engine.state.world_setting,
            "character_design": {"characters": engine.state.characters} if engine.state.characters else None,
            "plot_design": engine.state.plot_setting,
            "outline_draft": engine.state.outline,
            "outline_detail": {"chapter_outlines": engine.state.chapter_outlines} if (engine.state.chapter_outlines or WorkflowPhase.OUTLINE_DETAIL in engine.state.phase_history) else None,
        }
        
        data = phase_data_map.get(phase)
        
        if data is None:
            return {
                "success": True,
                "phase": phase,
                "data": None,
                "message": "该阶段尚未完成或没有数据"
            }
        
        return {
            "success": True,
            "phase": phase,
            "data": data,
            "message": "获取成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取阶段结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extend-outlines/{novel_id}")
async def extend_chapter_outlines(novel_id: int, target_chapters: int = 30):
    """扩展章节细纲到指定章数"""
    try:
        engine = await get_workflow_engine(novel_id)
        
        if not engine.state:
            raise HTTPException(status_code=404, detail="工作流状态不存在")
        
        existing_outlines = engine.state.chapter_outlines or []
        current_count = len(existing_outlines)
        
        if current_count >= target_chapters:
            return {
                "success": True,
                "message": f"已有{current_count}章细纲，无需扩展",
                "total_outlines": current_count
            }
        
        # 创建新章节细纲
        new_outlines = []
        for ch in range(current_count + 1, target_chapters + 1):
            outline = {
                "chapter_number": ch,
                "title": f"第{ch}章",
                "summary": f"本章继续推进规则怪谈的主线剧情，揭示新的规则和危险。主角面临更严峻的考验，需要在诡异规则中寻找生存之道。",
                "key_points": ["推进主线剧情", "揭示新规则或新危险", "角色心理变化", "为下一章埋下伏笔"],
                "scenes": [{"scene_name": "主场景", "description": "本章主要发生地点"}],
                "word_count_target": 3000
            }
            new_outlines.append(outline)
        
        # 合并并保存
        all_outlines = existing_outlines + new_outlines
        engine.state.chapter_outlines = all_outlines
        await engine.save_state()
        
        # 同时更新数据库中的 outlines 表
        try:
            from app.core.database import get_session
            from app.models.outline import Outline
            from sqlalchemy import select
            
            async with get_session() as db:
                # 查找 detail 类型的 outline
                stmt = select(Outline).where(Outline.novel_id == novel_id)
                result = await db.execute(stmt)
                outlines = result.scalars().all()
                
                detail_outline = None
                for o in outlines:
                    if o.outline_type == "detail" or "细纲" in (o.volume_title or ""):
                        detail_outline = o
                        break
                
                if detail_outline:
                    detail_outline.content = json.dumps(all_outlines, ensure_ascii=False)
                else:
                    detail_outline = Outline(
                        novel_id=novel_id,
                        volume_number=1,
                        volume_title="章节细纲",
                        content=json.dumps(all_outlines, ensure_ascii=False),
                        outline_type="detail",
                    )
                    db.add(detail_outline)
                await db.commit()
        except Exception as db_error:
            logger.error(f"更新outlines表失败: {db_error}")
        
        return {
            "success": True,
            "message": f"已扩展细纲从{current_count}章到{target_chapters}章",
            "previous_count": current_count,
            "new_count": target_chapters,
            "added": len(new_outlines)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"扩展章节细纲失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/phase-prompt/{novel_id}/{phase}")
async def get_phase_prompt_info(novel_id: int, phase: str):
    """获取指定阶段的提示词构建信息"""
    try:
        engine = await get_workflow_engine(novel_id)
        
        if not engine.state:
            raise HTTPException(status_code=404, detail="工作流状态不存在")
        
        # 从阶段结果中提取提示词构建信息
        phase_data_map = {
            "demand_analysis": engine.state.demand_analysis,
            "world_building": engine.state.world_setting,
            "character_design": {"characters": engine.state.characters} if engine.state.characters else None,
            "plot_design": engine.state.plot_setting,
            "outline_draft": engine.state.outline,
            "outline_detail": {"chapter_outlines": engine.state.chapter_outlines} if (engine.state.chapter_outlines or WorkflowPhase.OUTLINE_DETAIL in engine.state.phase_history) else None,
        }
        
        data = phase_data_map.get(phase)
        
        if not data:
            return {
                "success": True,
                "phase": phase,
                "prompt_info": None,
                "message": "该阶段尚未完成或没有提示词信息"
            }
        
        # 提取提示词构建信息
        prompt_info = data.get("_prompt_build_info", {})
        
        return {
            "success": True,
            "phase": phase,
            "prompt_info": prompt_info,
            "message": "获取成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取提示词信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/phase-toggle/{novel_id}/{phase}")
async def toggle_phase_completion(novel_id: int, phase: str, request: WorkflowPhaseRequest):
    """手动切换阶段完成状态"""
    try:
        engine = await get_workflow_engine(novel_id)
        
        if not engine.state:
            raise HTTPException(status_code=404, detail="工作流状态不存在")
        
        # 解析阶段
        try:
            target_phase = WorkflowPhase(phase)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的阶段: {phase}")
        
        # 检查当前阶段是否已完成（有数据）
        phase_data_map = {
            "demand_analysis": engine.state.demand_analysis,
            "world_building": engine.state.world_setting,
            "character_design": engine.state.characters,
            "plot_design": engine.state.plot_setting,
            "outline_draft": engine.state.outline,
            "outline_detail": engine.state.chapter_outlines,
        }
        
        current_data = phase_data_map.get(phase)
        # 修复：对于列表类型，即使为空数组也算有数据（用户手动标记完成的情况）
        is_completed = current_data is not None
        
        if is_completed:
            # 标记为未完成 - 清除数据
            if phase == "demand_analysis":
                engine.state.demand_analysis = None
            elif phase == "world_building":
                engine.state.world_setting = None
            elif phase == "character_design":
                engine.state.characters = []
            elif phase == "plot_design":
                engine.state.plot_setting = None
            elif phase == "outline_draft":
                engine.state.outline = None
            elif phase == "outline_detail":
                engine.state.chapter_outlines = []
            
            # 从phase_history中移除
            if target_phase in engine.state.phase_history:
                engine.state.phase_history.remove(target_phase)
            
            await engine.save_state()
            
            return {
                "success": True,
                "phase": phase,
                "completed": False,
                "message": f"已将 {phase} 标记为未完成"
            }
        else:
            # 标记为完成 - 添加空数据或用户提供的input_data
            input_data = request.input_data or {"manually_marked": True, "timestamp": datetime.now().isoformat()}

            if phase == "demand_analysis":
                engine.state.demand_analysis = input_data
            elif phase == "world_building":
                engine.state.world_setting = input_data
            elif phase == "character_design":
                characters = input_data.get("characters", [])
                engine.state.characters = characters
                # 同步角色到数据库（修复手动标记完成时不同步的问题）
                if characters and isinstance(characters, list):
                    await engine._sync_characters_to_db(characters)
            elif phase == "plot_design":
                engine.state.plot_setting = input_data
            elif phase == "outline_draft":
                engine.state.outline = input_data
            elif phase == "outline_detail":
                engine.state.chapter_outlines = input_data.get("chapter_outlines", [])

            # 添加到phase_history
            if target_phase not in engine.state.phase_history:
                engine.state.phase_history.append(target_phase)

            await engine.save_state()
            
            return {
                "success": True,
                "phase": phase,
                "completed": True,
                "message": f"已将 {phase} 标记为完成"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换阶段完成状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task-progress/{task_id}")
async def get_task_progress(task_id: str):
    """获取任务执行进度（用于轮询）"""
    progress = await ProgressTracker.get_progress(task_id)
    if not progress:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return progress


async def _execute_phase_with_progress(
    novel_id: int,
    phase: WorkflowPhase,
    input_data: dict,
    tracker: ProgressTracker,
    timeout: Optional[int] = None
):
    """在后台执行阶段并跟踪进度"""
    step_id = f"phase_{phase.value}"
    step = tracker.add_step(
        step_id=step_id,
        name=f"执行{phase.value}",
        description=f"执行工作流阶段: {phase.value}",
        total_substeps=4
    )
    tracker.set_current_step(step_id)

    try:
        # 步骤1: 初始化引擎
        await tracker.update_substep(step_id, 1, "初始化工作流引擎...")
        engine = await get_workflow_engine(novel_id)

        # 步骤2: 准备执行
        await tracker.update_substep(step_id, 2, f"准备执行阶段: {phase.value}")

        # 步骤3: 调用LLM（可能耗时较长）
        await tracker.update_step_status(step_id, ProgressStatus.LLM_CALLING, "调用AI模型...")

        # 确定超时时间：优先使用手动设置的timeout，否则根据阶段自动计算
        if timeout is None:
            base_timeout = llm_config.get_timeout()
            # 后面的阶段需要更长的超时时间
            phase_timeout_map = {
                WorkflowPhase.DEMAND_ANALYSIS: base_timeout,
                WorkflowPhase.WORLD_BUILDING: base_timeout * 1.2,
                WorkflowPhase.CHARACTER_DESIGN: base_timeout * 1.5,
                WorkflowPhase.PLOT_DESIGN: base_timeout * 1.5,
                WorkflowPhase.OUTLINE_DRAFT: base_timeout * 2.0,
                WorkflowPhase.OUTLINE_DETAIL: base_timeout * 2.5,
            }
            timeout = int(phase_timeout_map.get(phase, base_timeout))

        await tracker.add_log(step_id, f"设置超时时间: {timeout}秒", "info")

        result = await asyncio.wait_for(
            engine.run_phase(phase, input_data, timeout),
            timeout=timeout
        )
        
        # 步骤4: 处理结果
        await tracker.update_step_status(step_id, ProgressStatus.PROCESSING, "处理AI响应...")
        await tracker.update_substep(step_id, 4, "完成")
        
        if result.success:
            await tracker.complete_step(step_id, f"阶段 {phase.value} 执行成功")
        else:
            await tracker.fail_step(step_id, result.error or "未知错误")
            
    except asyncio.TimeoutError:
        logger.error(f"阶段 {phase.value} 执行超时")
        await tracker.fail_step(step_id, f"执行超时（超过{timeout}秒），请检查LLM服务是否正常")
    except Exception as e:
        logger.error(f"阶段 {phase.value} 执行失败: {e}")
        await tracker.fail_step(step_id, str(e))


@router.post("/phase-switch/{novel_id}")
async def switch_workflow_phase(novel_id: int, request: WorkflowPhaseRequest):
    """只切换阶段，不执行（用于"进入下一阶段"按钮）"""
    try:
        engine = await get_workflow_engine(novel_id)
        phase = WorkflowPhase(request.phase)
        
        # 只改变当前阶段，不执行任何任务
        await engine.transition_to(phase)
        
        logger.info(f"阶段切换: novel_id={novel_id}, phase={phase.value}")
        
        return {
            "success": True,
            "message": f"已切换到{phase.value}阶段",
            "current_phase": phase.value
        }
    except Exception as e:
        logger.error(f"阶段切换失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/phase/{novel_id}")
async def execute_workflow_phase(
    novel_id: int,
    request: WorkflowPhaseRequest,
    background_tasks: BackgroundTasks
):
    """执行指定工作流阶段（异步）"""
    task_id = f"novel_{novel_id}_phase_{request.phase}_{int(asyncio.get_event_loop().time())}"

    try:
        # 创建进度追踪器
        tracker = get_progress_tracker(task_id)

        # 在后台执行
        phase = WorkflowPhase(request.phase)
        background_tasks.add_task(
            _execute_phase_with_progress,
            novel_id,
            phase,
            request.input_data,
            tracker,
            request.timeout  # 传递超时参数
        )

        # 立即返回任务ID，前端可以用它来轮询进度
        return {
            "success": True,
            "task_id": task_id,
            "message": f"已开始执行阶段: {request.phase}",
            "status": "running"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"启动阶段执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chapter/{novel_id}")
async def write_chapter(
    novel_id: int,
    request: ChapterWriteRequest,
    background_tasks: BackgroundTasks
):
    """撰写指定章节（异步）"""
    task_id = f"novel_{novel_id}_chapter_{request.chapter_number}_{int(asyncio.get_event_loop().time())}"
    
    try:
        # 快速检查：章节细纲是否存在
        engine = await get_workflow_engine(novel_id)
        chapter_outline = None
        for co in (engine.state.chapter_outlines or []):
            if isinstance(co, dict) and co.get("chapter_number") == request.chapter_number:
                chapter_outline = co
                break
        
        if not chapter_outline or not chapter_outline.get("summary"):
            raise HTTPException(
                status_code=400,
                detail=f"第{request.chapter_number}章缺少有效的章节细纲，无法撰写。请先在「工作流」->「章节细纲」阶段完成本章细纲设计。"
            )
        
        tracker = get_progress_tracker(task_id)
        step = tracker.add_step(
            step_id="write_chapter",
            name=f"撰写第{request.chapter_number}章",
            description="生成章节内容",
            total_substeps=3
        )
        tracker.set_current_step("write_chapter")
        
        # 构造写作参数
        writing_params = {
            "writing_style": request.writing_style,
            "env_description_level": request.env_description_level or "normal",
            "dialogue_ratio": request.dialogue_ratio if request.dialogue_ratio is not None else 0.3,
            "notes": request.notes,
        }
        
        async def _write():
            try:
                await tracker.update_substep("write_chapter", 1, "初始化写作引擎...")
                engine = await get_workflow_engine(novel_id)
                
                await tracker.update_substep("write_chapter", 2, "调用AI撰写章节...")
                # 设置超时（章节写作可能需要更长时间）
                base_timeout = llm_config.get_timeout()
                # 如果请求中指定了timeout，使用请求中的值，否则使用默认3倍
                timeout = request.timeout if request.timeout else base_timeout * 3
                await tracker.add_log("write_chapter", f"设置超时时间: {timeout}秒", "info")
                
                result = await asyncio.wait_for(
                    engine.write_chapter(
                        chapter_number=request.chapter_number,
                        outline=request.outline,
                        auto_mode=request.auto_mode,
                        writing_params=writing_params,
                    ),
                    timeout=timeout
                )
                
                await tracker.update_substep("write_chapter", 3, "完成")
                
                if result.success:
                    await tracker.complete_step("write_chapter", f"第{request.chapter_number}章撰写完成")
                    
                    # 自动保存生成的章节到数据库
                    try:
                        from app.core.database import get_session
                        from app.services.chapter_service import ChapterService
                        from app.schemas.chapter import ChapterCreate, ChapterUpdate
                        import json as _json
                        
                        async with get_session() as db:
                            chapter_service = ChapterService(db)
                            
                            # 从工作流状态获取对应章节的细纲（优先于 request.outline）
                            engine_state = engine.state
                            chapter_outline = {}
                            if engine_state and engine_state.chapter_outlines:
                                for co in engine_state.chapter_outlines:
                                    if isinstance(co, dict) and co.get("chapter_number") == request.chapter_number:
                                        chapter_outline = co
                                        break
                            
                            outline_data = chapter_outline or (request.outline or {})
                            title = outline_data.get("title", f"第{request.chapter_number}章")
                            summary = outline_data.get("summary", "")
                            
                            content = result.data.get("content", "")
                            word_count = result.data.get("word_count", 0)
                            
                            # 验证内容：如果 content 是 JSON 数组（细纲被错误存入），则跳过保存
                            if content and content.strip().startswith("["):
                                try:
                                    _json.loads(content)
                                    logger.warning(f"[write_chapter] 检测到内容是JSON数组（可能是细纲数据），跳过保存。chapter={request.chapter_number}, content_len={len(content)}")
                                    await tracker.add_log("write_chapter", "内容验证失败：检测到JSON数组而非小说正文，已跳过保存", "error")
                                except _json.JSONDecodeError:
                                    pass  # 不是合法 JSON，继续正常保存
                            
                            if not content or not content.strip().startswith("["):
                                existing = await chapter_service.get_chapter_by_number(novel_id, request.chapter_number)
                                
                                # 收集读者反馈数据
                                reader_feedback = result.data.get("reader_feedback", {})
                                loop_history = result.data.get("writer_reader_loop_history", [])
                                editor_review = result.data.get("editor_review", {})
                                feedbacks_data = {}
                                if reader_feedback:
                                    feedbacks_data["reader_feedback"] = reader_feedback
                                if loop_history:
                                    feedbacks_data["loop_history"] = loop_history
                                if editor_review:
                                    feedbacks_data["editor_review"] = editor_review
                                feedbacks_json = _json.dumps(feedbacks_data, ensure_ascii=False) if feedbacks_data else None
                                
                                if existing:
                                    await chapter_service.update_chapter(
                                        existing.id,
                                        ChapterUpdate(
                                            title=title,
                                            content=content,
                                            summary=summary,
                                        )
                                    )
                                    # 单独更新 feedbacks 字段（ChapterUpdate 不含此字段）
                                    if feedbacks_json:
                                        from app.models.chapter import Chapter
                                        from sqlalchemy import select
                                        stmt = select(Chapter).where(Chapter.id == existing.id)
                                        chapter_row = (await db.execute(stmt)).scalar_one_or_none()
                                        if chapter_row:
                                            chapter_row.feedbacks = feedbacks_json
                                            await db.commit()
                                    logger.info(f"[write_chapter] 更新章节到数据库: novel_id={novel_id}, chapter={request.chapter_number}")
                                else:
                                    await chapter_service.create_chapter(
                                        ChapterCreate(
                                            novel_id=novel_id,
                                            chapter_number=request.chapter_number,
                                            title=title,
                                            content=content,
                                            summary=summary,
                                        )
                                    )
                                    # 保存 feedbacks
                                    if feedbacks_json:
                                        from app.models.chapter import Chapter
                                        from sqlalchemy import select
                                        stmt = select(Chapter).where(Chapter.novel_id == novel_id, Chapter.chapter_number == request.chapter_number)
                                        chapter_row = (await db.execute(stmt)).scalar_one_or_none()
                                        if chapter_row:
                                            chapter_row.feedbacks = feedbacks_json
                                            await db.commit()
                                    logger.info(f"[write_chapter] 创建章节到数据库: novel_id={novel_id}, chapter={request.chapter_number}, words={word_count}")
                        await tracker.add_log("write_chapter", "章节已自动保存到数据库", "info")
                    except Exception as save_error:
                        logger.error(f"[write_chapter] 自动保存章节失败: {save_error}")
                        await tracker.add_log("write_chapter", f"自动保存失败: {save_error}", "error")
                else:
                    await tracker.fail_step("write_chapter", result.error or "撰写失败")
                    
            except asyncio.TimeoutError:
                await tracker.fail_step("write_chapter", f"撰写超时（超过{timeout}秒）")
            except Exception as e:
                await tracker.fail_step("write_chapter", str(e))
        
        background_tasks.add_task(_write)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": f"已开始撰写第{request.chapter_number}章",
            "status": "running"
        }
        
    except Exception as e:
        logger.error(f"启动章节撰写失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chapter-feedback/{novel_id}/{chapter_number}")
async def get_chapter_feedback(novel_id: int, chapter_number: int):
    """获取章节的读者反馈和写作历史"""
    try:
        from app.core.database import get_session
        from app.services.chapter_service import ChapterService
        import json
        
        async with get_session() as db:
            chapter_service = ChapterService(db)
            chapter = await chapter_service.get_chapter_by_number(novel_id, chapter_number)
            if not chapter:
                raise HTTPException(status_code=404, detail="章节不存在")
            
            # 解析 feedbacks JSON 字段
            feedbacks = {}
            feedbacks_raw = getattr(chapter, 'feedbacks', None) or chapter.feedbacks if hasattr(chapter, 'feedbacks') else None
            if feedbacks_raw:
                if isinstance(feedbacks_raw, str):
                    try:
                        feedbacks = json.loads(feedbacks_raw)
                    except json.JSONDecodeError:
                        feedbacks = {"raw": feedbacks_raw}
                elif isinstance(feedbacks_raw, dict):
                    feedbacks = feedbacks_raw
            
            return {
                "success": True,
                "chapter_number": chapter_number,
                "title": chapter.title,
                "reader_feedback": feedbacks.get("reader_feedback", {}),
                "loop_history": feedbacks.get("loop_history", []),
                "editor_review": feedbacks.get("editor_review", {}),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取章节反馈失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/revise/{novel_id}", response_model=TaskResultResponse)
async def revise_chapter(
    novel_id: int,
    request: ChapterRevisionRequest
):
    """修订章节"""
    try:
        engine = await get_workflow_engine(novel_id)
        result = await engine.revise_chapter(
            chapter_number=request.chapter_number,
            feedback=request.feedback,
            scope=request.scope
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause/{novel_id}")
async def pause_workflow(novel_id: int):
    """暂停工作流"""
    try:
        engine = await get_workflow_engine(novel_id)
        success = await engine.pause()
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume/{novel_id}")
async def resume_workflow(novel_id: int):
    """恢复工作流"""
    try:
        engine = await get_workflow_engine(novel_id)
        success = await engine.resume()
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm/{novel_id}")
async def confirm_action(novel_id: int, request: ConfirmRequest):
    """确认操作"""
    try:
        engine = await get_workflow_engine(novel_id)
        await engine.confirm(request.confirmation, request.response)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshot/{novel_id}")
async def create_snapshot(novel_id: int, reason: str = "manual"):
    """创建状态快照"""
    try:
        from app.core.redis_client import WorkflowStateManager
        snapshot_id = await WorkflowStateManager.create_snapshot(
            f"workflow_{novel_id}",
            reason
        )
        return WorkflowSnapshotResponse(
            snapshot_id=snapshot_id or "",
            workflow_id=f"workflow_{novel_id}",
            reason=reason,
            created_at=""
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots/{workflow_id}")
async def list_snapshots(workflow_id: str):
    """列出所有快照"""
    try:
        from app.core.redis_client import WorkflowStateManager
        snapshots = await WorkflowStateManager.list_snapshots(workflow_id)
        return {"snapshots": snapshots}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshot/{workflow_id}/restore/{snapshot_id}")
async def restore_snapshot(workflow_id: str, snapshot_id: str):
    """从快照恢复"""
    try:
        from app.core.redis_client import WorkflowStateManager
        success = await WorkflowStateManager.restore_snapshot(workflow_id, snapshot_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== 兼容旧版API =====

@router.post("/start", response_model=WorkflowResponse)
async def start_workflow(
    request: WorkflowStartRequest,
    db: AsyncSession = Depends(get_db)
):
    """启动新小说工作流（兼容旧版）"""
    service = WorkflowService(db)
    result = await service.start_workflow(request)
    return result


@router.get("/state/{novel_id}")
async def get_workflow_state(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取工作流状态（兼容旧版）"""
    service = WorkflowService(db)
    state = await service.get_state(novel_id)
    if not state:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return state


@router.post("/analyze-genre", response_model=GenreAnalysisResponse)
async def analyze_genre(
    request: GenreAnalysisRequest,
    db: AsyncSession = Depends(get_db)
):
    """分析小说类型"""
    service = WorkflowService(db)
    result = await service.analyze_genre(request)
    return result


@router.post("/user-input/{novel_id}")
async def submit_user_input(
    novel_id: int,
    request: UserInputRequest,
    db: AsyncSession = Depends(get_db)
):
    """提交用户输入"""
    try:
        service = WorkflowService(db)
        result = await service.process_user_input(novel_id, request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"处理用户输入失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.post("/generate-characters/{novel_id}")
async def generate_characters(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """生成角色设计"""
    service = WorkflowService(db)
    result = await service.generate_characters(novel_id)
    return result


@router.post("/generate-outline/{novel_id}")
async def generate_outline(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """生成剧情大纲"""
    service = WorkflowService(db)
    result = await service.generate_outline(novel_id)
    return result


@router.post("/start-writing/{novel_id}")
async def start_writing(
    novel_id: int,
    auto_mode: bool = False,
    target_chapters: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """开始自动撰写"""
    service = WorkflowService(db)
    result = await service.start_writing(novel_id, auto_mode, target_chapters)
    return result


# ===== WebSocket实时通信 =====

@router.websocket("/ws/{novel_id}")
async def workflow_websocket(websocket: WebSocket, novel_id: int):
    """WebSocket实时推送工作流状态"""
    await websocket_manager.connect(websocket, novel_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            action = data.get("action")
            
            if action == "ping":
                await websocket_manager.send_to_client(
                    websocket,
                    {"type": "pong", "timestamp": __import__('time').time()}
                )
            
            elif action == "get_progress":
                try:
                    engine = await get_workflow_engine(novel_id)
                    progress = engine.get_progress()
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "progress", "data": progress}
                    )
                except Exception as e:
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "error", "message": str(e)}
                    )
            
            elif action == "get_state":
                try:
                    engine = await get_workflow_engine(novel_id)
                    progress = engine.get_progress()
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "state", "data": progress}
                    )
                except Exception as e:
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "error", "message": str(e)}
                    )
            
            elif action == "write_chapter":
                try:
                    engine = await get_workflow_engine(novel_id)
                    chapter_num = data.get("chapter_number", 1)
                    result = await engine.write_chapter(chapter_num)
                    
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "chapter_written", "data": {
                            "chapter": chapter_num,
                            "success": result.success
                        }}
                    )
                except Exception as e:
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "error", "message": str(e)}
                    )
            
            elif action == "pause":
                try:
                    engine = await get_workflow_engine(novel_id)
                    await engine.pause()
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "paused"}
                    )
                except Exception as e:
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "error", "message": str(e)}
                    )
            
            elif action == "resume":
                try:
                    engine = await get_workflow_engine(novel_id)
                    await engine.resume()
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "resumed"}
                    )
                except Exception as e:
                    await websocket_manager.send_to_client(
                        websocket,
                        {"type": "error", "message": str(e)}
                    )
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        try:
            await websocket_manager.send_to_client(
                websocket,
                {"type": "error", "message": str(e)}
            )
        except:
            pass
        websocket_manager.disconnect(websocket)
