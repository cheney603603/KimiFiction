"""番茄小说榜单快照（hot_topics）：品类榜单入库，供榜单页与选题提示使用。"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Integer, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HotTopic(Base):
    """番茄榜单快照（每个 品类×榜型 每天一条榜单条目）。"""

    __tablename__ = "hot_topics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    gender: Mapped[str] = mapped_column(String(10), default="", comment="male/female")
    genre: Mapped[str] = mapped_column(String(30), default="", comment="品类名（解码后）")
    genre_id: Mapped[str] = mapped_column(String(20), default="", comment="品类 ID")
    rank_type: Mapped[str] = mapped_column(String(10), default="", comment="read/new")
    rank: Mapped[int] = mapped_column(Integer, default=0)
    rank_change: Mapped[int] = mapped_column(Integer, default=0, comment="较昨日位次变化")
    book_id: Mapped[str] = mapped_column(String(30), default="")
    book_name: Mapped[str] = mapped_column(String(100), default="")
    author: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    read_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="")
    last_chapter: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
