"""
小说项目模型
存储小说的基本信息和状态
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Integer, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class NovelStatus(str, enum.Enum):
    """小说状态枚举"""
    planning = "planning"       # 规划中
    writing = "writing"         # 撰写中
    paused = "paused"           # 暂停
    completed = "completed"     # 已完成


class Novel(Base):
    """小说项目表"""
    
    __tablename__ = "novels"
    
    # 主键
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 基本信息
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="小说标题")
    genre: Mapped[str] = mapped_column(String(100), nullable=True, comment="小说类型(玄幻/科幻/都市等)")
    style_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="风格提示词")
    
    # 进度统计
    total_chapters: Mapped[int] = mapped_column(Integer, default=0, comment="总章节数")
    current_chapter: Mapped[int] = mapped_column(Integer, default=0, comment="当前章节序号")
    total_words: Mapped[int] = mapped_column(Integer, default=0, comment="总字数")
    
    # 状态
    status: Mapped[NovelStatus] = mapped_column(
        Enum(NovelStatus),
        default=NovelStatus.planning,
        comment="小说状态"
    )
    
    # 元数据
    target_chapters: Mapped[int] = mapped_column(Integer, default=100, comment="目标章节数")
    words_per_chapter: Mapped[int] = mapped_column(Integer, default=3000, comment="每章目标字数")
    
    # 类型分析结果（JSON存储）
    genre_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="类型分析结果JSON")
    
    # 世界观设定（JSON存储）
    world_setting: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="世界观设定JSON")
    
    # 软删除标记
    is_deleted: Mapped[bool] = mapped_column(default=False, comment="是否已删除")
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间"
    )
    
    # 关系
    chapters: Mapped[List["Chapter"]] = relationship(
        "Chapter",
        back_populates="novel",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    characters: Mapped[List["Character"]] = relationship(
        "Character",
        back_populates="novel",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    outlines: Mapped[List["Outline"]] = relationship(
        "Outline",
        back_populates="novel",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    memory_nodes: Mapped[List["MemoryNode"]] = relationship(
        "MemoryNode",
        back_populates="novel",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    feedbacks: Mapped[List["ChapterFeedback"]] = relationship(
        "ChapterFeedback",
        back_populates="novel",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    framework_adjustments: Mapped[List["FrameworkAdjustment"]] = relationship(
        "FrameworkAdjustment",
        back_populates="novel",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    writing_sessions: Mapped[List["WritingSession"]] = relationship(
        "WritingSession",
        back_populates="novel",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<Novel(id={self.id}, title='{self.title}', status='{self.status.value}')>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "genre": self.genre,
            "style_prompt": self.style_prompt,
            "total_chapters": self.total_chapters,
            "current_chapter": self.current_chapter,
            "total_words": self.total_words,
            "status": self.status.value,
            "target_chapters": self.target_chapters,
            "words_per_chapter": self.words_per_chapter,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
