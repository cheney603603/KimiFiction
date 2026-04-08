"""
剧情大纲模型
存储小说的分卷大纲和剧情结构
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Outline(Base):
    """剧情大纲表"""
    
    __tablename__ = "outlines"
    
    # 主键
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 外键
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属小说ID"
    )
    
    # 卷信息
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="第几卷")
    volume_title: Mapped[str] = mapped_column(String(255), nullable=False, comment="卷标题")
    outline_type: Mapped[str] = mapped_column(String(50), default="main", comment="大纲类型: main/detail")
    
    # 剧情弧（JSON数组）
    arcs: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        comment="剧情弧数组"
    )
    # arcs JSON结构示例:
    # [
    #   {
    #     "arc_id": "arc_1",
    #     "title": "剧情弧标题",
    #     "description": "描述",
    #     "start_chapter": 1,
    #     "end_chapter": 10,
    #     "key_events": ["事件1", "事件2"],
    #     "conflict": "冲突描述",
    #     "resolution": "解决方式"
    #   }
    # ]
    
    # 详细内容（JSON存储，用于细纲等）
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="大纲内容JSON")
    
    # 关键节点
    key_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="关键节点描述")
    
    # 预计章节数
    target_chapters: Mapped[int] = mapped_column(
        Integer,
        default=100,
        comment="本卷预计章节数"
    )
    
    # 实际章节数
    actual_chapters: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="本卷实际章节数"
    )
    
    # 卷摘要
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="卷摘要")
    
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
    novel: Mapped["Novel"] = relationship("Novel", back_populates="outlines")
    
    def __repr__(self) -> str:
        return f"<Outline(id={self.id}, novel_id={self.novel_id}, volume={self.volume_number}, title='{self.volume_title}')>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "volume_number": self.volume_number,
            "volume_title": self.volume_title,
            "arcs": self.arcs,
            "key_points": self.key_points,
            "target_chapters": self.target_chapters,
            "actual_chapters": self.actual_chapters,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
