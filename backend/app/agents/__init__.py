"""
智能体模块
包含所有AI智能体的实现
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

__all__ = [
    "BaseAgent",
    "GenreAnalyzerAgent",
    "PlotDiscussorAgent",
    "CharacterDesignerAgent",
    "OutlineGeneratorAgent",
    "ChapterWriterAgent",
    "ReaderAgent",
    "ConsistencyCheckerAgent",
    "MemoryManagerAgent",
]
