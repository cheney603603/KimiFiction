"""
记忆节点相关Pydantic模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class MemoryNodeBase(BaseModel):
    """记忆节点基础模型"""
    novel_id: int = Field(..., description="所属小说ID")
    node_type: str = Field(..., description="节点类型")
    title: str = Field(..., min_length=1, max_length=255, description="节点标题")
    content: str = Field(..., min_length=1, description="节点内容")


class MemoryNodeCreate(MemoryNodeBase):
    """创建记忆节点请求模型"""
    chapter_range: str = Field(..., description="涉及章节范围")
    specific_chapter: Optional[int] = None
    importance_score: float = Field(default=0.5, ge=0, le=1)
    related_characters: Optional[List[str]] = Field(default_factory=list)
    related_locations: Optional[List[str]] = Field(default_factory=list)
    embedding_id: Optional[str] = None


class MemoryNodeUpdate(BaseModel):
    """更新记忆节点请求模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    importance_score: Optional[float] = Field(None, ge=0, le=1)
    is_resolved: Optional[bool] = None
    resolved_chapter: Optional[int] = None


class MemoryNodeResponse(BaseModel):
    """记忆节点响应模型"""
    id: int
    novel_id: int
    node_type: str
    title: str
    content: str
    chapter_range: str
    specific_chapter: Optional[int]
    importance_score: float
    related_characters: List[str]
    related_locations: List[str]
    embedding_id: str
    is_resolved: bool
    resolved_chapter: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MemorySearchRequest(BaseModel):
    """记忆搜索请求"""
    novel_id: int
    query: str = Field(..., min_length=1, description="搜索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数")
    node_type: Optional[str] = None  # 按类型筛选
    min_importance: float = Field(default=0.0, ge=0, le=1)


class MemorySearchResult(BaseModel):
    """记忆搜索结果项"""
    node: MemoryNodeResponse
    similarity_score: float


class MemorySearchResponse(BaseModel):
    """记忆搜索响应"""
    query: str
    results: List[MemorySearchResult]
    total: int


class MemoryConsolidateResult(BaseModel):
    """记忆整理结果"""
    novel_id: int
    chapters_processed: int
    nodes_created: int
    nodes_updated: int
    summary: str
