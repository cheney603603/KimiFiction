"""
智能体模块
包含所有AI智能体的实现

推荐使用 AgentFactory 获取Agent实例，保留旧版独立Agent以兼容现有代码。
"""
from app.agents.base import BaseAgent
from app.agents.analyzer import GenreAnalyzerAgent
from app.agents.discussor import PlotDiscussorAgent
from app.agents.character_designer import CharacterDesignerAgent
from app.agents.outline_generator import OutlineGeneratorAgent
from app.agents.writer import ChapterWriterAgent
from app.agents.reader import ReaderAgent
from app.agents.consistency_checker import ConsistencyCheckerAgent
from app.agents.memory_manager import MemoryManagerAgent

# 统一Agent (推荐使用)
from app.agents.unified_agent import (
    UnifiedAgent,
    UnifiedWorldBuilderAgent,
    UnifiedCharacterDesignerAgent,
    UnifiedPlotDesignerAgent,
    UnifiedOutlineGeneratorAgent,
)

__all__ = [
    # Base
    "BaseAgent",
    # Legacy Agents (向后兼容)
    "GenreAnalyzerAgent",
    "PlotDiscussorAgent",
    "CharacterDesignerAgent",
    "OutlineGeneratorAgent",
    "ChapterWriterAgent",
    "ReaderAgent",
    "ConsistencyCheckerAgent",
    "MemoryManagerAgent",
    # Unified Agents (推荐)
    "UnifiedAgent",
    "UnifiedWorldBuilderAgent",
    "UnifiedCharacterDesignerAgent",
    "UnifiedPlotDesignerAgent",
    "UnifiedOutlineGeneratorAgent",
    # Factory
    "AgentFactory",
]


class AgentFactory:
    """
    Agent工厂类 - 统一创建和管理Agent实例
    
    使用方法:
        agent = AgentFactory.create("world_builder", context)
        agent = AgentFactory.create("character_designer", context)
    """
    
    _AGENT_MAP = {
        # 统一Agent (推荐)
        "world_builder": UnifiedWorldBuilderAgent,
        "character_designer": UnifiedCharacterDesignerAgent,
        "plot_designer": UnifiedPlotDesignerAgent,
        "outline_generator": UnifiedOutlineGeneratorAgent,
        
        # Legacy Agents (向后兼容)
        "analyzer": GenreAnalyzerAgent,
        "discussor": PlotDiscussorAgent,
        "writer": ChapterWriterAgent,
        "reader": ReaderAgent,
        "consistency": ConsistencyCheckerAgent,
        "memory": MemoryManagerAgent,
    }
    
    @classmethod
    def create(cls, agent_type: str, context: dict = None) -> BaseAgent:
        """
        创建Agent实例
        
        Args:
            agent_type: Agent类型标识
            context: 可选的初始化上下文
            
        Returns:
            Agent实例
            
        Raises:
            ValueError: 不支持的Agent类型
        """
        agent_class = cls._AGENT_MAP.get(agent_type)
        
        if agent_class is None:
            available = ", ".join(cls._AGENT_MAP.keys())
            raise ValueError(
                f"未知的Agent类型: {agent_type}\n"
                f"支持的类型: {available}"
            )
        
        # 统一Agent需要实例化
        if agent_type in ["world_builder", "character_designer", "plot_designer", "outline_generator"]:
            return agent_class()
        
        # Legacy Agent直接返回类或实例化
        return agent_class()
    
    @classmethod
    def list_agents(cls) -> list:
        """列出所有可用的Agent类型"""
        return list(cls._AGENT_MAP.keys())
    
    @classmethod
    def get_agent_info(cls, agent_type: str) -> dict:
        """获取Agent信息"""
        info = {
            "world_builder": {
                "name": "世界观构建Agent",
                "description": "构建完整的小说世界观设定",
                "unified": True,
            },
            "character_designer": {
                "name": "角色设计Agent", 
                "description": "设计主角、配角、反派等角色阵容",
                "unified": True,
            },
            "plot_designer": {
                "name": "剧情设计Agent",
                "description": "设计核心冲突和伏笔系统",
                "unified": True,
            },
            "outline_generator": {
                "name": "大纲生成Agent",
                "description": "生成三级大纲(卷/剧情弧/章节)",
                "unified": True,
            },
            "analyzer": {
                "name": "类型分析Agent",
                "description": "分析用户需求，确定小说类型",
                "unified": False,
            },
            "discussor": {
                "name": "剧情讨论Agent",
                "description": "与用户讨论剧情走向",
                "unified": False,
            },
            "writer": {
                "name": "章节写作Agent",
                "description": "撰写小说章节正文",
                "unified": False,
            },
            "reader": {
                "name": "阅读审核Agent",
                "description": "阅读并审核章节内容",
                "unified": False,
            },
            "consistency": {
                "name": "一致性检查Agent",
                "description": "检查角色/世界观一致性",
                "unified": False,
            },
            "memory": {
                "name": "记忆管理Agent",
                "description": "管理长期记忆和上下文",
                "unified": False,
            },
        }
        return info.get(agent_type, {})
