"""
工作流模块
包含LangGraph状态机和工作流编排
"""
from app.workflows.novel_workflow import (
    NovelGraphState,
    WritingPhase,
    NodeStatus,
    build_novel_graph,
    get_novel_graph,
    create_initial_state,
    run_workflow,
    resume_workflow,
    get_workflow_snapshot,
    run_parallel_nodes,
)

__all__ = [
    "NovelGraphState",
    "WritingPhase",
    "NodeStatus",
    "build_novel_graph",
    "get_novel_graph",
    "create_initial_state",
    "run_workflow",
    "resume_workflow",
    "get_workflow_snapshot",
    "run_parallel_nodes",
]
