"""
章节相关Pydantic模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChapterBase(BaseModel):
    """章节基础模型"""
    novel_id: int = Field(..., description="所属小说ID")
    chapter_number: int = Field(..., ge=1, description="章节序号")
    title: str = Field(..., min_length=1, max_length=255, description="章节标题")
    content: str = Field(..., min_length=1, description="章节内容")


class ChapterCreate(ChapterBase):
    """创建章节请求模型"""
    summary: Optional[str] = None
    key_events: Optional[List[str]] = None
    characters_present: Optional[List[str]] = None


class ChapterUpdate(BaseModel):
    """更新章节请求模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    summary: Optional[str] = None
    key_events: Optional[List[str]] = None
    characters_present: Optional[List[str]] = None
    status: Optional[str] = None


class ChapterResponse(BaseModel):
    """章节响应模型"""
    id: int
    novel_id: int
    chapter_number: int
    title: str
    content: str
    summary: Optional[str]
    key_events: Optional[List[str]]
    characters_present: Optional[List[str]]
    word_count: int
    status: str
    quality_score: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ChapterListItem(BaseModel):
    """章节列表项（不含内容）"""
    id: int
    novel_id: int
    chapter_number: int
    title: str
    summary: Optional[str]
    word_count: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChapterListResponse(BaseModel):
    """章节列表响应"""
    items: List[ChapterListItem]
    total: int
    skip: int
    limit: int


class ChapterGenerateRequest(BaseModel):
    """生成章节请求"""
    novel_id: int
    chapter_number: Optional[int] = None  # 为None则自动续写
    outline_guidance: Optional[str] = None  # 额外大纲指导
    temperature: float = Field(default=0.7, ge=0, le=2)
    style_override: Optional[str] = None  # 临时风格覆盖


class ChapterGenerationStatus(BaseModel):
    """章节生成状态"""
    task_id: str
    status: str  # pending, generating, completed, failed
    progress: float  # 0-100
    message: Optional[str] = None
