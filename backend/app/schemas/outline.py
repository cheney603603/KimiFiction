"""
大纲相关Pydantic模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ArcItem(BaseModel):
    """剧情弧项"""
    arc_id: str
    title: str
    description: str
    start_chapter: int
    end_chapter: int
    key_events: List[str]
    conflict: Optional[str] = None
    resolution: Optional[str] = None


class OutlineBase(BaseModel):
    """大纲基础模型"""
    novel_id: int = Field(..., description="所属小说ID")
    volume_number: int = Field(..., ge=1, description="第几卷")
    volume_title: str = Field(..., min_length=1, max_length=255, description="卷标题")


class OutlineCreate(OutlineBase):
    """创建大纲请求模型"""
    arcs: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    key_points: Optional[str] = None
    target_chapters: int = Field(default=100, ge=1)


class OutlineUpdate(BaseModel):
    """更新大纲请求模型"""
    volume_title: Optional[str] = Field(None, min_length=1, max_length=255)
    arcs: Optional[List[Dict[str, Any]]] = None
    key_points: Optional[str] = None
    target_chapters: Optional[int] = Field(None, ge=1)
    summary: Optional[str] = None


class OutlineResponse(BaseModel):
    """大纲响应模型"""
    id: int
    novel_id: int
    volume_number: int
    volume_title: str
    arcs: List[Dict[str, Any]]
    key_points: Optional[str]
    target_chapters: int
    actual_chapters: int
    summary: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OutlineListResponse(BaseModel):
    """大纲列表响应"""
    items: List[OutlineResponse]
    total: int


class OutlineGenerateRequest(BaseModel):
    """生成大纲请求"""
    novel_id: int
    total_volumes: int = Field(default=3, ge=1, le=10, description="总卷数")
    chapters_per_volume: int = Field(default=100, ge=10, le=200)
    genre_guidance: Optional[str] = None  # 额外的类型指导
