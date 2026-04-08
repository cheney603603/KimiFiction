"""
记忆节点模型
存储向量化检索用的剧情记忆节点
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Enum, DateTime, ForeignKey, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class NodeType(str, enum.Enum):
    """记忆节点类型枚举"""
    PLOT_POINT = "plot_point"           # 剧情节点
    CHARACTER_MOMENT = "character_moment"  # 角色关键时刻
    WORLD_BUILDING = "world_building"   # 世界观设定
    MYSTERY = "mystery"                 # 未解之谜/伏笔
    CONFLICT = "conflict"               # 冲突事件
    RELATIONSHIP = "relationship"       # 关系变化


class MemoryNode(Base):
    """记忆节点表"""
    
    __tablename__ = "memory_nodes"
    
    # 主键
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 外键
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属小说ID"
    )
    
    # 节点类型
    node_type: Mapped[NodeType] = mapped_column(
        Enum(NodeType),
        nullable=False,
        comment="节点类型"
    )
    
    # 节点内容
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="节点标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="节点内容")
    
    # 涉及章节范围
    chapter_range: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="涉及章节范围(如: 1-10)"
    )
    specific_chapter: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="具体章节号"
    )
    
    # 重要性评分
    importance_score: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        comment="重要性 0-1"
    )
    
    # 关联实体
    related_characters: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="关联角色(JSON数组)"
    )
    related_locations: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="关联地点(JSON数组)"
    )
    
    # 向量库ID（用于同步）
    embedding_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="向量库中的ID"
    )
    
    # 是否已解决（用于伏笔追踪）
    is_resolved: Mapped[bool] = mapped_column(
        default=False,
        comment="是否已解决/回收"
    )
    resolved_chapter: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="解决章节"
    )
    
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
    novel: Mapped["Novel"] = relationship("Novel", back_populates="memory_nodes")
    
    def __repr__(self) -> str:
        return f"<MemoryNode(id={self.id}, type='{self.node_type.value}', title='{self.title}')>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        import json
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "node_type": self.node_type.value,
            "title": self.title,
            "content": self.content,
            "chapter_range": self.chapter_range,
            "specific_chapter": self.specific_chapter,
            "importance_score": self.importance_score,
            "related_characters": json.loads(self.related_characters) if self.related_characters else [],
            "related_locations": json.loads(self.related_locations) if self.related_locations else [],
            "embedding_id": self.embedding_id,
            "is_resolved": self.is_resolved,
            "resolved_chapter": self.resolved_chapter,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
