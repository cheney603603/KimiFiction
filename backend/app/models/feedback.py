"""
反馈数据模型
记录用户对章节和框架的修改意见
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class ChapterFeedback(Base):
    """章节反馈"""
    __tablename__ = "chapter_feedbacks"
    
    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)
    chapter_number = Column(Integer, nullable=False)
    
    # 反馈类型
    feedback_type = Column(String(50), nullable=False)  # revision, style, plot, character, etc.
    
    # 反馈内容
    feedback_content = Column(Text, nullable=False)
    
    # 处理状态
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    processing_result = Column(Text, nullable=True)
    
    # 关联
    revision_id = Column(Integer, nullable=True)  # 关联的修订版本
    
    # 元数据
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    novel = relationship("Novel", back_populates="feedbacks")
    # 使用字符串引用避免循环导入
    chapter = relationship("Chapter", back_populates="feedbacks", foreign_keys=[chapter_id])
    
    def __repr__(self):
        return f"<ChapterFeedback(id={self.id}, chapter={self.chapter_number}, type={self.feedback_type})>"


class FrameworkAdjustment(Base):
    """框架调整记录"""
    __tablename__ = "framework_adjustments"
    
    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    
    # 调整类型
    adjustment_type = Column(String(50), nullable=False)  # outline, character_arc, foreshadowing, style, etc.
    
    # 调整范围
    target_phase = Column(String(50), nullable=True)  # 影响的阶段
    affected_chapters = Column(String(100), nullable=True)  # 影响的章节范围，如 "10-30"
    
    # 调整内容
    original_content = Column(Text, nullable=True)  # 原内容
    new_content = Column(Text, nullable=True)  # 新内容
    adjustment_reason = Column(Text, nullable=True)  # 调整原因
    
    # 状态
    is_applied = Column(Boolean, default=False)
    applied_at = Column(DateTime, nullable=True)
    
    # 元数据
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    novel = relationship("Novel", back_populates="framework_adjustments")
    
    def __repr__(self):
        return f"<FrameworkAdjustment(id={self.id}, type={self.adjustment_type}, applied={self.is_applied})>"


class WritingSession(Base):
    """写作会话记录"""
    __tablename__ = "writing_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    
    # 会话信息
    session_type = Column(String(50), nullable=False)  # planning, writing, revision, review
    start_chapter = Column(Integer, nullable=True)
    end_chapter = Column(Integer, nullable=True)
    
    # 会话统计
    chapters_written = Column(Integer, default=0)
    words_written = Column(Integer, default=0)
    
    # 状态
    status = Column(String(20), default="active")  # active, completed, paused
    
    # 元数据
    started_at = Column(DateTime, default=datetime.now)
    ended_at = Column(DateTime, nullable=True)
    
    # 关系
    novel = relationship("Novel", back_populates="writing_sessions")
    
    def __repr__(self):
        return f"<WritingSession(id={self.id}, type={self.session_type}, status={self.status})>"
