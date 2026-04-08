"""
用户模型
存储用户信息和认证数据
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """用户表"""
    
    __tablename__ = "users"
    
    # 主键
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 基本信息
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="邮箱"
    )
    nickname: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="昵称"
    )
    
    # 密码（存储哈希值）
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码哈希"
    )
    
    # 用户状态
    is_active: Mapped[bool] = mapped_column(
        default=True,
        comment="是否激活"
    )
    is_superuser: Mapped[bool] = mapped_column(
        default=False,
        comment="是否超级用户"
    )
    
    # 头像
    avatar: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="头像URL"
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
    
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录时间"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """转换为字典"""
        result = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "nickname": self.nickname,
            "is_active": self.is_active,
            "avatar": self.avatar,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        
        if include_sensitive:
            result["is_superuser"] = self.is_superuser
        
        return result
