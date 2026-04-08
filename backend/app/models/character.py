"""
角色模型
存储小说角色信息和状态
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, Integer, Enum, DateTime, ForeignKey, JSON, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class RoleType(str, enum.Enum):
    """角色类型枚举"""
    PROTAGONIST = "protagonist"      # 主角
    ANTAGONIST = "antagonist"        # 反派
    SUPPORTING = "supporting"        # 配角
    MINOR = "minor"                  # 龙套


class Character(Base):
    """角色表"""
    
    __tablename__ = "characters"
    
    # 主键
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 外键
    novel_id: Mapped[int] = mapped_column(
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属小说ID"
    )
    
    # 基本信息
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="角色名称")
    role_type: Mapped[RoleType] = mapped_column(
        Enum(RoleType),
        default=RoleType.SUPPORTING,
        comment="角色类型"
    )
    
    # 详细人设（JSON存储）
    profile: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="详细人设"
    )
    # profile JSON结构示例:
    # {
    #   "age": 20,
    #   "gender": "male",
    #   "appearance": "描述...",
    #   "personality": "描述...",
    #   "background": "背景故事...",
    #   "mbti": "INTJ",
    #   "goals": ["目标1", "目标2"],
    #   "fears": ["恐惧1"],
    #   "skills": ["技能1", "技能2"],
    #   "relationships": {
    #     "角色A": "关系描述",
    #     "角色B": "关系描述"
    #   }
    # }
    
    # 当前状态（动态更新）
    current_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="当前状态")
    # 当前状态示例:
    # {
    #   "location": "当前地点",
    #   "health": "健康状态",
    #   "mood": "心情",
    #   "cultivation_level": "修为等级（修仙类）",
    #   "current_goal": "当前目标",
    #   "recent_events": "最近经历"
    # }
    
    # 角色弧光
    arc_progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="角色弧光进度 0-1"
    )
    
    # 出场信息
    first_appearance: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="首次出场章节"
    )
    last_appearance: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="最后出场章节"
    )
    appearance_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="出场次数"
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
    novel: Mapped["Novel"] = relationship("Novel", back_populates="characters")
    
    def __repr__(self) -> str:
        return f"<Character(id={self.id}, name='{self.name}', type='{self.role_type.value}')>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "role_type": self.role_type.value,
            "profile": self.profile,
            "current_status": self.current_status,
            "arc_progress": self.arc_progress,
            "first_appearance": self.first_appearance,
            "last_appearance": self.last_appearance,
            "appearance_count": self.appearance_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def update_status(self, new_status: dict):
        """更新角色当前状态"""
        import json
        self.current_status = json.dumps(new_status, ensure_ascii=False)
    
    def get_status_dict(self) -> dict:
        """获取当前状态字典"""
        import json
        if not self.current_status:
            return {}
        try:
            return json.loads(self.current_status)
        except json.JSONDecodeError:
            return {}
