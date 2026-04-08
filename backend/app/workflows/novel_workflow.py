"""
小说生成工作流
使用LangGraph编排多智能体协作
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from enum import Enum
import operator
from loguru import logger

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not available, workflow will use simplified mode")


class WorkflowState(str, Enum):
    """工作流状态枚举"""
    AWAITING_GENRE = "awaiting_genre"
    DISCUSSING_PLOT = "discussing_plot"
    DESIGNING_CHARS = "designing_chars"
    GENERATING_OUTLINE = "generating_outline"
    WRITING_CHAPTER = "writing_chapter"
    REVIEWING = "reviewing"
    CONTINUING = "continuing"
    PAUSED = "paused"
    COMPLETED = "completed"


class NovelState(TypedDict):
    """
    小说工作流状态定义
    
    这是LangGraph的状态类型，包含工作流中的所有共享数据
    """
    # 基础信息
    novel_id: int
    current_state: str
    
    # 用户交互
    user_input: str
    messages: Annotated[List[Dict], operator.add]  # 消息历史
    waiting_for_user: bool
    
    # 类型分析
    genre_analysis: Optional[Dict]
    confirmed_genre: Optional[str]
    
    # 剧情讨论
    plot_summary: str
    discussion_stage: str
    
    # 角色设计
    characters: List[Dict]
    
    # 大纲
    outline: Optional[Dict]
    volumes: List[Dict]
    
    # 写作状态
    current_chapter: int
    target_chapters: int
    auto_mode: bool
    
    # 上下文窗口
    context_window: Dict
    
    # 错误和重试
    error: Optional[str]
    retry_count: int


class NovelWorkflow:
    """
    小说生成工作流
    
    管理从需求分析到章节生成的完整流程
    """
    
    def __init__(self):
        self.workflow = None
        if LANGGRAPH_AVAILABLE:
            self._build_graph()
    
    def _build_graph(self):
        """构建LangGraph状态机"""
        if not LANGGRAPH_AVAILABLE:
            return
        
        # 创建工作流图
        workflow = StateGraph(NovelState)
        
        # 添加节点
        workflow.add_node("analyze_genre", self._node_analyze_genre)
        workflow.add_node("discuss_plot", self._node_discuss_plot)
        workflow.add_node("design_characters", self._node_design_characters)
        workflow.add_node("generate_outline", self._node_generate_outline)
        workflow.add_node("prepare_writing", self._node_prepare_writing)
        workflow.add_node("write_chapter", self._node_write_chapter)
        workflow.add_node("check_consistency", self._node_check_consistency)
        workflow.add_node("update_memory", self._node_update_memory)
        workflow.add_node("wait_for_user", self._node_wait_for_user)
        
        # 设置入口点
        workflow.set_entry_point("analyze_genre")
        
        # 添加条件边
        workflow.add_conditional_edges(
            "analyze_genre",
            self._should_wait_for_genre_confirmation,
            {
                "wait": "wait_for_user",
                "continue": "discuss_plot"
            }
        )
        
        workflow.add_conditional_edges(
            "discuss_plot",
            self._should_proceed_to_characters,
            {
                "continue": "design_characters",
                "wait": "wait_for_user"
            }
        )
        
        workflow.add_conditional_edges(
            "design_characters",
            self._should_proceed_to_outline,
            {
                "continue": "generate_outline",
                "wait": "wait_for_user"
            }
        )
        
        workflow.add_conditional_edges(
            "generate_outline",
            self._should_start_writing,
            {
                "continue": "prepare_writing",
                "wait": "wait_for_user"
            }
        )
        
        workflow.add_conditional_edges(
            "prepare_writing",
            lambda s: "write" if s.get("auto_mode") else "wait",
            {
                "write": "write_chapter",
                "wait": "wait_for_user"
            }
        )
        
        # 写作循环
        workflow.add_edge("write_chapter", "check_consistency")
        workflow.add_edge("check_consistency", "update_memory")
        
        workflow.add_conditional_edges(
            "update_memory",
            self._should_continue_writing,
            {
                "continue": "write_chapter",
                "pause": "wait_for_user",
                "complete": END
            }
        )
        
        # 用户输入后的路由
        workflow.add_conditional_edges(
            "wait_for_user",
            self._route_after_user_input,
            {
                "analyze_genre": "analyze_genre",
                "discuss_plot": "discuss_plot",
                "design_characters": "design_characters",
                "generate_outline": "generate_outline",
                "write_chapter": "write_chapter",
            }
        )
        
        # 编译工作流
        self.workflow = workflow.compile(checkpointer=MemorySaver())
        logger.info("工作流图构建完成")
    
    # ===== 节点实现 =====
    
    async def _node_analyze_genre(self, state: NovelState) -> NovelState:
        """分析小说类型节点"""
        from app.agents.analyzer import GenreAnalyzerAgent
        
        agent = GenreAnalyzerAgent()
        result = await agent.process({
            "user_input": state.get("user_input", "")
        })
        
        if result.get("success"):
            state["genre_analysis"] = result.get("analysis")
            state["messages"].append({
                "role": "agent",
                "content": f"类型分析完成：建议类型为{result['analysis'].get('suggested_genre', '未知')}",
                "type": "suggestion"
            })
        else:
            state["error"] = result.get("error")
        
        return state
    
    async def _node_discuss_plot(self, state: NovelState) -> NovelState:
        """剧情讨论节点"""
        from app.agents.discussor import PlotDiscussorAgent
        
        agent = PlotDiscussorAgent()
        result = await agent.process({
            "user_input": state.get("user_input", ""),
            "genre": state.get("confirmed_genre") or state.get("genre_analysis", {}).get("suggested_genre"),
            "stage": state.get("discussion_stage", "initial"),
            "history": state.get("messages", [])
        })
        
        if result.get("success"):
            state["messages"].append({
                "role": "agent",
                "content": result.get("response", ""),
                "type": "discussion"
            })
            state["discussion_stage"] = result.get("next_stage", state.get("discussion_stage"))
            
            if result.get("can_proceed"):
                # 提取剧情摘要
                state["plot_summary"] = self._extract_plot_summary(state["messages"])
        
        return state
    
    async def _node_design_characters(self, state: NovelState) -> NovelState:
        """角色设计节点"""
        from app.agents.character_designer import CharacterDesignerAgent
        
        agent = CharacterDesignerAgent()
        result = await agent.process({
            "genre": state.get("confirmed_genre") or state.get("genre_analysis", {}).get("suggested_genre"),
            "plot_summary": state.get("plot_summary", ""),
            "num_characters": 5
        })
        
        if result.get("success"):
            state["characters"] = result.get("characters", [])
            state["messages"].append({
                "role": "agent",
                "content": f"角色设计完成！已创建{len(state['characters'])}个角色。",
                "type": "suggestion"
            })
        
        return state
    
    async def _node_generate_outline(self, state: NovelState) -> NovelState:
        """大纲生成节点"""
        from app.agents.outline_generator import OutlineGeneratorAgent
        
        agent = OutlineGeneratorAgent()
        result = await agent.process({
            "genre": state.get("confirmed_genre") or state.get("genre_analysis", {}).get("suggested_genre"),
            "characters": state.get("characters", []),
            "plot_summary": state.get("plot_summary", ""),
            "total_volumes": 3,
            "chapters_per_volume": 100
        })
        
        if result.get("success"):
            state["volumes"] = result.get("volumes", [])
            state["outline"] = result
            state["messages"].append({
                "role": "agent",
                "content": f"大纲生成完成！共{len(state['volumes'])}卷，预计{result.get('estimated_chapters', 0)}章。",
                "type": "suggestion"
            })
        
        return state
    
    async def _node_prepare_writing(self, state: NovelState) -> NovelState:
        """准备写作节点"""
        state["current_chapter"] = 1
        state["messages"].append({
            "role": "system",
            "content": "准备开始撰写章节...",
            "type": "system"
        })
        return state
    
    async def _node_write_chapter(self, state: NovelState) -> NovelState:
        """撰写章节节点"""
        from app.agents.writer import ChapterWriterAgent
        from app.services.memory_service import MemoryService
        
        agent = ChapterWriterAgent()
        
        # 获取当前章节的大纲
        chapter_outline = self._get_chapter_outline(state)
        
        # 构建上下文
        context = {
            "novel_id": state["novel_id"],
            "chapter_number": state["current_chapter"],
            "outline": chapter_outline,
            "characters": state.get("characters", []),
            "context_window": state.get("context_window", {}),
            "target_words": 3000
        }
        
        result = await agent.process(context)
        
        if result.get("success"):
            chapter = result.get("chapter", {})
            state["messages"].append({
                "role": "agent",
                "content": f"第{state['current_chapter']}章《{chapter.get('title')}》撰写完成！({chapter.get('word_count', 0)}字)",
                "type": "suggestion"
            })
            # 保存章节内容到临时位置
            state["last_chapter"] = chapter
        
        return state
    
    async def _node_check_consistency(self, state: NovelState) -> NovelState:
        """一致性检查节点"""
        from app.agents.consistency_checker import ConsistencyCheckerAgent
        
        agent = ConsistencyCheckerAgent()
        chapter = state.get("last_chapter", {})
        
        result = await agent.process({
            "chapter_content": chapter.get("content", ""),
            "characters": state.get("characters", []),
            "previous_chapters": [],  # 可以从数据库获取
            "world_settings": {}
        })
        
        if not result.get("is_consistent", True):
            issues = result.get("issues", [])
            state["messages"].append({
                "role": "system",
                "content": f"发现{len(issues)}个一致性问题，请检查。",
                "type": "warning"
            })
        
        return state
    
    async def _node_update_memory(self, state: NovelState) -> NovelState:
        """更新记忆节点"""
        from app.agents.memory_manager import MemoryManagerAgent
        
        agent = MemoryManagerAgent()
        chapter = state.get("last_chapter", {})
        
        result = await agent.process({
            "chapter_content": chapter.get("content", ""),
            "chapter_number": state["current_chapter"],
            "characters": state.get("characters", [])
        })
        
        if result.get("success"):
            # 更新章节号
            state["current_chapter"] += 1
        
        return state
    
    async def _node_wait_for_user(self, state: NovelState) -> NovelState:
        """等待用户输入节点"""
        state["waiting_for_user"] = True
        return state
    
    # ===== 条件路由函数 =====
    
    def _should_wait_for_genre_confirmation(self, state: NovelState) -> str:
        """是否应该等待类型确认"""
        if state.get("confirmed_genre"):
            return "continue"
        return "wait"
    
    def _should_proceed_to_characters(self, state: NovelState) -> str:
        """是否应该进入角色设计"""
        if state.get("discussion_stage") == "complete":
            return "continue"
        return "wait"
    
    def _should_proceed_to_outline(self, state: NovelState) -> str:
        """是否应该进入大纲生成"""
        if len(state.get("characters", [])) > 0:
            return "continue"
        return "wait"
    
    def _should_start_writing(self, state: NovelState) -> str:
        """是否应该开始写作"""
        if state.get("outline"):
            return "continue"
        return "wait"
    
    def _should_continue_writing(self, state: NovelState) -> str:
        """是否应该继续写作"""
        if state.get("current_chapter", 0) >= state.get("target_chapters", 100):
            return "complete"
        if state.get("auto_mode"):
            return "continue"
        return "pause"
    
    def _route_after_user_input(self, state: NovelState) -> str:
        """用户输入后的路由"""
        return state.get("current_state", "analyze_genre")
    
    # ===== 辅助方法 =====
    
    def _extract_plot_summary(self, messages: List[Dict]) -> str:
        """从消息中提取剧情摘要"""
        # 简化实现：合并所有agent的消息
        agent_messages = [m.get("content", "") for m in messages if m.get("role") == "agent"]
        return " ".join(agent_messages[-3:])  # 取最近3条
    
    def _get_chapter_outline(self, state: NovelState) -> Dict:
        """获取当前章节的大纲"""
        current = state.get("current_chapter", 1)
        volumes = state.get("volumes", [])
        
        # 找到对应的卷和剧情弧
        for volume in volumes:
            for arc in volume.get("arcs", []):
                if arc.get("start_chapter", 0) <= current <= arc.get("end_chapter", 0):
                    return {
                        "title": f"第{current}章",
                        "summary": arc.get("description", ""),
                        "key_events": arc.get("key_events", [])[:2],
                        "scene_setting": "",
                        "emotional_arc": ""
                    }
        
        return {"title": f"第{current}章", "summary": "", "key_events": []}
    
    # ===== 公共方法 =====
    
    async def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """运行工作流"""
        if not self.workflow:
            logger.warning("工作流未初始化，使用简化模式")
            return initial_state
        
        try:
            result = await self.workflow.ainvoke(initial_state)
            return result
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            return {**initial_state, "error": str(e)}


def create_novel_workflow() -> NovelWorkflow:
    """工厂函数：创建小说工作流实例"""
    return NovelWorkflow()
