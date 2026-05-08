"""
实体模型 - Entity-Aware RAG 核心数据层
存储小说世界中的各类实体、状态与关系
"""
import enum
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EntityType(str, enum.Enum):
    """实体类型枚举"""
    CHARACTER = "character"      # 角色
    FACTION = "faction"          # 势力/宗门/组织
    SKILL = "skill"              # 功法/武技/神通
    ITEM = "item"                # 物品/法宝/丹药
    LOCATION = "location"        # 地点/场景


class Entity(Base):
    """实体主表 - 存储小说世界中的各类实体及其状态卡片"""
    
    __tablename__ = "entities"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    entity_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="规范实体ID"
    )
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="所属小说ID"
    )
    canonical_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="规范名称"
    )
    aliases: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="别名列表(JSON数组)"
    )
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType), nullable=False, comment="实体类型"
    )
    state_vector: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="状态向量(JSON对象)"
    )
    narrative_summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="叙事摘要"
    )
    last_mentioned_paragraph_id: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="最后提及段落ID"
    )
    last_mentioned_chapter_number: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="最后提及章节号"
    )
    embedding: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="别名embedding(JSON数组)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    
    novel: Mapped["Novel"] = relationship("Novel", back_populates="entities")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "novel_id": self.novel_id,
            "canonical_name": self.canonical_name,
            "aliases": json.loads(self.aliases) if self.aliases else [],
            "entity_type": self.entity_type.value,
            "state_vector": json.loads(self.state_vector) if self.state_vector else {},
            "narrative_summary": self.narrative_summary,
            "last_mentioned_paragraph_id": self.last_mentioned_paragraph_id,
            "last_mentioned_chapter_number": self.last_mentioned_chapter_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def get_state_dict(self) -> dict:
        if not self.state_vector:
            return {}
        try:
            return json.loads(self.state_vector)
        except json.JSONDecodeError:
            return {}
    
    def set_state_dict(self, state: dict):
        self.state_vector = json.dumps(state, ensure_ascii=False)


class EntityRelationship(Base):
    """实体关系表"""
    
    __tablename__ = "entity_relationships"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="所属小说ID"
    )
    source_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="源实体ID"
    )
    target_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="目标实体ID"
    )
    relation_type: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="关系类型"
    )
    established_at_paragraph_id: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="关系建立段落ID"
    )
    established_at_chapter_number: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="关系建立章节号"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "established_at_paragraph_id": self.established_at_paragraph_id,
            "established_at_chapter_number": self.established_at_chapter_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
