"""
工作流引擎核心
统一管理小说生成的多Agent协作流程
"""
import json
import asyncio
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from loguru import logger
from sqlalchemy import select

from app.core.redis_client import SessionManager, WorkflowLogsManager
from app.core.agent_logging import log_agent_workflow
from app.core.database import get_session
from app.agents import (
    GenreAnalyzerAgent,
    CharacterDesignerAgent,
    OutlineGeneratorAgent,
    ChapterWriterAgent,
    ConsistencyCheckerAgent,
)
from app.agents.world_builder import WorldBuilderAgent
from app.agents.plot_designer import PlotDesignerAgent
from app.agents.reader import ReaderAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.unified_agent import (
    UnifiedWorldBuilderAgent,
    UnifiedCharacterDesignerAgent,
    UnifiedPlotDesignerAgent,
    UnifiedOutlineGeneratorAgent,
)


class WorkflowPhase(str, Enum):
    """工作流阶段枚举"""
    # 创作规划阶段
    DEMAND_ANALYSIS = "demand_analysis"      # 需求分析
    WORLD_BUILDING = "world_building"         # 世界观构建
    CHARACTER_DESIGN = "character_design"     # 角色设计
    PLOT_DESIGN = "plot_design"               # 冲突/伏笔设计
    # 大纲阶段
    OUTLINE_DRAFT = "outline_draft"            # 剧情大纲
    OUTLINE_DETAIL = "outline_detail"          # 细纲撰写
    # 写作阶段
    CHAPTER_WRITING = "chapter_writing"        # 章节写作
    CHAPTER_REVIEW = "chapter_review"          # 章节审核
    # 修改阶段
    CHAPTER_REVISION = "chapter_revision"      # 章节重写
    FRAMEWORK_ADJUSTMENT = "framework_adjustment"  # 框架调整
    # 状态
    WAITING_CONFIRM = "waiting_confirm"        # 等待用户确认
    PAUSED = "paused"                          # 已暂停
    COMPLETED = "completed"                    # 已完成
    ERROR = "error"                            # 错误状态


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING_RETRY = "waiting_retry"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool
    phase: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    warning: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowTask:
    """工作流任务"""
    task_id: str
    phase: WorkflowPhase
    agent_name: str
    input_data: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[TaskResult] = None
    error_history: List[str] = field(default_factory=list)


@dataclass
class WorkflowState:
    """
    工作流完整状态
    包含所有需要持久化的数据
    """
    # 基础信息
    workflow_id: str
    novel_id: int
    project_path: str  # 小说项目文件夹路径

    # 阶段管理
    current_phase: WorkflowPhase = WorkflowPhase.DEMAND_ANALYSIS
    phase_history: List[str] = field(default_factory=list)  # 已完成阶段列表

    # 创作数据
    demand_analysis: Dict[str, Any] = field(default_factory=dict)  # 需求分析结果
    world_setting: Dict[str, Any] = field(default_factory=dict)     # 世界观设定
    characters: List[Dict[str, Any]] = field(default_factory=list)  # 角色列表
    plot_setting: Dict[str, Any] = field(default_factory=dict)      # 冲突伏笔设定
    outline: Dict[str, Any] = field(default_factory=dict)         # 大纲
    chapter_outlines: List[Dict[str, Any]] = field(default_factory=list)  # 章节细纲数组 [{chapter_number, title, summary, key_points, scenes}]

    # 写作进度
    current_chapter: int = 0
    target_chapters: int = 300
    completed_chapters: List[int] = field(default_factory=list)
    confirmed_chapters: List[int] = field(default_factory=list)

    # 反馈追踪
    pending_revisions: List[Dict[str, Any]] = field(default_factory=list)  # 待处理修改
    revision_history: List[Dict[str, Any]] = field(default_factory=list)  # 修改历史

    # 任务队列
    task_queue: List[WorkflowTask] = field(default_factory=list)
    current_task: Optional[WorkflowTask] = None

    # 状态
    is_waiting: bool = False
    is_paused: bool = False
    is_completed: bool = False

    # 用户交互
    pending_questions: List[Dict[str, Any]] = field(default_factory=list)
    user_confirmations: Dict[str, bool] = field(default_factory=dict)

    # 错误恢复
    last_error: Optional[str] = None
    recovery_checkpoint: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 转换datetime为字符串
        data["current_phase"] = self.current_phase.value
        data["phase_history"] = [p.value if isinstance(p, WorkflowPhase) else p for p in self.phase_history]
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        for task in data.get("task_queue", []):
            if isinstance(task, WorkflowTask):
                task["phase"] = task.phase.value
                task["status"] = task.status.value
        if self.current_task and isinstance(self.current_task, WorkflowTask):
            data["current_task"]["phase"] = self.current_task.phase.value
            data["current_task"]["status"] = self.current_task.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        """从字典创建"""
        if "current_phase" in data and isinstance(data["current_phase"], str):
            data["current_phase"] = WorkflowPhase(data["current_phase"])
        if "phase_history" in data:
            data["phase_history"] = [
                WorkflowPhase(p) if isinstance(p, str) else p
                for p in data["phase_history"]
            ]
        # 转换datetime
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class ErrorRecoveryStrategy:
    """错误恢复策略"""

    @staticmethod
    def get_strategy(error_type: str) -> Dict[str, Any]:
        """根据错误类型获取恢复策略"""
        strategies = {
            "rate_limit": {
                "retry": True,
                "backoff": "exponential",
                "max_retries": 3,
                "base_delay": 5,
            },
            "timeout": {
                "retry": True,
                "backoff": "linear",
                "max_retries": 2,
                "base_delay": 3,
            },
            "invalid_json": {
                "retry": True,
                "fallback": "extract_content",
                "max_retries": 2,
            },
            "consistency_error": {
                "retry": False,
                "flag": "needs_review",
                "escalate": True,
            },
            "llm_error": {
                "retry": True,
                "backoff": "exponential",
                "max_retries": 3,
                "base_delay": 2,
            },
            "unknown": {
                "retry": True,
                "backoff": "exponential",
                "max_retries": 2,
                "base_delay": 1,
            }
        }
        return strategies.get(error_type, strategies["unknown"])

    @staticmethod
    def classify_error(error: Exception) -> str:
        """分类错误类型"""
        error_str = str(error).lower()
        if "rate" in error_str or "429" in error_str or "too many requests" in error_str:
            return "rate_limit"
        elif "timeout" in error_str or "timed out" in error_str:
            return "timeout"
        elif "json" in error_str or "parse" in error_str:
            return "invalid_json"
        elif "consistency" in error_str or "conflict" in error_str:
            return "consistency_error"
        elif "openai" in error_str or "api" in error_str or "connection" in error_str:
            return "llm_error"
        return "unknown"


class WorkflowEngine:
    """
    工作流引擎核心

    职责：
    1. 管理工作流状态
    2. 调度Agent任务
    3. 处理错误恢复
    4. 持久化状态
    5. 与用户交互
    """

    def __init__(self, novel_id: int, project_path: str):
        self.novel_id = novel_id
        self.project_path = project_path
        self.state: Optional[WorkflowState] = None
        self._agents: Dict[str, Callable] = {}  # agent_name -> agent_instance
        self._callbacks: Dict[str, List[Callable]] = {}  # event -> callbacks
        self._error_handler = ErrorRecoveryStrategy()

        # 阶段显示名称映射
        self._phase_display_names = {
            "demand_analysis": "需求分析",
            "world_building": "世界观构建",
            "character_design": "角色设计",
            "plot_design": "冲突伏笔设计",
            "outline_draft": "剧情大纲",
            "outline_detail": "章节细纲",
            "chapter_writing": "章节写作",
            "chapter_review": "章节审核",
            "chapter_revision": "章节修订",
            "framework_adjustment": "框架调整",
            "waiting_confirm": "等待确认",
            "paused": "已暂停",
            "completed": "已完成",
            "error": "错误",
        }

        logger.info(f"初始化工作流引擎: novel_id={novel_id}")

    def register_agent(self, name: str, agent: Any) -> None:
        """注册Agent"""
        self._agents[name] = agent
        logger.debug(f"注册Agent: {name}")

    def on_event(self, event: str, callback: Callable) -> None:
        """注册事件回调"""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    async def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
        """触发事件"""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"事件回调执行失败: {event}, error={e}")

    # ===== 状态管理 =====

    async def load_state(self) -> Optional[WorkflowState]:
        """从持久化加载状态"""
        key = f"workflow_{self.novel_id}"
        data = await SessionManager.get_state(key)
        if data:
            self.state = WorkflowState.from_dict(data)
            logger.info(f"加载工作流状态: phase={self.state.current_phase}")
            return self.state
        return None

    async def save_state(self) -> bool:
        """保存状态到持久化"""
        if not self.state:
            return False

        self.state.updated_at = datetime.now()
        key = f"workflow_{self.novel_id}"
        success = await SessionManager.save_state(key, self.state.to_dict())
        if success:
            logger.debug(f"保存工作流状态: {self.state.current_phase}")
        return success

    async def create_state(self) -> WorkflowState:
        """创建新的工作流状态"""
        self.state = WorkflowState(
            workflow_id=f"wf_{self.novel_id}_{int(datetime.now().timestamp())}",
            novel_id=self.novel_id,
            project_path=self.project_path,
        )
        await self.save_state()
        logger.info(f"创建工作流状态: {self.state.workflow_id}")
        return self.state

    async def create_checkpoint(self) -> None:
        """创建恢复检查点"""
        if self.state:
            self.state.recovery_checkpoint = {
                "phase": self.state.current_phase.value,
                "chapter": self.state.current_chapter,
                "timestamp": datetime.now().isoformat(),
            }
            await self.save_state()
            logger.info("创建恢复检查点")

    async def restore_from_checkpoint(self) -> bool:
        """从检查点恢复"""
        if not self.state or not self.state.recovery_checkpoint:
            return False

        checkpoint = self.state.recovery_checkpoint
        self.state.current_phase = WorkflowPhase(checkpoint["phase"])
        self.state.current_chapter = checkpoint["chapter"]
        await self.save_state()
        logger.info(f"从检查点恢复: {checkpoint}")
        return True

    # ===== 任务调度 =====

    def _create_task(
        self,
        phase: WorkflowPhase,
        agent_name: str,
        input_data: Dict[str, Any]
    ) -> WorkflowTask:
        """创建任务"""
        task_id = f"task_{phase.value}_{int(datetime.now().timestamp() * 1000)}"
        return WorkflowTask(
            task_id=task_id,
            phase=phase,
            agent_name=agent_name,
            input_data=input_data,
        )

    async def _execute_task(self, task: WorkflowTask) -> TaskResult:
        """执行单个任务"""
        agent = self._agents.get(task.agent_name)
        if not agent:
            return TaskResult(
                success=False,
                phase=task.phase.value,
                error=f"Agent不存在: {task.agent_name}"
            )


        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.state.current_task = task

        try:
            phase_name = self._phase_display_names.get(task.phase.value, task.phase.value)
            await WorkflowLogsManager.add_log(
                self.state.workflow_id, "info",
                f"🚀 开始执行: {phase_name}",
                step=task.phase.value
            )
            await WorkflowLogsManager.add_log(
                self.state.workflow_id, "info",
                f"🔧 正在构建融合提示词...",
                step=task.phase.value
            )
            logger.info(f"执行任务: {task.task_id}, agent={task.agent_name}")
            await self._emit_event("task_started", {"task": task.task_id, "phase": task.phase.value})

            # 调用Agent
            if asyncio.iscoroutinefunction(agent.process):
                result = await agent.process(task.input_data)
            else:
                result = agent.process(task.input_data)

            if result.get("success"):
                task.status = TaskStatus.SUCCESS
                task.result = TaskResult(
                    success=True,
                    phase=task.phase.value,
                    data=result,
                )
                task.completed_at = datetime.now()

                await WorkflowLogsManager.add_log(
                    self.state.workflow_id, "success",
                    f"✅ {phase_name} 执行成功",
                    step=task.phase.value
                )
                # 保存提示词构建信息到日志
                if hasattr(result, '_prompt_build_info') or (isinstance(result, dict) and '_prompt_build_info' in result):
                    prompt_info = result.get('_prompt_build_info') if isinstance(result, dict) else getattr(result, '_prompt_build_info', {})
                    if prompt_info:
                        await WorkflowLogsManager.add_log(
                            self.state.workflow_id, "info",
                            f"📝 提示词构建完成: 关键需求={len(prompt_info.get('key_requirements', []))}项, 模板调整={len(prompt_info.get('template_adaptations', []))}项",
                            step=task.phase.value
                        )
                await self._emit_event("task_completed", {
                    "task": task.task_id,
                    "phase": task.phase.value,
                    "data": result
                })

                return task.result
            else:
                raise Exception(result.get("error", "未知错误"))

        except Exception as e:
            return await self._handle_task_error(task, e)

    async def _handle_task_error(self, task: WorkflowTask, error: Exception) -> TaskResult:
        """处理任务错误"""
        error_type = self._error_handler.classify_error(error)
        strategy = self._error_handler.get_strategy(error_type)

        task.error_history.append(str(error))
        task.retry_count += 1

        # 记录错误日志
        await WorkflowLogsManager.add_log(
            self.state.workflow_id, "error",
            f"❌ 执行出错: {str(error)}",
            step=task.phase.value,
            extra={"error_type": error_type, "retry_count": task.retry_count}
        )

        if strategy["retry"] and task.retry_count < strategy.get("max_retries", 3):
            task.status = TaskStatus.WAITING_RETRY
            delay = self._calculate_backoff(
                strategy.get("backoff", "exponential"),
                task.retry_count,
                strategy.get("base_delay", 1)
            )
            logger.warning(f"任务失败，准备重试: {task.task_id}, retry={task.retry_count}, delay={delay}s")
            await asyncio.sleep(delay)
            task.status = TaskStatus.PENDING
            return await self._execute_task(task)
        else:
            task.status = TaskStatus.FAILED
            task.result = TaskResult(
                success=False,
                phase=task.phase.value,
                error=str(error),
            )
            task.completed_at = datetime.now()

            self.state.last_error = str(error)

            await self._emit_event("task_failed", {
                "task": task.task_id,
                "phase": task.phase.value,
                "error": str(error),
                "error_type": error_type,
                "retry_count": task.retry_count,
            })

            return task.result

    @staticmethod
    def _calculate_backoff(strategy: str, retry_count: int, base_delay: float) -> float:
        """计算退避时间"""
        if strategy == "exponential":
            return base_delay * (2 ** (retry_count - 1))
        elif strategy == "linear":
            return base_delay * retry_count
        else:
            return base_delay

    # ===== 阶段流转 =====

    def get_phase_order(self) -> List[WorkflowPhase]:
        """获取正确的阶段顺序"""
        return [
            WorkflowPhase.DEMAND_ANALYSIS,      # 需求分析
            WorkflowPhase.WORLD_BUILDING,         # 世界观构建
            WorkflowPhase.CHARACTER_DESIGN,       # 角色设计
            WorkflowPhase.OUTLINE_DRAFT,          # 剧情大纲
            WorkflowPhase.PLOT_DESIGN,            # 冲突/伏笔设计（在大纲之后）
            WorkflowPhase.OUTLINE_DETAIL,         # 章节细纲
            WorkflowPhase.CHAPTER_WRITING,        # 章节写作
            WorkflowPhase.CHAPTER_REVIEW,         # 章节审核
        ]

    async def transition_to(self, phase: WorkflowPhase, data: Dict[str, Any] = None) -> None:
        """转换到新阶段"""
        if not self.state:
            raise ValueError("工作流状态未初始化")

        old_phase = self.state.current_phase
        self.state.current_phase = phase

        if old_phase not in self.state.phase_history:
            self.state.phase_history.append(old_phase)

        logger.info(f"[WorkflowEngine] transition_to: {old_phase.value} -> {phase.value}")
        logger.info(f"[WorkflowEngine] transition_to: data={data is not None}, data_keys={list(data.keys()) if data else 'None'}")

        if data:
            # 根据阶段保存数据
            await self._save_phase_data(phase, data)

        await self.save_state()
        await self._emit_event("phase_changed", {
            "from": old_phase.value,
            "to": phase.value,
        })
        logger.info(f"[WorkflowEngine] 阶段转换: {old_phase.value} -> {phase.value}")

    async def _save_phase_data(self, phase: WorkflowPhase, data: Dict[str, Any]) -> None:
        """保存阶段数据"""
        if not self.state:
            logger.warning(f"[WorkflowEngine] _save_phase_data: state为空，无法保存")
            return

        if not isinstance(data, dict):
            logger.warning(f"[WorkflowEngine] _save_phase_data: phase={phase.value} received non-dict data: {type(data)}")
            if phase == WorkflowPhase.CHARACTER_DESIGN and isinstance(data, list):
                data = {"characters": data}
            else:
                return

        logger.info(f"[WorkflowEngine] 保存阶段数据: phase={phase.value}, data_keys={list(data.keys())}")

        if phase == WorkflowPhase.DEMAND_ANALYSIS:
            self.state.demand_analysis = data
        elif phase == WorkflowPhase.WORLD_BUILDING:
            self.state.world_setting = data
        elif phase == WorkflowPhase.CHARACTER_DESIGN:
            characters = data.get("characters", [])
            if not characters and isinstance(data.get("data"), dict):
                characters = data["data"].get("characters", [])
            if not characters and isinstance(data.get("result"), dict):
                characters = data["result"].get("characters", [])
            if not isinstance(characters, list):
                logger.warning(f"[WorkflowEngine] CHARACTER_DESIGN: characters field is not a list: {type(characters)}")
                characters = []
            logger.info(f"[WorkflowEngine] CHARACTER_DESIGN: 提取到 {len(characters)} 个角色")
            logger.debug(f"[WorkflowEngine] CHARACTER_DESIGN: characters数据 = {characters}")

            self.state.characters = characters

            # 同步角色到数据库
            if characters and isinstance(characters, list):
                logger.info(f"[WorkflowEngine] CHARACTER_DESIGN: 开始同步 {len(characters)} 个角色到数据库")
                await self._sync_characters_to_db(characters)
            else:
                logger.warning(f"[WorkflowEngine] CHARACTER_DESIGN: characters数据格式异常: {type(characters)}")
        elif phase == WorkflowPhase.PLOT_DESIGN:
            self.state.plot_setting = data
        elif phase == WorkflowPhase.OUTLINE_DRAFT:
            self.state.outline = data
        elif phase == WorkflowPhase.OUTLINE_DETAIL:
            # 统一格式为数组
            outlines_data = data
            if isinstance(data, dict):
                if "chapter_outlines" in data and isinstance(data["chapter_outlines"], list):
                    outlines_data = data["chapter_outlines"]
                elif "outlines" in data and isinstance(data["outlines"], list):
                    outlines_data = data["outlines"]
                else:
                    # 尝试从字典中提取按章节号排序的值
                    outlines_data = [v for k, v in sorted(data.items()) if isinstance(v, dict)]
            
            if isinstance(outlines_data, list):
                self.state.chapter_outlines = outlines_data
                logger.info(f"[WorkflowEngine] OUTLINE_DETAIL: 保存了 {len(outlines_data)} 个章节细纲")
            else:
                logger.warning(f"[WorkflowEngine] OUTLINE_DETAIL: 无法识别的数据格式 {type(outlines_data)}")

    async def _persist_phase_result_to_db(self, phase: WorkflowPhase, data: Dict[str, Any]) -> None:
        """将阶段结果持久化到数据库"""
        try:
            from sqlalchemy.ext.asyncio import AsyncSession
            from app.core.database import get_session_maker
            from app.services.novel_service import NovelService
            from app.schemas.novel import NovelUpdate
            import json

            async with get_session_maker()() as db:
                service = NovelService(db)
                novel = await service.get_novel(self.novel_id)
                if not novel:
                    logger.warning(f"无法保存阶段结果到DB：小说不存在 novel_id={self.novel_id}")
                    return

                update_data = {}

                if phase == WorkflowPhase.DEMAND_ANALYSIS:
                    # 保存类型分析结果到 novels 表
                    update_data["genre_analysis"] = json.dumps(data, ensure_ascii=False)

                elif phase == WorkflowPhase.CHARACTER_DESIGN:
                    # ⚠️ 注意：角色数据的实际保存由 transition_to -> _save_phase_data -> _sync_characters_to_db 处理
                    # 这里只是为了兼容性保留代码结构，但实际不执行保存操作
                    logger.debug(f"[WorkflowEngine] CHARACTER_DESIGN阶段的数据保存由_sync_characters_to_db处理，跳过此处的保存")
                    return

                elif phase == WorkflowPhase.WORLD_BUILDING:
                    # 保存世界观设定到 novels 表
                    update_data["world_setting"] = json.dumps(data, ensure_ascii=False)

                elif phase == WorkflowPhase.PLOT_DESIGN:
                    # 保存冲突伏笔到 novel 的扩展字段或新建表
                    # 这里我们存到 novels 表的 style_prompt 字段（临时复用）
                    update_data["style_prompt"] = json.dumps(data, ensure_ascii=False)

                elif phase == WorkflowPhase.OUTLINE_DRAFT:
                    # 保存大纲到 outlines 表
                    from app.models.outline import Outline
                    outline_title = data.get("outline_title", "剧情大纲")
                    existing_outline = await db.execute(
                        select(Outline).where(
                            Outline.novel_id == self.novel_id,
                            Outline.outline_type == "main"
                        )
                    )
                    outline_record = existing_outline.scalar_one_or_none()
                    if outline_record:
                        outline_record.volume_title = outline_title
                        outline_record.content = json.dumps(data, ensure_ascii=False)
                    else:
                        outline_record = Outline(
                            novel_id=self.novel_id,
                            volume_number=1,
                            volume_title=outline_title,
                            content=json.dumps(data, ensure_ascii=False),
                            outline_type="main",
                        )
                        db.add(outline_record)

                elif phase == WorkflowPhase.OUTLINE_DETAIL:
                    # 保存章节细纲到 outlines 表
                    from app.models.outline import Outline
                    existing_detail = await db.execute(
                        select(Outline).where(
                            Outline.novel_id == self.novel_id,
                            Outline.outline_type == "detail"
                        )
                    )
                    detail_record = existing_detail.scalar_one_or_none()
                    
                    # 从 data 或 state 中获取细纲数组
                    outlines_to_save = self.state.chapter_outlines if self.state.chapter_outlines else []
                    if not outlines_to_save and isinstance(data, dict) and "chapter_outlines" in data:
                        outlines_to_save = data["chapter_outlines"]
                    
                    if detail_record:
                        detail_record.content = json.dumps(outlines_to_save, ensure_ascii=False)
                    else:
                        detail_record = Outline(
                            novel_id=self.novel_id,
                            volume_number=1,
                            volume_title="章节细纲",
                            content=json.dumps(outlines_to_save, ensure_ascii=False),
                            outline_type="detail",
                        )
                        db.add(detail_record)

                if update_data:
                    for key, value in update_data.items():
                        setattr(novel, key, value)

                await db.commit()
                logger.info(f"阶段结果已保存到数据库: novel_id={self.novel_id}, phase={phase.value}")

        except Exception as e:
            logger.error(f"保存阶段结果到数据库失败: {e}", exc_info=True)
            # 不抛出异常，避免影响主流程

    async def wait_for_confirmation(self, question: str, context: Dict[str, Any] = None) -> None:
        """等待用户确认"""
        if not self.state:
            return

        self.state.is_waiting = True
        self.state.pending_questions.append({
            "question": question,
            "context": context or {},
            "timestamp": datetime.now().isoformat(),
        })
        await self.save_state()
        await self._emit_event("waiting_confirmation", {
            "question": question,
            "context": context,
        })

    async def confirm(self, confirmation: str, response: str = "") -> None:
        """处理用户确认"""
        if not self.state or not self.state.pending_questions:
            return

        q = self.state.pending_questions.pop()
        self.state.user_confirmations[q["question"]] = True
        self.state.is_waiting = False

        await self._emit_event("user_confirmed", {
            "question": q["question"],
            "response": response,
        })
        await self.save_state()

    # ===== 工作流执行 =====

    async def _get_previous_phase_data(self, phase: WorkflowPhase) -> Optional[Dict[str, Any]]:
        """获取上一阶段的数据"""
        if not self.state:
            return None

        phase_order = self.get_phase_order()

        try:
            current_idx = phase_order.index(phase)
        except ValueError:
            return None

        # 获取所有已完成阶段的数据
        prev_data = {}

        # 按顺序收集已完成阶段的数据
        for completed_phase in self.state.phase_history:
            if completed_phase == WorkflowPhase.DEMAND_ANALYSIS:
                if self.state.demand_analysis:
                    prev_data["demand_analysis"] = self.state.demand_analysis
            elif completed_phase == WorkflowPhase.WORLD_BUILDING:
                if self.state.world_setting:
                    prev_data["world_setting"] = self.state.world_setting
            elif completed_phase == WorkflowPhase.CHARACTER_DESIGN:
                if self.state.characters:
                    prev_data["characters"] = self.state.characters
            elif completed_phase == WorkflowPhase.OUTLINE_DRAFT:
                if self.state.outline:
                    prev_data["outline"] = self.state.outline
            elif completed_phase == WorkflowPhase.PLOT_DESIGN:
                if self.state.plot_setting:
                    prev_data["plot_setting"] = self.state.plot_setting
            elif completed_phase == WorkflowPhase.OUTLINE_DETAIL:
                if self.state.chapter_outlines:
                    prev_data["chapter_outlines"] = self.state.chapter_outlines

        return prev_data if prev_data else None

    async def run_phase(self, phase: WorkflowPhase, input_data: Dict[str, Any] = None, timeout: Optional[int] = None) -> TaskResult:
        """运行指定阶段

        Args:
            phase: 工作流阶段
            input_data: 输入数据
            timeout: 超时时间（秒），用于LLM调用
        """
        if not self.state:
            await self.create_state()

        # 获取上一阶段的数据并合并到输入中
        prev_data = await self._get_previous_phase_data(phase)
        if prev_data:
            input_data = input_data or {}
            input_data["previous_phase_result"] = prev_data
            # 同时展开上一阶段的关键数据，避免 Agent 手动解包
            for key, value in prev_data.items():
                if key not in input_data:
                    input_data[key] = value

        # 将超时时间添加到输入数据中，供Agent使用
        if timeout:
            input_data = input_data or {}
            input_data["timeout"] = timeout
            logger.info(f"[Workflow] 阶段 {phase.value} 设置超时: {timeout}秒")

        # 根据阶段确定Agent
        phase_agent_map = {
            WorkflowPhase.DEMAND_ANALYSIS: "analyzer",
            WorkflowPhase.WORLD_BUILDING: "world_builder",
            WorkflowPhase.CHARACTER_DESIGN: "character_designer",
            WorkflowPhase.OUTLINE_DRAFT: "outline_generator",
            WorkflowPhase.PLOT_DESIGN: "plot_designer",  # 现在在大纲之后
            WorkflowPhase.OUTLINE_DETAIL: "outline_generator",
            WorkflowPhase.CHAPTER_WRITING: "writer",
            WorkflowPhase.CHAPTER_REVIEW: "reviewer",
        }

        agent_name = phase_agent_map.get(phase)
        if not agent_name:
            return TaskResult(
                success=False,
                phase=phase.value,
                error=f"未知阶段: {phase.value}"
            )

        # outline_detail 阶段需要特殊标记
        if phase == WorkflowPhase.OUTLINE_DETAIL:
            input_data = input_data or {}
            input_data["generate_chapter_outlines"] = True
            # 传入已有的大纲作为参考
            if self.state.outline and "outline" not in input_data:
                input_data["outline"] = self.state.outline

        # 创建并执行任务
        task = self._create_task(phase, agent_name, input_data or {})
        result = await self._execute_task(task)

        if result.success:
            await self.transition_to(phase, result.data)
            # 同时持久化到数据库
            await self._persist_phase_result_to_db(phase, result.data)

        return result

    async def run_full_workflow(self, initial_input: Dict[str, Any]) -> Dict[str, Any]:
        """运行完整工作流（自动模式）"""
        if not self.state:
            await self.create_state()

        results = {}

        # 阶段1：需求分析
        if self.state.current_phase == WorkflowPhase.DEMAND_ANALYSIS:
            result = await self.run_phase(
                WorkflowPhase.DEMAND_ANALYSIS,
                initial_input
            )
            results["demand_analysis"] = result

            if not result.success:
                return results

        # 阶段2：世界观构建
        if self.state.current_phase == WorkflowPhase.WORLD_BUILDING:
            result = await self.run_phase(
                WorkflowPhase.WORLD_BUILDING,
                self.state.demand_analysis
            )
            results["world_building"] = result

        # 阶段3：角色设计
        if self.state.current_phase == WorkflowPhase.CHARACTER_DESIGN:
            result = await self.run_phase(
                WorkflowPhase.CHARACTER_DESIGN,
                {"world_setting": self.state.world_setting, **self.state.demand_analysis}
            )
            results["character_design"] = result

        # 阶段4：冲突伏笔设计
        if self.state.current_phase == WorkflowPhase.PLOT_DESIGN:
            result = await self.run_phase(
                WorkflowPhase.PLOT_DESIGN,
                {
                    "world_setting": self.state.world_setting,
                    "characters": self.state.characters,
                }
            )
            results["plot_design"] = result

        # 阶段5：大纲
        if self.state.current_phase == WorkflowPhase.OUTLINE_DRAFT:
            result = await self.run_phase(
                WorkflowPhase.OUTLINE_DRAFT,
                {
                    "world_setting": self.state.world_setting,
                    "characters": self.state.characters,
                    "plot_setting": self.state.plot_setting,
                }
            )
            results["outline_draft"] = result

        await self._emit_event("workflow_progress", {
            "completed_phases": [p.value for p in self.state.phase_history],
            "current_phase": self.state.current_phase.value,
            "results": {k: v.success for k, v in results.items()},
        })

        return results

    async def _load_characters_from_db(self):
        """从数据库加载角色数据到工作流状态"""
        try:
            async with get_session() as db:
                from app.services.character_service import CharacterService
                char_service = CharacterService(db)
                characters = await char_service.list_characters(self.novel_id)

                # 转换为工作流需要的格式
                self.state.characters = []
                for char in characters:
                    char_dict = {
                        "id": char.id,
                        "name": char.name,
                        "role_type": char.role_type.value if hasattr(char.role_type, 'value') else str(char.role_type),
                        "role": char.role_type.value if hasattr(char.role_type, 'value') else str(char.role_type),
                        "profile": char.profile or {},
                        "current_status": char.current_status,
                        "arc_progress": char.arc_progress,
                        "first_appearance": char.first_appearance,
                    }
                    self.state.characters.append(char_dict)

                logger.info(f"[WorkflowEngine] 从数据库加载了 {len(self.state.characters)} 个角色")
        except Exception as e:
            logger.warning(f"[WorkflowEngine] 加载角色数据失败: {e}")
            # 不抛出异常，继续使用空列表

    async def _sync_characters_to_db(self, characters: List[Dict[str, Any]]):
        """将角色数据同步到数据库"""
        try:
            logger.info(f"[WorkflowEngine] 开始同步角色到数据库，角色数量: {len(characters)}")

            async with get_session() as db:
                from app.services.character_service import CharacterService
                from app.schemas.character import CharacterCreate
                char_service = CharacterService(db)

                created_count = 0
                updated_count = 0

                for idx, char_data in enumerate(characters, 1):
                    char_name = char_data.get("name", f"角色{idx}")
                    logger.info(f"[WorkflowEngine] 处理角色 {idx}/{len(characters)}: {char_name}")
                    logger.debug(f"[WorkflowEngine] 角色原始数据: {char_data}")

                    # 处理 profile 数据，确保是扁平结构
                    profile = char_data.get("profile", {})
                    logger.debug(f"[WorkflowEngine] Profile类型: {type(profile)}, 内容: {list(profile.keys()) if isinstance(profile, dict) else profile}")

                    # 如果 profile 包含嵌套的 basic_info，需要展平
                    if "basic_info" in profile and isinstance(profile["basic_info"], dict):
                        basic_info = profile.pop("basic_info")
                        profile.update(basic_info)
                        logger.debug(f"[WorkflowEngine] 展平 profile.basic_info: {list(basic_info.keys())}")

                    # 确保必要的字段存在（支持英文和中文键名）
                    normalized_profile = {
                        "age": profile.get("age") or profile.get("年龄"),
                        "gender": profile.get("gender") or profile.get("性别"),
                        "appearance": profile.get("appearance") or profile.get("外貌描述") or "",
                        "personality": profile.get("personality") or profile.get("性格") or "",
                        "mbti": profile.get("mbti") or profile.get("mbti类型") or "",
                        "background": profile.get("background") or profile.get("背景") or "",
                        "goals": profile.get("goals") or profile.get("目标") or [],
                        "fears": profile.get("fears") or profile.get("恐惧") or [],
                        "skills": profile.get("skills") or profile.get("技能") or [],
                        "relationships": profile.get("relationships") or profile.get("人际关系") or {},
                    }

                    # 移除 None 值
                    normalized_profile = {k: v for k, v in normalized_profile.items() if v is not None and v != ""}

                    logger.debug(f"[WorkflowEngine] 标准化后的profile: {normalized_profile}")

                    # 检查角色是否已存在
                    existing_char = await char_service.get_character_by_name(
                        self.novel_id,
                        char_name
                    )

                    if existing_char:
                        # 更新现有角色
                        from app.schemas.character import CharacterUpdate
                        update_data = {
                            "role_type": char_data.get("role_type", "supporting"),
                            "profile": normalized_profile,
                        }
                        await char_service.update_character(existing_char.id, CharacterUpdate(**update_data))
                        updated_count += 1
                        logger.info(f"[WorkflowEngine] ✅ 更新角色: {char_name} (ID: {existing_char.id})")
                    else:
                        # 创建新角色
                        char_create = CharacterCreate(
                            novel_id=self.novel_id,
                            name=char_name,
                            role_type=char_data.get("role_type", "supporting"),
                            profile=normalized_profile,
                            first_appearance=1,
                        )
                        new_char = await char_service.create_character(char_create)
                        created_count += 1
                        logger.info(f"[WorkflowEngine] ✅ 创建新角色: {char_name} (ID: {new_char.id})")

                logger.info(f"[WorkflowEngine] ✅ 角色同步完成: 创建{created_count}个, 更新{updated_count}个")
        except Exception as e:
            logger.error(f"[WorkflowEngine] ❌ 同步角色到数据库失败: {e}", exc_info=True)
            # 不抛出异常，不影响主流程

    # ===== 章节写作 =====

    async def write_chapter(
        self,
        chapter_number: int,
        outline: Dict[str, Any] = None,
        auto_mode: bool = False,
        writing_params: Dict[str, Any] = None,
    ) -> TaskResult:
        """撰写指定章节"""
        if not self.state:
            raise ValueError("工作流状态未初始化")

        self.state.current_chapter = chapter_number

        # 辅助函数：从细纲数组中查找指定章节
        def _find_chapter_outline(chapter_outlines: list, ch_num: int) -> dict:
            for co in chapter_outlines:
                if isinstance(co, dict) and co.get("chapter_number") == ch_num:
                    return co
            return {}

        # 如果没有提供大纲，尝试从细纲数组中获取
        if not outline:
            outline = _find_chapter_outline(self.state.chapter_outlines, chapter_number)
        
        # 检查细纲是否存在且有效
        if not outline or not outline.get("summary"):
            logger.warning(f"[write_chapter] 第{chapter_number}章缺少有效的章节细纲，无法撰写")
            return TaskResult(
                success=False,
                phase=WorkflowPhase.CHAPTER_WRITING.value,
                error=f"第{chapter_number}章缺少有效的章节细纲。请先在「工作流」->「章节细纲」阶段完成本章细纲设计。",
            )

        # 确保角色数据已从数据库加载
        if not self.state.characters:
            await self._load_characters_from_db()

        # 构建上下文（包含前文摘要、世界观、角色设定等）
        from app.context_manager import ContextManager
        ctx_manager = ContextManager(self.novel_id, self.state)
        context = await ctx_manager.build_chapter_context(chapter_number, outline)

        # 如果大纲中没有细纲信息，尝试从工作流状态中获取（防御性代码）
        if not outline.get("summary") or not outline.get("key_points"):
            detail_outline = _find_chapter_outline(self.state.chapter_outlines, chapter_number)
            if detail_outline:
                outline.update({
                    "summary": detail_outline.get("summary", outline.get("summary", "")),
                    "key_points": detail_outline.get("key_points", outline.get("key_points", [])),
                    "scenes": detail_outline.get("scenes", []),
                })

        # 构建章节写作参数
        chapter_input = {
            "novel_id": self.novel_id,
            "workflow_id": self.state.workflow_id,
            "phase": WorkflowPhase.CHAPTER_WRITING.value,
            "chapter_number": chapter_number,
            "outline": outline,
            "context": context,
            "characters": self.state.characters,
            "target_words": outline.get("word_count_target", 3000),
        }

        # 合并写作参数
        if writing_params:
            chapter_input.update(writing_params)

        writer_reader_max_rounds = int((writing_params or {}).get("writer_reader_max_rounds", 3))
        reader_score_threshold = float((writing_params or {}).get("reader_score_threshold", 0.78))
        hook_score_threshold = float((writing_params or {}).get("hook_score_threshold", 0.70))

        reader_agent = self._agents.get("reader")
        reviewer_agent = self._agents.get("reviewer")
        result = None
        reader_result = {}
        chapter_content = ""
        loop_history = []

        for loop_round in range(1, writer_reader_max_rounds + 1):
            loop_input = {
                **chapter_input,
                "loop_round": loop_round,
                "rewrite_round": loop_round,
            }
            if chapter_content:
                loop_input["previous_draft"] = chapter_content
            if reader_result.get("reader_feedback"):
                loop_input["reader_feedback"] = reader_result["reader_feedback"]

            log_agent_workflow(
                "writer",
                "writer_reader_loop_start",
                context=loop_input,
                details={"loop_round": loop_round},
            )
            result = await self.run_phase(WorkflowPhase.CHAPTER_WRITING, loop_input)
            if not result.success:
                return result

            chapter_content = result.data.get("content", "")
            if reader_agent and chapter_content:
                reader_input = {
                    "workflow_id": self.state.workflow_id,
                    "novel_id": self.novel_id,
                    "phase": WorkflowPhase.CHAPTER_WRITING.value,
                    "loop_round": loop_round,
                    "chapter_number": chapter_number,
                    "chapter_content": chapter_content,
                    "outline": outline,
                    "characters": self.state.characters,
                    "world_setting": self.state.world_setting,
                    "plot_setting": self.state.plot_setting,
                }
                reader_result = await reader_agent.process(reader_input)
            else:
                reader_result = {}

            feedback = reader_result.get("reader_feedback", {})
            reader_score = float(feedback.get("reader_score", 0) or 0)
            hook_score = float(feedback.get("hook_score", 0) or 0)
            continue_reading = bool(feedback.get("would_continue_reading", False))
            passed = (
                reader_result.get("success", False)
                and reader_score >= reader_score_threshold
                and hook_score >= hook_score_threshold
                and continue_reading
            )
            loop_history.append({
                "loop_round": loop_round,
                "reader_score": reader_score,
                "hook_score": hook_score,
                "would_continue_reading": continue_reading,
                "passed": passed,
            })
            log_agent_workflow(
                "reader",
                "writer_reader_loop_feedback",
                context={
                    "workflow_id": self.state.workflow_id,
                    "novel_id": self.novel_id,
                    "chapter_number": chapter_number,
                    "phase": WorkflowPhase.CHAPTER_WRITING.value,
                    "loop_round": loop_round,
                },
                details=loop_history[-1],
            )
            result.data["reader_feedback"] = feedback
            result.data["reader_agent_success"] = reader_result.get("success", False)
            result.data["writer_reader_loop_history"] = loop_history

            if passed:
                break

        if result and result.success:
            if reviewer_agent and chapter_content:
                review_result = await reviewer_agent.process({
                    "workflow_id": self.state.workflow_id,
                    "novel_id": self.novel_id,
                    "phase": WorkflowPhase.CHAPTER_REVIEW.value,
                    "chapter_number": chapter_number,
                    "operation": "review",
                    "chapter_content": chapter_content,
                    "characters": self.state.characters,
                    "world_setting": self.state.world_setting,
                    "plot_setting": self.state.plot_setting,
                    "reader_feedback": reader_result.get("reader_feedback", {}),
                })
                result.data["editor_review"] = review_result

            self.state.revision_history.append({
                "chapter_number": chapter_number,
                "writer_reader_loop_history": loop_history,
                "final_reader_feedback": reader_result.get("reader_feedback", {}),
                "timestamp": datetime.now().isoformat(),
            })
            self.state.completed_chapters.append(chapter_number)
            await self.save_state()

        return result

    async def revise_chapter(
        self,
        chapter_number: int,
        feedback: str,
        scope: str = "chapter"  # "chapter" | "framework"
    ) -> TaskResult:
        """根据反馈修订"""
        if scope == "chapter":
            return await self.run_phase(
                WorkflowPhase.CHAPTER_REVISION,
                {
                    "chapter_number": chapter_number,
                    "feedback": feedback,
                    "characters": self.state.characters,
                    "plot_setting": self.state.plot_setting,
                }
            )
        else:
            return await self.run_phase(
                WorkflowPhase.FRAMEWORK_ADJUSTMENT,
                {
                    "chapter_number": chapter_number,
                    "feedback": feedback,
                    "current_outline": self.state.outline,
                    "characters": self.state.characters,
                    "plot_setting": self.state.plot_setting,
                }
            )

    # ===== 暂停/恢复 =====

    async def pause(self) -> bool:
        """暂停工作流"""
        if not self.state:
            return False

        await self.create_checkpoint()
        self.state.is_paused = True
        self.state.previous_phase = self.state.current_phase
        await self.save_state()
        await self._emit_event("workflow_paused", {"phase": self.state.current_phase.value})
        return True

    async def resume(self) -> bool:
        """恢复工作流"""
        if not self.state or not self.state.is_paused:
            return False

        if self.state.recovery_checkpoint:
            await self.restore_from_checkpoint()

        self.state.is_paused = False
        await self.save_state()
        await self._emit_event("workflow_resumed", {"phase": self.state.current_phase.value})
        return True

    # ===== 状态查询 =====

    def get_progress(self) -> Dict[str, Any]:
        """获取工作流进度"""
        if not self.state:
            return {"status": "not_started"}

        phases = self.get_phase_order()
        # 只有当阶段有实际数据时才标记为已完成
        truly_completed = []
        
        if self.state.demand_analysis:
            truly_completed.append(WorkflowPhase.DEMAND_ANALYSIS.value)
        if self.state.world_setting:
            truly_completed.append(WorkflowPhase.WORLD_BUILDING.value)
        if self.state.characters:
            truly_completed.append(WorkflowPhase.CHARACTER_DESIGN.value)
        if self.state.plot_setting:
            truly_completed.append(WorkflowPhase.PLOT_DESIGN.value)
        if self.state.outline:
            truly_completed.append(WorkflowPhase.OUTLINE_DRAFT.value)
        if self.state.chapter_outlines:
            truly_completed.append(WorkflowPhase.OUTLINE_DETAIL.value)
        
        total = len([p for p in phases if p not in [WorkflowPhase.WAITING_CONFIRM, WorkflowPhase.PAUSED, WorkflowPhase.COMPLETED, WorkflowPhase.ERROR]])
        completed = len(truly_completed)

        return {
            "workflow_id": self.state.workflow_id,
            "current_phase": self.state.current_phase.value,
            "phase_display": self._get_phase_display_name(self.state.current_phase),
            "progress_percent": int((completed / max(total, 1)) * 100),
            "completed_phases": truly_completed,
            "current_chapter": self.state.current_chapter,
            "target_chapters": self.state.target_chapters,
            "completed_chapters": len(self.state.completed_chapters),
            "is_waiting": self.state.is_waiting,
            "is_paused": self.state.is_paused,
            "last_error": self.state.last_error,
        }

    @staticmethod
    def _get_phase_display_name(phase: WorkflowPhase) -> str:
        """获取阶段显示名称"""
        names = {
            WorkflowPhase.DEMAND_ANALYSIS: "需求分析",
            WorkflowPhase.WORLD_BUILDING: "世界观构建",
            WorkflowPhase.CHARACTER_DESIGN: "角色设计",
            WorkflowPhase.PLOT_DESIGN: "冲突与伏笔",
            WorkflowPhase.OUTLINE_DRAFT: "剧情大纲",
            WorkflowPhase.OUTLINE_DETAIL: "章节细纲",
            WorkflowPhase.CHAPTER_WRITING: "章节写作",
            WorkflowPhase.CHAPTER_REVIEW: "章节审核",
            WorkflowPhase.CHAPTER_REVISION: "章节修改",
            WorkflowPhase.FRAMEWORK_ADJUSTMENT: "框架调整",
            WorkflowPhase.WAITING_CONFIRM: "等待确认",
            WorkflowPhase.PAUSED: "已暂停",
            WorkflowPhase.COMPLETED: "已完成",
            WorkflowPhase.ERROR: "错误",
        }
        return names.get(phase, phase.value)


# ===== 工厂函数 =====

_workflow_instances: Dict[int, WorkflowEngine] = {}


async def get_workflow_engine(novel_id: int, project_path: str = "") -> WorkflowEngine:
    """获取工作流引擎实例"""
    if novel_id not in _workflow_instances:
        engine = WorkflowEngine(novel_id, project_path)

        # 注册所有Agent（使用新的统一Agent）
        engine.register_agent("analyzer", GenreAnalyzerAgent())
        engine.register_agent("world_builder", UnifiedWorldBuilderAgent())
        engine.register_agent("character_designer", UnifiedCharacterDesignerAgent())
        engine.register_agent("plot_designer", UnifiedPlotDesignerAgent())
        engine.register_agent("outline_generator", UnifiedOutlineGeneratorAgent())
        engine.register_agent("writer", ChapterWriterAgent())
        engine.register_agent("reader", ReaderAgent())
        engine.register_agent("reviewer", ReviewerAgent())
        engine.register_agent("consistency_checker", ConsistencyCheckerAgent())

        await engine.load_state()
        if not engine.state:
            await engine.create_state()
        _workflow_instances[novel_id] = engine
        logger.info(f"工作流引擎初始化完成，已注册 {len(engine._agents)} 个Agent")
    return _workflow_instances[novel_id]


async def close_workflow_engine(novel_id: int) -> None:
    """关闭工作流引擎"""
    if novel_id in _workflow_instances:
        engine = _workflow_instances[novel_id]
        await engine.save_state()
        del _workflow_instances[novel_id]
