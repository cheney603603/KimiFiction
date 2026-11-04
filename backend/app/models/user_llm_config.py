"""用户 LLM 配置（BYOK：每个用户可配置自己的 API Key / Base URL / 模型）"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserLLMConfig(Base):
    """用户级 LLM 配置表，api_key 密文存储（Fernet）。"""

    __tablename__ = "user_llm_configs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(50), default="deepseek", comment="提供商")
    api_key_enc: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="加密后的 API Key")
    base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Base URL")
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="模型名")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserLLMConfig(user_id={self.user_id}, provider={self.provider})>"
