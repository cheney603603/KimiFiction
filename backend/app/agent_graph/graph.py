"""
LangGraph ReAct 工作流图

构建基于ReAct架构的有向状态图，实现多Agent协作。
支持状态持久化和断点续写。
"""
from typing import Any, Dict, List, Optional, TypedDict, Annotated
import operator
from loguru import logger

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.base import BaseCheckpointSaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not available, using mock implementation")

from app.agent_graph.state import NovelState, WritingPhase, create_initial_state


class ReActNode:
    """ReAct节点基类"""
    
    def __init__(self, name: str):
        self.name = name
    
    async def execute(self, state: NovelState) -> Dict[str, Any]:
        """执行节点逻辑"""
        raise NotImplementedError


class PlanningNode(ReActNode):
    """规划节点 - 需求分析和类型识别"""
    
    def __init__(self):
        super().__init__("planning")
    
    async def execute(self, state: NovelState) -> Dict[str, Any]:
        """执行规划"""
        logger.info(f"[ReAct] {self.name}: 执行规划")
        
        # 这里应该调用GenreAnalyzerAgent
        # 简化实现
        return {
            "current_phase": WritingPhase.WORLD_BUILDING,
            "messages": [{"role": "assistant", "content": "完成需求分析"}],
        }


class WorldBuildingNode(ReActNode):
    """世界观构建节点"""
    
    def __init__(self):
        super().__init__("world_building")
    
    async def execute(self, state: NovelState) -> Dict[str, Any]:
        """构建世界观"""
        logger.info(f"[ReAct] {self.name}: 构建世界观")
        
        return {
            "current_phase": WritingPhase.CHARACTER_DESIGN,
            "world_setting": {"era": "modern", "location": "fictional_city"},
            "messages": [{"role": "assistant", "content": "完成世界观构建"}],
        }


class CharacterDesignNode(ReActNode):
    """角色设计节点"""
    
    def __init__(self):
        super().__init__("character_design")
    
    async def execute(self, state: NovelState) -> Dict[str, Any]:
        """设计角色"""
        logger.info(f"[ReAct] {self.name}: 设计角色")
        
        return {
            "current_phase": WritingPhase.PLOT_DESIGN,
            "characters": [
                {"name": "主角", "role": "protagonist"},
                {"name": "反派", "role": "antagonist"}
            ],
            "messages": [{"role": "assistant", "content": "完成角色设计"}],
        }


class PlotDesignNode(ReActNode):
    """情节设计节点"""
    
    def __init__(self):
        super().__init__("plot_design")
    
    async def execute(self, state: NovelState) -> Dict[str, Any]:
        """设计情节"""
        logger.info(f"[ReAct] {self.name}: 设计情节")
        
        return {
            "current_phase": WritingPhase.OUTLINE,
            "plot_setting": {"conflict": "main_conflict", "climax": "story_climax"},
            "messages": [{"role": "assistant", "content": "完成情节设计"}],
        }


class OutlineNode(ReActNode):
    """大纲生成节点"""
    
    def __init__(self):
        super().__init__("outline")
    
    async def execute(self, state: NovelState) -> Dict[str, Any]:
        """生成大纲"""
        logger.info(f"[ReAct] {self.name}: 生成大纲")
        
        return {
            "current_phase": WritingPhase.WRITING,
            "outline": {
                "title": "小说大纲",
                "volumes": [
                    {"volume_number": 1, "title": "第一卷", "chapters": 100}
                ]
            },
            "messages": [{"role": "assistant", "content": "完成大纲生成"}],
        }


class WritingNode(ReActNode):
    """写作节点 - 使用Writer-Reader RL"""
    
    def __init__(self):
        super().__init__("writing")
    
    async def execute(self, state: NovelState) -> Dict[str, Any]:
        """执行写作"""
        logger.info(f"[ReAct] {self.name}: 写作第{state['current_chapter']}章")
        
        # 这里应该调用WriterReaderLoop
        # 简化实现
        current_chapter = state["current_chapter"]
        
        return {
            "current_chapter": current_chapter + 1,
            "chapters": state.get("chapters", []) + [{
                "chapter_number": current_chapter,
                "title": f"第{current_chapter}章",
                "content": "章节内容..."
            }],
            "messages": [{"role": "assistant", "content": f"完成第{current_chapter}章写作"}],
        }


class ReviewNode(ReActNode):
    """审核节点"""
    
    def __init__(self):
        super().__init__("review")
    
    async def execute(self, state: NovelState) -> Dict[str, Any]:
        """审核内容"""
        logger.info(f"[ReAct] {self.name}: 审核内容")
        
        # 检查是否完成所有章节
        if state["current_chapter"] > 10:  # 简化：假设写10章就完成
            return {
                "current_phase": WritingPhase.COMPLETED,
                "messages": [{"role": "assistant", "content": "小说写作完成！"}],
            }
        
        return {
            "current_phase": WritingPhase.WRITING,
            "messages": [{"role": "assistant", "content": "审核通过，继续写作"}],
        }


class NovelWorkflowGraph:
    """
    小说工作流图
    
    基于LangGraph构建的ReAct工作流
    """
    
    def __init__(self, checkpointer: Optional[Any] = None):
        self.checkpointer = checkpointer
        self.graph = None
        self._build_graph()
    
    def _build_graph(self):
        """构建工作流图"""
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph不可用，使用模拟实现")
            return
        
        # 创建状态图
        workflow = StateGraph(NovelState)
        
        # 添加节点
        workflow.add_node("planning", self._wrap_node(PlanningNode()))
        workflow.add_node("world_building", self._wrap_node(WorldBuildingNode()))
        workflow.add_node("character_design", self._wrap_node(CharacterDesignNode()))
        workflow.add_node("plot_design", self._wrap_node(PlotDesignNode()))
        workflow.add_node("outline", self._wrap_node(OutlineNode()))
        workflow.add_node("writing", self._wrap_node(WritingNode()))
        workflow.add_node("review", self._wrap_node(ReviewNode()))
        
        # 添加边
        workflow.set_entry_point("planning")
        workflow.add_edge("planning", "world_building")
        workflow.add_edge("world_building", "character_design")
        workflow.add_edge("character_design", "plot_design")
        workflow.add_edge("plot_design", "outline")
        workflow.add_edge("outline", "writing")
        workflow.add_edge("writing", "review")
        
        # 条件边：审核后决定是继续写作还是完成
        workflow.add_conditional_edges(
            "review",
            self._should_continue,
            {
                "continue": "writing",
                "finish": END
            }
        )
        
        # 编译图
        self.graph = workflow.compile(checkpointer=self.checkpointer)
        
        logger.info("[NovelWorkflowGraph] 工作流图构建完成")
    
    def _wrap_node(self, node: ReActNode):
        """包装节点为LangGraph可调用的函数"""
        async def wrapped_node(state: NovelState) -> Dict[str, Any]:
            return await node.execute(state)
        return wrapped_node
    
    def _should_continue(self, state: NovelState) -> str:
        """判断是否继续写作"""
        if state["current_phase"] == WritingPhase.COMPLETED:
            return "finish"
        return "continue"
    
    async def run(
        self,
        novel_id: int,
        user_input: str,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        运行工作流
        
        Args:
            novel_id: 小说ID
            user_input: 用户输入
            thread_id: 线程ID（用于断点续写）
            
        Returns:
            最终结果
        """
        if not self.graph:
            logger.error("[NovelWorkflowGraph] 工作流图未初始化")
            return {"error": "工作流图未初始化"}
        
        # 创建初始状态
        workflow_id = f"wf_{novel_id}_{thread_id or 'default'}"
        initial_state = create_initial_state(novel_id, workflow_id, user_input)
        
        # 配置
        config = {"configurable": {"thread_id": thread_id or f"novel_{novel_id}"}}
        
        logger.info(f"[NovelWorkflowGraph] 运行工作流: {workflow_id}")
        
        try:
            # 运行图
            result = await self.graph.ainvoke(initial_state, config)
            return result
            
        except Exception as e:
            logger.error(f"[NovelWorkflowGraph] 工作流执行失败: {e}")
            return {"error": str(e)}
    
    async def resume(
        self,
        thread_id: str,
        user_response: str
    ) -> Dict[str, Any]:
        """
        恢复工作流（断点续写）
        
        Args:
            thread_id: 线程ID
            user_response: 用户回复
            
        Returns:
            结果
        """
        if not self.graph:
            return {"error": "工作流图未初始化"}
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # 获取当前状态
        state = await self.graph.aget_state(config)
        
        # 更新状态（添加用户回复）
        updated_state = dict(state.values)
        updated_state["messages"].append({"role": "user", "content": user_response})
        updated_state["waiting_for_user"] = False
        updated_state["user_confirmed"] = True
        
        # 继续执行
        result = await self.graph.ainvoke(updated_state, config)
        return result
    
    def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取当前状态"""
        if not self.graph:
            return None
        
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            state = self.graph.get_state(config)
            return dict(state.values) if state else None
        except Exception as e:
            logger.error(f"[NovelWorkflowGraph] 获取状态失败: {e}")
            return None


# 便捷函数
async def run_novel_workflow(
    novel_id: int,
    user_input: str,
    checkpointer: Optional[Any] = None
) -> Dict[str, Any]:
    """
    运行小说工作流的便捷函数
    
    Args:
        novel_id: 小说ID
        user_input: 用户输入
        checkpointer: 检查点保存器
        
    Returns:
        结果
    """
    workflow = NovelWorkflowGraph(checkpointer)
    return await workflow.run(novel_id, user_input)
