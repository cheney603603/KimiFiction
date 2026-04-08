"""
章节模型
存储小说章节内容和元数据
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Integer, Enum, DateTime, ForeignKey, JSON, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class ChapterStatus(str, enum.Enum):
    """章节状态枚举"""
    DRAFT = "draft"           # 草稿
    REVIEW = "review"         # 审核中
    PUBLISHED = "published"   # 已发布


class Chapter(Base):
    """章节表"""
    
    __tablename__ = "chapters"
    
    # 复合索引优化查询
    __table_args__ = (
        Index('idx_novel_chapter', 'novel_id', 'chapter_number'),
        Index('idx_novel_status', 'novel_id', 'status'),
    )
    
    # 主键
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 外键
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属小说ID"
    )
    
    # 章节信息
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="章节序号")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="章节标题")
    
    # 内容（使用LONGTEXT类型存储大文本）
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="章节正文")
    
    # 摘要和关键信息
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="本章摘要")
    key_events: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="关键事件列表")
    characters_present: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, comment="出场角色列表")
    
    # 统计信息
    word_count: Mapped[int] = mapped_column(Integer, default=0, comment="字数统计")
    
    # 状态
    status: Mapped[ChapterStatus] = mapped_column(
        Enum(ChapterStatus),
        default=ChapterStatus.DRAFT,
        comment="章节状态"
    )
    
    # 生成元数据
    generation_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="生成参数")
    quality_score: Mapped[Optional[float]] = mapped_column(nullable=True, comment="质量评分")
    
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
    novel: Mapped["Novel"] = relationship("Novel", back_populates="chapters")
    feedbacks: Mapped[List["ChapterFeedback"]] = relationship(
        "ChapterFeedback",
        back_populates="chapter",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<Chapter(id={self.id}, novel_id={self.novel_id}, number={self.chapter_number}, title='{self.title}')>"
    
    def to_dict(self, include_content: bool = True) -> dict:
        """转换为字典"""
        result = {
            "id": self.id,
            "novel_id": self.novel_id,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "summary": self.summary,
            "key_events": self.key_events,
            "characters_present": self.characters_present,
            "word_count": self.word_count,
            "status": self.status.value,
            "quality_score": self.quality_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            result["content"] = self.content
        return result
