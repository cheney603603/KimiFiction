"""
小说写作工作流状态定义
基于 LangGraph 的状态图定义
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from enum import Enum
import operator


class WritingPhase(str, Enum):
    """写作阶段枚举"""
    PLANNING = "planning"
    WORLD_BUILDING = "world_building"
    CHARACTER_DESIGN = "character_design"
    PLOT_DESIGN = "plot_design"
    OUTLINE = "outline"
    WRITING = "writing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"


class NovelState(TypedDict):
    """
    小说写作工作流状态
    
    贯穿整个多Agent协作流程的核心状态对象
    """
    novel_id: int                              # 小说ID
    workflow_id: str                            # 工作流ID
    current_phase: WritingPhase                # 当前阶段
    messages: Annotated[List[Dict], operator.add]  # 对话消息记录
    user_input: str                            # 用户输入
    waiting_for_user: bool                      # 是否等待用户确认
    user_confirmed: bool                        # 用户是否已确认
    genre_analysis: Optional[Dict]              # 类型分析结果
    confirmed_genre: Optional[str]              # 已确认的类型
    world_setting: Dict[str, Any]               # 世界观设定
    characters: List[Dict]                      # 角色列表
    plot_setting: Dict[str, Any]                # 情节设定
    outline: Dict[str, Any]                     # 大纲
    current_chapter: int                        # 当前章节序号
    chapters: List[Dict]                        # 章节列表
    rag_context: List[Dict]                     # RAG检索上下文
    checkpoint_data: Optional[Dict]             # 断点数据
    errors: List[str]                           # 错误列表
    status: str                                 # 状态字符串


# 默认初始状态工厂
def create_initial_state(novel_id: int, workflow_id: str, user_input: str = "") -> NovelState:
    """
    创建初始状态
    
    Args:
        novel_id: 小说ID
        workflow_id: 工作流ID
        user_input: 用户初始输入
        
    Returns:
        初始状态字典
    """
    return {
        "novel_id": novel_id,
        "workflow_id": workflow_id,
        "current_phase": WritingPhase.PLANNING,
        "messages": [],
        "user_input": user_input,
        "waiting_for_user": False,
        "user_confirmed": False,
        "genre_analysis": None,
        "confirmed_genre": None,
        "world_setting": {},
        "characters": [],
        "plot_setting": {},
        "outline": {},
        "current_chapter": 1,
        "chapters": [],
        "rag_context": [],
        "checkpoint_data": None,
        "errors": [],
        "status": "init"
    }