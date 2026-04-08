"""
小说生成工作流 - ReAct 有向状态图
基于 LangGraph 构建的多Agent协作系统

核心特性：
- ReAct 架构：Thought -> Action -> Observation 循环
- 有向状态图：通过条件边实现智能体间的循环协作
- 状态持久化：Redis Checkpoint 支持长周期任务断点续写
- AsyncIO并行：多个Agent可同时执行不同任务
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
from enum import Enum
import operator
import asyncio
from loguru import logger

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command, Interrupt, Send
    from langgraph.constants import Send as SendSig
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not available, workflow will use simplified mode")


# ─────────────────────────────────────────────────────────────
# 状态类型定义
# ─────────────────────────────────────────────────────────────

class NodeStatus(str, Enum):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class WritingPhase(str, Enum):
    """写作阶段"""
    AWAITING_GENRE = "awaiting_genre"
    DISCUSSING_PLOT = "discussing_plot"
    DESIGNING_CHARS = "designing_chars"
    GENERATING_OUTLINE = "generating_outline"
    WRITING_CHAPTER = "writing_chapter"
    REVIEWING = "reviewing"
    CONTINUING = "continuing"
    PAUSED = "paused"
    COMPLETED = "completed"


class NovelGraphState(TypedDict):
    """
    LangGraph 有向状态图状态定义
    
    所有 Agent 之间共享的数据通过这个状态传递。
    每个节点的输出会更新状态，然后触发下一个节点。
    """
    # ── 基础信息 ──
    novel_id: int
    workflow_id: str
    current_phase: WritingPhase
    
    # ── 用户交互 ──
    user_input: str
    messages: Annotated[List[Dict], operator.add]
    waiting_for_user: bool
    user_confirmed: bool
    
    # ── 创作数据 ──
    genre_analysis: Optional[Dict]
    confirmed_genre: Optional[str]
    plot_summary: str
    world_setting: Dict[str, Any]
    characters: List[Dict]
    plot_setting: Dict[str, Any]
    outline: Dict[str, Any]
    volumes: List[Dict]
    chapter_outlines: List[Dict[str, Any]]
    
    # ── 写作进度 ──
    current_chapter: int
    target_chapters: int
    completed_chapters: List[int]
    confirmed_chapters: List[int]
    auto_mode: bool
    
    # ── 当前章节写作状态 ──
    current_draft: str
    current_draft_version: int
    reader_feedback: Dict[str, Any]
    chapter_reward: float
    writer_reader_rounds: int
    
    # ── RAG 上下文 ──
    rag_context: Dict[str, Any]  # RAG检索结果
    
    # ── Checkpoint 专用 ──
    checkpoint_id: str
    
    # ── 错误与重试 ──
    error: Optional[str]
    retry_count: int
    
    # ── 节点执行状态（用于并行追踪） ──
    node_statuses: Dict[str, NodeStatus]


# ─────────────────────────────────────────────────────────────
# 节点函数（每个函数对应图中的一个节点）
# ─────────────────────────────────────────────────────────────

def _update_status(state: NovelGraphState, node: str, status: NodeStatus) -> None:
    """更新节点状态"""
    statuses = dict(state.get("node_statuses", {}))
    statuses[node] = status.value
    state["node_statuses"] = statuses


async def node_analyze_genre(state: NovelGraphState) -> NovelGraphState:
    """分析小说类型节点"""
    _update_status(state, "analyze_genre", NodeStatus.RUNNING)
    from app.agents.analyzer import GenreAnalyzerAgent
    agent = GenreAnalyzerAgent()
    result = await agent.process({"user_input": state.get("user_input", "")})
    if result.get("success"):
        state["genre_analysis"] = result.get("analysis")
        state["messages"].append({
            "role": "agent",
            "content": f"类型分析完成：{result['analysis'].get('suggested_genre', '未知')}",
            "type": "suggestion"
        })
    else:
        state["error"] = result.get("error")
    _update_status(state, "analyze_genre", NodeStatus.SUCCESS if result.get("success") else NodeStatus.FAILED)
    return state


async def node_discuss_plot(state: NovelGraphState) -> NovelGraphState:
    """剧情讨论节点"""
    _update_status(state, "discuss_plot", NodeStatus.RUNNING)
    from app.agents.discussor import PlotDiscussorAgent
    agent = PlotDiscussorAgent()
    genre = state.get("confirmed_genre") or state.get("genre_analysis", {}).get("suggested_genre")
    result = await agent.process({
        "user_input": state.get("user_input", ""),
        "genre": genre,
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
            state["plot_summary"] = _extract_plot_summary(state["messages"])
    _update_status(state, "discuss_plot", NodeStatus.SUCCESS)
    return state


async def node_design_characters(state: NovelGraphState) -> NovelGraphState:
    """角色设计节点"""
    _update_status(state, "design_characters", NodeStatus.RUNNING)
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
    _update_status(state, "design_characters", NodeStatus.SUCCESS)
    return state


async def node_generate_outline(state: NovelGraphState) -> NovelGraphState:
    """大纲生成节点"""
    _update_status(state, "generate_outline", NodeStatus.RUNNING)
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
        state["chapter_outlines"] = result.get("chapter_outlines", [])
        state["messages"].append({
            "role": "agent",
            "content": f"大纲生成完成！共{len(state['volumes'])}卷，预计{result.get('estimated_chapters', 0)}章。",
            "type": "suggestion"
        })
    _update_status(state, "generate_outline", NodeStatus.SUCCESS)
    return state


async def node_prepare_chapter(state: NovelGraphState) -> NovelGraphState:
    """准备章节写作：RAG检索上下文"""
    _update_status(state, "prepare_chapter", NodeStatus.RUNNING)
    from app.rag_system import HierarchicalRAG
    chapter_num = state.get("current_chapter", 1)
    
    # 找到本章细纲
    outline = {}
    for co in state.get("chapter_outlines", []):
        if co.get("chapter_number") == chapter_num:
            outline = co
            break
    
    if not outline:
        outline = {"title": f"第{chapter_num}章", "summary": "", "key_events": []}
    
    # RAG 检索相关上下文
    rag = HierarchicalRAG(state["novel_id"])
    rag_result = await rag.retrieve_for_writer(outline, top_k=8)
    state["rag_context"] = rag_result
    state["messages"].append({
        "role": "system",
        "content": f"[RAG] 第{chapter_num}章检索到{len(rag_result.get('chunks', []))}个相关上下文块",
        "type": "system"
    })
    _update_status(state, "prepare_chapter", NodeStatus.SUCCESS)
    return state


async def node_write_chapter(state: NovelGraphState) -> NovelGraphState:
    """
    撰写章节节点（集成 RAG + Writer-Reader RL）
    
    这是核心写作节点：
    1. 从 state 提取 RAG 上下文
    2. 调用 Writer-Reader 对抗循环
    3. 更新 draft 和 feedback
    """
    _update_status(state, "write_chapter", NodeStatus.RUNNING)
    from app.writer_reader_rl import WriterReaderLoop
    chapter_num = state.get("current_chapter", 1)
    
    # 获取本章细纲
    outline = {}
    for co in state.get("chapter_outlines", []):
        if co.get("chapter_number") == chapter_num:
            outline = co
            break
    if not outline:
        outline = {"title": f"第{chapter_num}章", "summary": "", "key_events": []}
    
    # 构建完整上下文（融合 RAG 结果）
    full_context = dict(state.get("rag_context", {}))
    full_context.update({
        "world_setting": state.get("world_setting", {}),
        "characters": state.get("characters", []),
        "plot_setting": state.get("plot_setting", {}),
        "writing_style": "叙事流畅，情节紧凑",
        "env_level": "normal",
        "dialogue_ratio": 0.3,
    })
    
    # 运行 Writer-Reader 对抗循环
    loop = WriterReaderLoop(
        novel_id=state["novel_id"],
        chapter_number=chapter_num,
        max_rounds=state.get("writer_reader_rounds", 3),
        score_threshold=0.78,
    )
    
    result = await loop.run(
        outline=outline,
        characters=state.get("characters", []),
        context=full_context,
        initial_draft=state.get("current_draft", ""),
    )
    
    if result.get("success"):
        state["current_draft"] = result.get("final_draft", "")
        state["current_draft_version"] = result.get("total_rounds", 1)
        state["chapter_reward"] = result.get("final_reward", 0)
        state["completed_chapters"].append(chapter_num)
        
        # 从循环结果中提取 Reader 反馈
        if result.get("loop_history"):
            last_round = result["loop_history"][-1]
            state["reader_feedback"] = {
                "reader_score": last_round.get("reader_score", 0),
                "hook_score": last_round.get("hook_score", 0),
                "would_continue_reading": last_round.get("continue_reading", False),
            }
        
        # 记录学习报告
        learning = loop.get_learning_report()
        state["messages"].append({
            "role": "agent",
            "content": (
                f"第{chapter_num}章撰写完成！"
                f"轮次={result['total_rounds']}, "
                f"Reward={result['final_reward']:.3f}, "
                f"Reader评分={learning.get('reward_progression', [0])[-1]:.3f}"
            ),
            "type": "chapter_complete",
            "data": result
        })
        
        # RAG 索引本章（后台异步）
        asyncio.create_task(_index_chapter_async(
            state["novel_id"], chapter_num, result["final_draft"], outline
        ))
    else:
        state["error"] = result.get("error", "写作失败")
    
    _update_status(state, "write_chapter", NodeStatus.SUCCESS)
    return state


async def _index_chapter_async(novel_id: int, chapter_num: int, content: str, outline: Dict):
    """异步索引章节到 RAG 系统"""
    try:
        from app.rag_system import HierarchicalRAG
        rag = HierarchicalRAG(novel_id)
        await rag.index_chapter(
            chapter_number=chapter_num,
            chapter_content=content,
            chapter_summary=outline.get("summary", ""),
        )
        logger.info(f"[RAG] 第{chapter_num}章已异步索引")
    except Exception as e:
        logger.error(f"[RAG] 第{chapter_num}章索引失败: {e}")


async def node_review_chapter(state: NovelGraphState) -> NovelGraphState:
    """审核章节节点"""
    _update_status(state, "review_chapter", NodeStatus.RUNNING)
    from app.agents.reviewer import ReviewerAgent
    agent = ReviewerAgent()
    result = await agent.process({
        "operation": "review",
        "chapter_content": state.get("current_draft", ""),
        "chapter_number": state.get("current_chapter", 0),
        "characters": state.get("characters", []),
        "world_setting": state.get("world_setting", {}),
        "plot_setting": state.get("plot_setting", {}),
        "reader_feedback": state.get("reader_feedback", {}),
    })
    if result.get("success"):
        state["messages"].append({
            "role": "agent",
            "content": f"章节审核完成，质量评分={result.get('quality_score', 0):.2f}",
            "type": "review"
        })
    _update_status(state, "review_chapter", NodeStatus.SUCCESS)
    return state


async def node_update_memory(state: NovelGraphState) -> NovelGraphState:
    """更新记忆节点"""
    _update_status(state, "update_memory", NodeStatus.RUNNING)
    from app.agents.memory_manager import MemoryManagerAgent
    agent = MemoryManagerAgent()
    result = await agent.process({
        "chapter_content": state.get("current_draft", ""),
        "chapter_number": state.get("current_chapter", 0),
        "characters": state.get("characters", [])
    })
    if result.get("success"):
        # 推进到下一章
        state["current_chapter"] += 1
        state["current_draft"] = ""
        state["current_draft_version"] = 0
    _update_status(state, "update_memory", NodeStatus.SUCCESS)
    return state


def node_wait_for_user(state: NovelGraphState) -> NovelGraphState:
    """等待用户输入（路由节点）"""
    state["waiting_for_user"] = True
    return state


# ─────────────────────────────────────────────────────────────
# 条件路由函数（有向边）
# ─────────────────────────────────────────────────────────────

def route_genre(state: NovelGraphState) -> Literal["wait_user", "discuss_plot"]:
    """类型分析后的路由"""
    if state.get("confirmed_genre"):
        return "discuss_plot"
    return "wait_user"


def route_discuss(state: NovelGraphState) -> Literal["design_characters", "wait_user"]:
    """剧情讨论后的路由"""
    if state.get("discussion_stage") == "complete":
        return "design_characters"
    return "wait_user"


def route_characters(state: NovelGraphState) -> Literal["generate_outline", "wait_user"]:
    """角色设计后的路由"""
    if len(state.get("characters", [])) > 0:
        return "generate_outline"
    return "wait_user"


def route_outline(state: NovelGraphState) -> Literal["write_chapter", "wait_user"]:
    """大纲生成后的路由"""
    if state.get("outline") and state.get("auto_mode"):
        return "write_chapter"
    if state.get("outline"):
        return "write_chapter"
    return "wait_user"


def route_chapter(state: NovelGraphState) -> Literal[
    "write_chapter", "review_chapter", "update_memory", "__end__"
]:
    """
    章节写作循环路由（ReAct 架构的循环边）
    
    写作流程：
    write_chapter -> review_chapter -> update_memory
                                           |
    是否继续写作？<---(未完成)----(已完成)----+
                              |
                              v
                         __end__ (全部完成)
    """
    current = state.get("current_chapter", 1)
    target = state.get("target_chapters", 100)
    
    if current > target:
        return "__end__"
    
    if state.get("auto_mode"):
        return "write_chapter"
    
    return "update_memory"


def route_wait_user(state: NovelGraphState) -> Literal[
    "analyze_genre", "discuss_plot", "design_characters",
    "generate_outline", "write_chapter"
]:
    """用户输入后的路由"""
    phase = state.get("current_phase", WritingPhase.AWAITING_GENRE)
    routing = {
        WritingPhase.AWAITING_GENRE.value: "analyze_genre",
        WritingPhase.DISCUSSING_PLOT.value: "discuss_plot",
        WritingPhase.DESIGNING_CHARS.value: "design_characters",
        WritingPhase.GENERATING_OUTLINE.value: "generate_outline",
        WritingPhase.WRITING_CHAPTER.value: "write_chapter",
    }
    return routing.get(phase.value, "analyze_genre")


# ─────────────────────────────────────────────────────────────
# LangGraph 有向状态图构建
# ─────────────────────────────────────────────────────────────

_graph_instance = None


def build_novel_graph():
    """
    构建 LangGraph 有向状态图
    
    图结构：
    
    [analyze_genre] ──(confirmed)──> [discuss_plot] ──(complete)──> [design_characters]
                                          │                              │
                                     (wait) v                       (wait) v
                                  [wait_user] <───────────────── [wait_user]
                                          │                              │
                                     (confirm) v                       (confirm) v
                                  [generate_outline] ──(done)──> [prepare_chapter]
                                                                    │
                                                                    v
                                                             [write_chapter]
                                                                    │
                                                                    v
                                                             [review_chapter]
                                                                    │
                                                                    v
                                                             [update_memory] ──(未完成)──┐
                                                                                          │
                                                                              (current < target)───>[write_chapter]
                                                                                          │
                                                                               (全部完成)────>__end__
    """
    if not LANGGRAPH_AVAILABLE:
        logger.warning("[NovelGraph] LangGraph不可用，将使用简化模式")
        return None
    
    workflow = StateGraph(NovelGraphState)
    
    # 注册节点
    workflow.add_node("analyze_genre", node_analyze_genre)
    workflow.add_node("discuss_plot", node_discuss_plot)
    workflow.add_node("design_characters", node_design_characters)
    workflow.add_node("generate_outline", node_generate_outline)
    workflow.add_node("prepare_chapter", node_prepare_chapter)
    workflow.add_node("write_chapter", node_write_chapter)
    workflow.add_node("review_chapter", node_review_chapter)
    workflow.add_node("update_memory", node_update_memory)
    workflow.add_node("wait_user", node_wait_for_user)
    
    # 设置入口点
    workflow.set_entry_point("analyze_genre")
    
    # 类型分析后的路由
    workflow.add_conditional_edges(
        "analyze_genre",
        route_genre,
        {
            "wait_user": "wait_user",
            "discuss_plot": "discuss_plot",
        }
    )
    
    # 剧情讨论后的路由
    workflow.add_conditional_edges(
        "discuss_plot",
        route_discuss,
        {
            "design_characters": "design_characters",
            "wait_user": "wait_user",
        }
    )
    
    # 角色设计后的路由
    workflow.add_conditional_edges(
        "design_characters",
        route_characters,
        {
            "generate_outline": "generate_outline",
            "wait_user": "wait_user",
        }
    )
    
    # 大纲生成后
    workflow.add_conditional_edges(
        "generate_outline",
        route_outline,
        {
            "write_chapter": "prepare_chapter",
            "wait_user": "wait_user",
        }
    )
    
    # 章节写作循环（有向边）
    workflow.add_edge("prepare_chapter", "write_chapter")
    workflow.add_edge("write_chapter", "review_chapter")
    workflow.add_edge("review_chapter", "update_memory")
    
    # 写作循环路由（回到prepare_chapter继续写下一章）
    workflow.add_conditional_edges(
        "update_memory",
        route_chapter,
        {
            "write_chapter": "prepare_chapter",
            "__end__": END,
        }
    )
    
    # 用户输入后路由
    workflow.add_conditional_edges(
        "wait_user",
        route_wait_user,
        {
            "analyze_genre": "analyze_genre",
            "discuss_plot": "discuss_plot",
            "design_characters": "design_characters",
            "generate_outline": "generate_outline",
            "write_chapter": "prepare_chapter",
        }
    )
    
    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["wait_user"],
    )


def get_novel_graph():
    """获取工作流图的单例"""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_novel_graph()
    return _graph_instance


# ─────────────────────────────────────────────────────────────
# 异步并行节点执行（用于提升吞吐量）
# ─────────────────────────────────────────────────────────────

async def run_parallel_nodes(
    state: NovelGraphState,
    node_names: List[str]
) -> NovelGraphState:
    """
    并行执行多个节点（AsyncIO）
    
    用于以下场景：
    - 同时执行 RAG 检索和角色状态查询
    - 同时查询多个数据源
    - 并行生成多个候选内容
    """
    node_funcs = {
        "prepare_chapter": node_prepare_chapter,
        "update_memory": node_update_memory,
    }
    
    tasks = []
    for name in node_names:
        func = node_funcs.get(name)
        if func:
            tasks.append(func(state))
    
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[Parallel] 节点 {node_names[i]} 执行失败: {result}")
    
    return state


# ─────────────────────────────────────────────────────────────
# 便捷工厂函数
# ─────────────────────────────────────────────────────────────

def create_initial_state(
    novel_id: int,
    user_input: str = "",
    target_chapters: int = 100,
    auto_mode: bool = False,
) -> NovelGraphState:
    """创建工作流初始状态"""
    import uuid
    return NovelGraphState(
        novel_id=novel_id,
        workflow_id=f"wf_{novel_id}_{uuid.uuid4().hex[:8]}",
        current_phase=WritingPhase.AWAITING_GENRE,
        user_input=user_input,
        messages=[],
        waiting_for_user=False,
        user_confirmed=False,
        genre_analysis=None,
        confirmed_genre=None,
        plot_summary="",
        world_setting={},
        characters=[],
        plot_setting={},
        outline={},
        volumes=[],
        chapter_outlines=[],
        current_chapter=0,
        target_chapters=target_chapters,
        completed_chapters=[],
        confirmed_chapters=[],
        auto_mode=auto_mode,
        current_draft="",
        current_draft_version=0,
        reader_feedback={},
        chapter_reward=0.0,
        writer_reader_rounds=3,
        rag_context={},
        checkpoint_id=str(uuid.uuid4()),
        error=None,
        retry_count=0,
        node_statuses={},
    )


async def run_workflow(
    initial_state: NovelGraphState,
    checkpoint_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    运行工作流（断点续写）
    
    Args:
        initial_state: 初始状态
        checkpoint_id: checkpoint ID（用于断点续写）
    """
    graph = get_novel_graph()
    if graph is None:
        logger.error("[NovelGraph] 工作流图未初始化")
        return {"error": "LangGraph not available"}
    
    config = {
        "configurable": {
            "thread_id": checkpoint_id or initial_state.get("checkpoint_id", "default"),
        }
    }
    
    try:
        result = await graph.ainvoke(initial_state, config=config)
        return result
    except Exception as e:
        logger.error(f"[NovelGraph] 工作流执行失败: {e}")
        return {**initial_state, "error": str(e)}


async def resume_workflow(
    checkpoint_id: str,
    user_input: str = "",
) -> Dict[str, Any]:
    """
    从断点恢复工作流（断点续写）
    """
    graph = get_novel_graph()
    if graph is None:
        return {"error": "LangGraph not available"}
    
    config = {
        "configurable": {
            "thread_id": checkpoint_id,
        }
    }
    
    try:
        # 从 checkpoint 恢复状态
        snapshot = await graph.aget_state(config)
        if snapshot is None:
            return {"error": f"Checkpoint {checkpoint_id} not found"}
        
        # 注入用户输入，继续执行
        updated_state = dict(snapshot.values)
        updated_state["user_input"] = user_input
        updated_state["waiting_for_user"] = False
        updated_state["user_confirmed"] = True
        
        result = await graph.ainvoke(Command(resume=user_input), config=config)
        return result
    except Exception as e:
        logger.error(f"[NovelGraph] 断点续写失败: {e}")
        return {"error": str(e)}


async def get_workflow_snapshot(
    checkpoint_id: str,
) -> Optional[Dict[str, Any]]:
    """获取当前工作流快照"""
    graph = get_novel_graph()
    if graph is None:
        return None
    
    config = {"configurable": {"thread_id": checkpoint_id}}
    try:
        snapshot = await graph.aget_state(config)
        if snapshot:
            return {
                "checkpoint_id": checkpoint_id,
                "values": dict(snapshot.values),
                "next_nodes": list(snapshot.next) if hasattr(snapshot, 'next') else [],
                "created_at": getattr(snapshot, 'created_at', None),
            }
    except Exception as e:
        logger.error(f"[NovelGraph] 获取快照失败: {e}")
    return None


def _extract_plot_summary(messages: List[Dict]) -> str:
    """从消息中提取剧情摘要"""
    agent_messages = [
        m.get("content", "") 
        for m in messages 
        if m.get("role") == "agent"
    ]
    return " ".join(agent_messages[-3:])
