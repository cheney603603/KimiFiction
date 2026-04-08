"""
工作流相关Pydantic模型
支持新版多Agent协作工作流
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ===== 新版工作流模型 =====

class WorkflowPhaseRequest(BaseModel):
    """执行工作流阶段请求"""
    phase: str
    input_data: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = Field(None, ge=30, le=3600, description="阶段超时时间（秒），不填则使用默认值")


class WorkflowProgressResponse(BaseModel):
    """工作流进度响应"""
    workflow_id: str
    current_phase: str
    phase_display: str
    progress_percent: int
    completed_phases: List[str]
    current_chapter: int
    target_chapters: int
    completed_chapters: int
    is_waiting: bool
    is_paused: bool
    last_error: Optional[str] = None


class TaskResultResponse(BaseModel):
    """任务执行结果"""
    success: bool
    phase: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    warning: Optional[str] = None


class ChapterWriteRequest(BaseModel):
    """章节写作请求"""
    chapter_number: int
    outline: Optional[Dict[str, Any]] = None
    auto_mode: bool = False
    timeout: Optional[int] = Field(None, ge=30, le=3600, description="超时时间（秒），不填则使用默认值")
    # 章节写作参数
    writing_style: Optional[str] = Field(None, description="文风，如'古风典雅'、'现代简洁'、'网络轻松'等")
    env_description_level: Optional[str] = Field("normal", description="环境描写级别: minimal/normal/rich")
    dialogue_ratio: Optional[float] = Field(0.3, ge=0.0, le=1.0, description="对话占比 0-1")
    notes: Optional[str] = Field(None, description="写作注意事项/特殊要求")


class ChapterRevisionRequest(BaseModel):
    """章节修订请求"""
    chapter_number: int
    feedback: str = Field(..., min_length=1)
    scope: str = Field(default="chapter", pattern="^(chapter|framework)$")


class WorkflowSnapshotResponse(BaseModel):
    """工作流快照"""
    snapshot_id: str
    workflow_id: str
    reason: str
    created_at: str


class ConfirmRequest(BaseModel):
    """用户确认请求"""
    confirmation: str = Field(..., min_length=1)
    response: str = ""


# ===== 旧版兼容模型 =====

class WorkflowState(str):
    """工作流状态（兼容旧版）"""
    AWAITING_GENRE = "awaiting_genre"
    DISCUSSING_PLOT = "discussing_plot"
    DESIGNING_CHARS = "designing_chars"
    GENERATING_OUTLINE = "generating_outline"
    WRITING_CHAPTER = "writing_chapter"
    REVIEWING = "reviewing"
    CONTINUING = "continuing"
    PAUSED = "paused"
    COMPLETED = "completed"


class WorkflowStartRequest(BaseModel):
    """启动工作流请求"""
    title: str = Field(..., min_length=1, max_length=255)
    initial_idea: Optional[str] = None
    preferred_genre: Optional[str] = None


class GenreAnalysisRequest(BaseModel):
    """类型分析请求"""
    user_input: str = Field(..., min_length=1)


class GenreAnalysisResponse(BaseModel):
    """类型分析响应"""
    suggested_genre: str
    sub_genres: List[str]
    style_keywords: List[str]
    tropes: List[str]
    target_audience: str
    similar_works: List[str]
    reasoning: str


class UserInputRequest(BaseModel):
    """用户输入请求"""
    message: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = None


class AgentMessage(BaseModel):
    """智能体消息"""
    role: str
    content: str
    message_type: str = "text"
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class WorkflowResponse(BaseModel):
    """工作流响应"""
    novel_id: int
    current_state: str
    messages: List[AgentMessage]
    waiting_for_user: bool
    progress: Dict[str, Any]
    can_proceed: bool
    suggestions: Optional[List[str]] = None


class WritingProgress(BaseModel):
    """写作进度"""
    novel_id: int
    current_chapter: int
    total_chapters: int
    is_auto_mode: bool
    last_generated_at: Optional[datetime]
    next_chapter_eta: Optional[str]


# ===== WebSocket消息 =====

class WSMessageType(str):
    """WebSocket消息类型"""
    STATE_UPDATE = "state_update"
    PHASE_CHANGED = "phase_changed"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    CHAPTER_GENERATED = "chapter_generated"
    WAITING_CONFIRMATION = "waiting_confirmation"
    USER_CONFIRMED = "user_confirmed"
    ERROR = "error"


class WSMessage(BaseModel):
    """WebSocket消息"""
    type: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
