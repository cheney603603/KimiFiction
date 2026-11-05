"""LLM 用量日志（token 统计 / 重试统计 / 阶段归属）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMUsageLog(Base):
    """每次 LLM 调用的用量记录。"""

    __tablename__ = "llm_usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="归属用户")
    novel_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="归属小说")
    chapter_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="归属章节")
    phase: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="工作流阶段")
    agent_name: Mapped[str] = mapped_column(String(50), default="", comment="调用方 Agent")
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="模型名")
    provider: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, comment="提供商")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, comment="输入 token 估算")
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, comment="输出 token 估算")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, comment="耗时毫秒")
    status: Mapped[str] = mapped_column(String(20), default="success", comment="success/error")
    retry_count: Mapped[int] = mapped_column(Integer, default=0, comment="本次调用内部重试次数")
    error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="失败原因摘要")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
